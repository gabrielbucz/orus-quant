"""Camada de coleta — interface + stub. Fonte: SDD §2.1.

CoinGeckoProvider real é a próxima tarefa; este stub determinístico permite
a API e o scoring funcionarem sem rede.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone

from models.schemas import Candle, PriceSnapshot

_STUB_PRICES: dict[str, float] = {"BTC": 100000.0, "ETH": 3500.0, "SOL": 150.0}


class PriceDataProvider(ABC):
    @abstractmethod
    def get_current_price(self, symbol: str) -> PriceSnapshot: ...

    @abstractmethod
    def get_ohlc(self, symbol: str, interval: str, limit: int) -> list[Candle]: ...

    @abstractmethod
    def get_volume(self, symbol: str, interval: str) -> float: ...


class StubProvider(PriceDataProvider):
    """Provider in-memory determinístico (sem rede) para bootstrapping da API."""

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


# TODO (próxima tarefa): implementar CoinGeckoProvider(PriceDataProvider)
# com throttling + fallback para cache expirado (spec.md §6).
_provider: PriceDataProvider = StubProvider()


def get_provider() -> PriceDataProvider:
    return _provider
