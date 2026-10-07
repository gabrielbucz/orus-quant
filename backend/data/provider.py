"""Camada de coleta — interface + providers. Fonte: SDD §2.1 / spec.md §6.

- `StubProvider`: in-memory determinístico (sem rede) para dev/testes.
- `CoinGeckoProvider`: coleta real via CoinGecko com throttling e fallback
  para o último dado em cache quando a API falha (rate limit/rede).
"""

from __future__ import annotations

import os
import threading
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Callable

import httpx
from dotenv import load_dotenv

from models.schemas import Candle, PriceSnapshot

load_dotenv()

SYMBOL_TO_ID: dict[str, str] = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
}

_STUB_PRICES: dict[str, float] = {"BTC": 100000.0, "ETH": 3500.0, "SOL": 150.0}

_COINGECKO_BASE = "https://api.coingecko.com/api/v3"

# Intervalo mínimo entre chamadas (spec.md §6 — plano demo/free ~10 req/min).
DEFAULT_MIN_INTERVAL_SECONDS = 6.0

_INTERVAL_TO_DAYS: dict[str, int] = {
    "1d": 1,
    "7d": 7,
    "14d": 14,
    "30d": 30,
    "90d": 90,
    "180d": 180,
    "365d": 365,
    "1y": 365,
    "max": 365,
}


class PriceDataProvider(ABC):
    @abstractmethod
    def get_current_price(self, symbol: str) -> PriceSnapshot: ...

    @abstractmethod
    def get_ohlc(self, symbol: str, interval: str, limit: int) -> list[Candle]: ...

    @abstractmethod
    def get_volume(self, symbol: str, interval: str) -> float: ...


def _coingecko_id(symbol: str) -> str:
    coin_id = SYMBOL_TO_ID.get(symbol.upper())
    if coin_id is None:
        raise KeyError(f"ativo desconhecido: {symbol.upper()}")
    return coin_id


class StubProvider(PriceDataProvider):
    """Provider in-memory determinístico (sem rede) para bootstrapping e testes."""

    def get_current_price(self, symbol: str) -> PriceSnapshot:
        symbol = symbol.upper()
        if symbol not in _STUB_PRICES:
            raise KeyError(f"ativo desconhecido: {symbol}")
        return PriceSnapshot(
            symbol=symbol,
            price=_STUB_PRICES[symbol],
            timestamp=datetime.now(timezone.utc),
        )

    def get_ohlc(self, symbol: str, interval: str, limit: int) -> list[Candle]:
        snapshot = self.get_current_price(symbol)
        return [
            Candle(
                timestamp=snapshot.timestamp,
                open=snapshot.price,
                high=snapshot.price,
                low=snapshot.price,
                close=snapshot.price,
                volume=0.0,
            )
            for _ in range(max(0, limit))
        ]

    def get_volume(self, symbol: str, interval: str) -> float:
        self.get_current_price(symbol)  # valida o símbolo
        return 0.0


# Tipo do fetcher injetável (testes usam stub sem rede):
# recebe (url, params, headers) e retorna o JSON já decodificado.
HttpGet = Callable[[str, dict[str, Any], dict[str, str]], Any]


def _default_http_get(url: str, params: dict[str, Any], headers: dict[str, str]) -> Any:
    response = httpx.get(url, params=params, headers=headers, timeout=15.0)
    response.raise_for_status()
    return response.json()


class CoinGeckoProvider(PriceDataProvider):
    """Coleta real via CoinGecko (plano demo/free).

    - Throttling: garante `min_interval_seconds` entre chamadas.
    - Fallback (spec.md §6): em falha de rede/rate limit, devolve o último
      dado em cache em vez de quebrar a API.
    """

    def __init__(
        self,
        api_key: str | None = None,
        min_interval_seconds: float = DEFAULT_MIN_INTERVAL_SECONDS,
        http_get: HttpGet | None = None,
    ) -> None:
        self._api_key = api_key if api_key is not None else os.getenv("COINGECKO_API_KEY", "")
        self._min_interval = max(0.0, min_interval_seconds)
        self._http_get: HttpGet = http_get or _default_http_get
        self._lock = threading.Lock()
        self._last_call = 0.0
        # fallback cru: chave -> (timestamp, valor)
        self._fallback: dict[str, tuple[float, Any]] = {}

    def _headers(self) -> dict[str, str]:
        if self._api_key:
            return {"x-cg-demo-api-key": self._api_key}
        return {}

    def _throttled_get(self, path: str, params: dict[str, Any]) -> Any:
        with self._lock:
            now = time.monotonic()
            wait = self._min_interval - (now - self._last_call)
            if wait > 0:
                time.sleep(wait)
            try:
                data = self._http_get(f"{_COINGECKO_BASE}{path}", params, self._headers())
            except Exception:
                key = f"{path}:{sorted(params.items())}"
                if key in self._fallback:
                    return self._fallback[key][1]
                raise
            self._last_call = time.monotonic()
            key = f"{path}:{sorted(params.items())}"
            self._fallback[key] = (time.time(), data)
            return data

    def get_current_price(self, symbol: str) -> PriceSnapshot:
        coin_id = _coingecko_id(symbol)
        data = self._throttled_get(
            "/simple/price", {"ids": coin_id, "vs_currencies": "usd"}
        )
        try:
            price = float(data[coin_id]["usd"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(f"resposta inesperada do CoinGecko: {data!r}") from exc
        return PriceSnapshot(
            symbol=symbol.upper(),
            price=price,
            timestamp=datetime.now(timezone.utc),
        )

    def get_ohlc(self, symbol: str, interval: str, limit: int) -> list[Candle]:
        coin_id = _coingecko_id(symbol)
        days = _INTERVAL_TO_DAYS.get(interval, 30)
        rows = self._throttled_get(
            f"/coins/{coin_id}/ohlc",
            {"vs_currency": "usd", "days": days},
        )
        candles = [
            Candle(
                timestamp=datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc),
                open=float(o),
                high=float(h),
                low=float(low),
                close=float(c),
                volume=0.0,
            )
            for ts_ms, o, h, low, c in rows
        ]
        return candles[-max(0, limit):] if limit else []

    def get_volume(self, symbol: str, interval: str) -> float:
        coin_id = _coingecko_id(symbol)
        days = _INTERVAL_TO_DAYS.get(interval, 1)
        data = self._throttled_get(
            f"/coins/{coin_id}/market_chart",
            {"vs_currency": "usd", "days": days},
        )
        try:
            volumes = data["total_volumes"]
            return float(volumes[-1][1])
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise RuntimeError(f"resposta inesperada do CoinGecko: {data!r}") from exc


_provider: PriceDataProvider = (
    StubProvider()
    if os.getenv("ORUS_USE_STUB", "").strip() in {"1", "true", "yes"}
    else CoinGeckoProvider()
)


def get_provider() -> PriceDataProvider:
    return _provider


def set_provider(provider: PriceDataProvider) -> None:
    """Troca o provider global (testes)."""
    global _provider
    _provider = provider
