"""Coleta via Binance (ccxt) — arquitetura.md §2.1.

Primário: Binance pública (sem conta/chave para leitura OHLCV).
Fallback de rede: CoinGeckoProvider (arquitetura.md §5) e por último
SQLite local (models/db.py) com dado stale.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from models import db as db_module
from models.schemas import Candle, PriceSnapshot
from data.validation import sanitize_candles

SYMBOL_TO_PAIR: dict[str, str] = {
    "BTC": "BTC/USDT",
    "ETH": "ETH/USDT",
    "SOL": "SOL/USDT",
}

# Timeframes ccxt válidos na Binance.
CCXT_TIMEFRAMES = {"1m", "5m", "15m", "1h", "4h", "1d", "1w"}

# Compat: intervalos legados estilo CoinGecko ("30d", "365d", "max") -> timeframe ccxt.
LEGACY_TO_TIMEFRAME: dict[str, str] = {
    "1d": "1h",
    "7d": "4h",
    "14d": "4h",
    "30d": "1d",
    "90d": "1d",
    "180d": "1d",
    "365d": "1d",
    "1y": "1d",
    "max": "1w",
}


def resolve_timeframe(interval: str) -> str:
    if interval in CCXT_TIMEFRAMES:
        return interval
    return LEGACY_TO_TIMEFRAME.get(interval, "1d")


def _pair(symbol: str) -> str:
    pair = SYMBOL_TO_PAIR.get(symbol.upper())
    if pair is None:
        raise KeyError(f"ativo desconhecido: {symbol.upper()}")
    return pair


def _build_exchange():
    import ccxt  # import lazy: permite rodar testes sem a lib

    return ccxt.binance({"enableRateLimit": True, "timeout": 15000})


class BinanceProvider:
    """Provider ccxt/Binance com persistência SQLite e fallback CoinGecko."""

    def __init__(self, exchange=None, fallback=None, db_path: str | None = None) -> None:
        self._exchange = exchange  # injetável nos testes (fake sem rede)
        self._fallback = fallback
        self._db_path = db_path or os.getenv("ORUS_DB_PATH", None)

    def _client(self):
        if self._exchange is None:
            self._exchange = _build_exchange()
        return self._exchange

    def get_current_price(self, symbol: str) -> PriceSnapshot:
        pair = _pair(symbol)
        try:
            ticker = self._client().fetch_ticker(pair)
            price = float(ticker["last"] if ticker.get("last") is not None else ticker["close"])
            return PriceSnapshot(
                symbol=symbol.upper(),
                price=price,
                timestamp=datetime.now(timezone.utc),
            )
        except (KeyError, ValueError):
            raise
        except Exception:
            if self._fallback is not None:
                return self._fallback.get_current_price(symbol)
            raise

    def get_ohlc(self, symbol: str, interval: str, limit: int) -> list[Candle]:
        timeframe = resolve_timeframe(interval)
        pair = _pair(symbol)
        try:
            raw = self._client().fetch_ohlcv(pair, timeframe=timeframe, limit=max(1, limit))
            candles = [
                Candle(
                    timestamp=datetime.fromtimestamp(ts / 1000, tz=timezone.utc),
                    open=float(o),
                    high=float(h),
                    low=float(low),
                    close=float(c),
                    volume=float(v),
                )
                for ts, o, h, low, c, v in raw
            ]
            # Só candles fechados alimentam indicadores/SQLite: o último da
            # exchange em geral ainda está em formação (não é dado final).
            out, _ = sanitize_candles(candles, timeframe=timeframe, drop_forming=True)
            out = out[-max(0, limit):] if limit else []
            if out:
                try:
                    db_module.save_candles(symbol, timeframe, out, self._db_path)
                except Exception:
                    pass  # cache SQLite é best-effort
            return out
        except (KeyError, ValueError):
            raise
        except Exception:
            # 1) tenta SQLite stale (pode estar defasado: a idade real é
            # exposta pelo sinal via data_age_seconds/stale, nunca como atual)
            try:
                cached = db_module.load_candles(symbol, timeframe, limit, self._db_path)
                clean, _ = sanitize_candles(cached, timeframe=timeframe, drop_forming=False)
                if clean:
                    return clean[-max(0, limit):] if limit else []
            except Exception:
                pass
            # 2) tenta fallback (CoinGecko)
            if self._fallback is not None:
                rows = self._fallback.get_ohlc(symbol, interval, limit)
                clean, _ = sanitize_candles(rows, timeframe=timeframe, drop_forming=False)
                return clean[-max(0, limit):] if limit else []
            raise

    def get_volume(self, symbol: str, interval: str) -> float:
        timeframe = resolve_timeframe(interval)
        try:
            candles = self.get_ohlc(symbol, interval, 30)
            if not candles:
                return 0.0
            return float(sum(c.volume for c in candles[-7:]))
        except (KeyError, ValueError):
            raise
        except Exception:
            if self._fallback is not None:
                return self._fallback.get_volume(symbol, interval)
            return 0.0
