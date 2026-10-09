"""Consistência dos dados: duplicatas, ordem, OHLC inválido, forming, idade
real e fallback honesto. Indicador certo sobre dado errado continua errado.
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from data import cache as signal_cache
from data.provider import StubProvider, set_provider
from data.validation import (
    data_age_seconds,
    is_stale,
    is_valid_ohlc,
    sanitize_candles,
)
from models.schemas import Candle

NOW = datetime.now(timezone.utc)


def _c(ts: datetime, o: float, h: float, low: float, c: float, v: float = 10.0) -> Candle:
    return Candle(timestamp=ts, open=o, high=h, low=low, close=c, volume=v)


def _closed_series(n: int = 10, step_s: int = 3600, end: datetime | None = None) -> list[Candle]:
    end = end or (NOW - timedelta(seconds=step_s))  # último FECHADO
    return [
        _c(end - timedelta(seconds=(n - 1 - i) * step_s), 100.0, 101.0, 99.0, 100.0)
        for i in range(n)
    ]


# --- OHLC válido/inválido ---


def test_ohlc_valido_e_casos_invalidos():
    assert is_valid_ohlc(_c(NOW, 100.0, 101.0, 99.0, 100.0))
    assert not is_valid_ohlc(_c(NOW, 100.0, 99.0, 101.0, 100.0))  # high<low
    assert not is_valid_ohlc(_c(NOW, 100.0, 100.0, 99.0, 101.0))  # high<close
    assert not is_valid_ohlc(_c(NOW, 100.0, 101.0, 100.5, 100.0))  # low>open
    assert not is_valid_ohlc(_c(NOW, -100.0, 101.0, 99.0, 100.0))  # preço negativo
    assert not is_valid_ohlc(_c(NOW, 0.0, 101.0, 99.0, 100.0))  # preço zero
    assert not is_valid_ohlc(_c(NOW, 100.0, 101.0, 99.0, 100.0, v=-1.0))  # volume<0
    assert not is_valid_ohlc(_c(NOW, 100.0, float("nan"), 99.0, 100.0))  # NaN
    assert not is_valid_ohlc(_c(NOW, 100.0, float("inf"), 99.0, 100.0))  # inf


# --- Ordenação, duplicatas, inválidos, forming ---


def test_fora_de_ordem_ordena():
    series = _closed_series(5)
    shuffled = [series[3], series[0], series[4], series[1], series[2]]
    clean, report = sanitize_candles(shuffled, timeframe="1h", now=NOW)
    assert report.was_out_of_order
    assert [c.timestamp for c in clean] == sorted(c.timestamp for c in clean)
    assert len(clean) == 5


def test_duplicata_vale_ultimo():
    ts = NOW - timedelta(hours=2)
    a = _c(ts, 100.0, 101.0, 99.0, 100.0)
    b = _c(ts, 100.0, 121.0, 99.0, 120.0)  # mesmo ts, recebido depois
    clean, report = sanitize_candles([a, b], timeframe="1h", now=NOW)
    assert report.dropped_duplicates == 1
    assert len(clean) == 1 and clean[0].close == 120.0


def test_invalidos_descartados_e_vazio_nao_quebra():
    ok = _closed_series(3)
    bad = _c(NOW - timedelta(minutes=30), -5.0, 1.0, 2.0, 3.0)  # ts distinto
    clean, report = sanitize_candles(ok + [bad], timeframe="1h", now=NOW)
    assert report.dropped_invalid == 1 and len(clean) == 3
    clean2, _ = sanitize_candles([], timeframe="1h", now=NOW)
    assert clean2 == []


def test_candle_em_formacao_excluido():
    closed = _closed_series(5)  # último = NOW-1h (fechado p/ 1h)
    forming = _c(NOW, 100.0, 501.0, 99.0, 500.0)  # ainda formando, OHLC válido
    clean, report = sanitize_candles(closed + [forming], timeframe="1h", now=NOW)
    assert report.dropped_forming == 1
    assert len(clean) == 5 and all(c.close == 100.0 for c in clean)


def test_sem_timeframe_nao_corta_forming():
    closed = _closed_series(3)
    clean, _ = sanitize_candles(closed, timeframe=None, drop_forming=True)
    assert len(clean) == 3


# --- Idade real e stale ---


def test_idade_e_stale():
    old = _closed_series(5, end=NOW - timedelta(days=10))
    assert data_age_seconds(old, NOW) == pytest.approx(10 * 86_400, abs=2)
    assert is_stale(old, "1h", NOW)  # 10 dias >> 2×1h
    fresh = _closed_series(5)  # último = NOW-1h
    assert not is_stale(fresh, "1h", NOW)
    assert is_stale([], "1h", NOW)


def test_stub_sem_timestamps_duplicados():
    candles = StubProvider().get_ohlc("BTC", "1d", 20)
    ts = [c.timestamp for c in candles]
    assert len(set(ts)) == 20 and ts == sorted(ts)


# --- Sinais com idade honesta ---


class _FixedProvider(StubProvider):
    """Stub com série fixa (permite dado antigo / candle formando)."""

    def __init__(self, candles: list[Candle]):
        self._candles = candles

    def get_ohlc(self, symbol: str, interval: str, limit: int) -> list[Candle]:
        if symbol.upper() not in ("BTC", "ETH", "SOL"):
            raise KeyError(f"ativo desconhecido: {symbol.upper()}")
        return list(self._candles[-limit:])


@pytest.fixture()
def client():
    import api.signals as signals_module
    import main as main_module

    for horizon_cache in signal_cache._caches.values():
        horizon_cache.clear()
    signal_cache._last_write.clear()
    signals_module._LAST_KNOWN.clear()
    set_provider(StubProvider())
    return TestClient(main_module.app)


def test_sinal_expõe_idade_real_e_stale(client):
    old = _closed_series(200, step_s=3600, end=NOW - timedelta(days=10))
    set_provider(_FixedProvider(old))
    data = client.get("/signals/BTC/day_trade").json()
    assert data["last_updated"]  # as-of do dado, não hora do cálculo
    assert data["data_age_seconds"] >= 9 * 86_400  # ~10 dias, não zero
    assert data["stale"] is True
    assert data["candles_n"] == 200  # série antiga já toda fechada, nada a cortar


def test_forming_nao_contamina_sinal(client):
    closed = _closed_series(199)  # 199 < limit 200: provider entrega tudo
    forming = _c(NOW, 100.0, 500.0, 99.0, 450.0)  # spike que distorceria tudo
    set_provider(_FixedProvider(closed + [forming]))
    with_spike = client.get("/signals/BTC/day_trade").json()
    set_provider(_FixedProvider(closed))
    for horizon_cache in signal_cache._caches.values():
        horizon_cache.clear()
    without_spike = client.get("/signals/BTC/day_trade").json()
    assert with_spike["score"] == without_spike["score"]
    assert with_spike["candles_n"] == without_spike["candles_n"] == 199


def test_fallback_marca_stale_sem_zerar_idade(client):
    import api.signals as signals_module

    old = _closed_series(200, step_s=3600, end=NOW - timedelta(days=5))
    set_provider(_FixedProvider(old))
    first = client.get("/signals/BTC/day_trade").json()
    assert first["stale"] is True

    class _Down(_FixedProvider):
        def get_ohlc(self, symbol: str, interval: str, limit: int):
            raise RuntimeError("fonte fora do ar")

    set_provider(_Down(old))
    for horizon_cache in signal_cache._caches.values():
        horizon_cache.clear()  # expira o TTL, mas _LAST_KNOWN permanece
    second = client.get("/signals/BTC/day_trade").json()
    assert second["score"] == first["score"]  # serviu o último conhecido
    assert second["stale"] is True  # e admite que não é atual
    assert second["data_age_seconds"] >= first["data_age_seconds"]
    assert "_LAST_KNOWN" in dir(signals_module)


def test_sem_candle_valido_vira_502(client):
    import main as main_module

    bad = [_c(NOW - timedelta(hours=i + 2), -1.0, -0.5, -2.0, -1.5) for i in range(10)]
    set_provider(_FixedProvider(bad))
    no_raise = TestClient(main_module.app, raise_server_exceptions=False)
    resp = no_raise.get("/signals/BTC/day_trade")
    assert resp.status_code in (500, 502)  # sem dado válido não há sinal


# --- Binance: forming não alimenta indicador nem SQLite ---


def test_binance_descarta_forming_e_nao_persiste(tmp_path):
    import time

    from data.binance_provider import BinanceProvider
    from models import db as db_module

    now_ms = int(time.time() * 1000)
    day_ms = 86_400_000
    forming_ts = (now_ms // day_ms) * day_ms  # abertura do dia corrente (forming p/ 1d)
    ohlcv = [
        [forming_ts - 2 * day_ms, 100.0, 101.0, 99.0, 100.0, 10.0],
        [forming_ts - 1 * day_ms, 100.0, 101.0, 99.0, 100.0, 10.0],
        [forming_ts, 100.0, 500.0, 99.0, 450.0, 10.0],  # forming: spike irreal
    ]

    class _Ex:
        def fetch_ohlcv(self, pair, timeframe="1d", limit=100):
            return ohlcv[:limit]

        def fetch_ticker(self, pair):
            return {"last": 100.0}

    db_path = str(tmp_path / "t.db")
    candles = BinanceProvider(exchange=_Ex(), db_path=db_path).get_ohlc("BTC", "1d", 3)
    assert [c.close for c in candles] == [100.0, 100.0]  # spike forming fora
    saved = db_module.load_candles("BTC", "1d", 10, db_path)
    assert [c.close for c in saved] == [100.0, 100.0]  # SQLite sem forming


# --- Backtest sanitiza a entrada ---


def test_backtest_ordena_e_dedup_antes_de_calcular():
    from backtest.engine import run_backtest

    base = _closed_series(120, step_s=86_400)
    for i, c in enumerate(base):  # série com tendência p/ gerar sinais
        c.close = 100.0 + i * 0.5 + (i % 5)
        c.open, c.high, c.low = c.close - 1, c.close + 1, c.close - 2
    shuffled = list(reversed(base))
    dup = base + [base[-1]]  # duplicata do último
    r1 = run_backtest(base, "swing_trade", n_windows=2, test_windows=1, cost_bps=0.0)
    r2 = run_backtest(shuffled, "swing_trade", n_windows=2, test_windows=1, cost_bps=0.0)
    r3 = run_backtest(dup, "swing_trade", n_windows=2, test_windows=1, cost_bps=0.0)
    assert r1.cumulative_return == pytest.approx(r2.cumulative_return)
    assert r1.cumulative_return == pytest.approx(r3.cumulative_return)
    assert r1.trades == r3.trades


def test_backtest_sem_dado_valido_rejeita():
    from backtest.engine import run_backtest

    bad = [_c(NOW - timedelta(days=i + 1), -1.0, -0.5, -2.0, -1.5) for i in range(30)]
    with pytest.raises(ValueError):
        run_backtest(bad, "swing_trade")
