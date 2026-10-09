"""BinanceProvider (ccxt) + SQLite — arquitetura.md §2.1/§3. Sem rede: fake exchange."""

import os
from datetime import datetime, timezone

from data.binance_provider import BinanceProvider, resolve_timeframe
from models import db as db_module


class FakeExchange:
    def __init__(self, ohlcv=None, ticker=None, fail=False):
        self._ohlcv = ohlcv or [
            [1719792000000, 60000.0, 61000.0, 59000.0, 60500.0, 123.0],
            [1719878400000, 60500.0, 62000.0, 60000.0, 61500.0, 200.0],
        ]
        self._ticker = ticker or {"last": 67234.5}
        self._fail = fail
        self.calls = []

    def fetch_ohlcv(self, pair, timeframe="1d", limit=100):
        self.calls.append((pair, timeframe, limit))
        if self._fail:
            raise RuntimeError("rede fora")
        return self._ohlcv[:limit]

    def fetch_ticker(self, pair):
        if self._fail:
            raise RuntimeError("rede fora")
        return dict(self._ticker)


def _db(tmp_path):
    return str(tmp_path / "test.db")


def test_resolve_timeframe():
    assert resolve_timeframe("1d") == "1d"  # timeframe ccxt passa direto
    assert resolve_timeframe("15m") == "15m"
    assert resolve_timeframe("30d") == "1d"  # legado CoinGecko
    assert resolve_timeframe("max") == "1w"


def test_ohlc_parse_e_persiste_sqlite(tmp_path):
    ex = FakeExchange()
    p = BinanceProvider(exchange=ex, db_path=_db(tmp_path))
    candles = p.get_ohlc("BTC", "1d", 2)
    assert len(candles) == 2
    assert candles[-1].close == 61500.0
    assert ex.calls[0][0] == "BTC/USDT"
    # persistiu no SQLite
    cached = db_module.load_candles("BTC", "1d", 10, _db(tmp_path))
    assert len(cached) == 2
    assert cached[-1].close == 61500.0


def test_preco_atual(tmp_path):
    p = BinanceProvider(exchange=FakeExchange(), db_path=_db(tmp_path))
    snap = p.get_current_price("BTC")
    assert snap.symbol == "BTC"
    assert snap.price == 67234.5


def test_fallback_sqlite_quando_rede_cai(tmp_path):
    db_path = _db(tmp_path)
    ok = BinanceProvider(exchange=FakeExchange(), db_path=db_path)
    assert len(ok.get_ohlc("ETH", "1d", 2)) == 2
    # agora rede cai -> serve SQLite stale
    down = BinanceProvider(exchange=FakeExchange(fail=True), db_path=db_path)
    candles = down.get_ohlc("ETH", "1d", 2)
    assert len(candles) == 2
    assert candles[-1].close == 61500.0


def test_fallback_coingecko(tmp_path):
    from data.provider import StubProvider

    down = BinanceProvider(
        exchange=FakeExchange(fail=True),
        fallback=StubProvider(),
        db_path=_db(tmp_path),
    )
    # sem SQLite, cai no fallback (stub devolve candles chapados)
    candles = down.get_ohlc("BTC", "1d", 3)
    assert len(candles) == 3


def test_ativo_desconhecido(tmp_path):
    import pytest

    p = BinanceProvider(exchange=FakeExchange(), db_path=_db(tmp_path))
    with pytest.raises(KeyError):
        p.get_ohlc("XXX", "1d", 5)
