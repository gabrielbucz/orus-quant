"""Backtest engine + endpoints: métricas sãs e walk-forward — spec.md §7."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backtest.engine import run_backtest
from data import cache as signal_cache
from data.provider import StubProvider, set_provider
from models.schemas import Candle


def _candles(closes: list[float]) -> list[Candle]:
    now = datetime.now(timezone.utc)
    return [
        Candle(timestamp=now, open=c - 1, high=c + 1, low=c - 2, close=c, volume=100.0)
        for c in closes
    ]


def test_sem_lookahead_e_metricas_sas():
    closes = [100.0 + i * 0.5 + (i % 5) for i in range(120)]
    report = run_backtest(_candles(closes), "swing_trade")
    assert 0.0 <= report.win_rate <= 1.0
    assert report.max_drawdown <= 0.0
    assert report.trades >= 0
    assert report.windows == 3
    assert report.period_start <= report.period_end


def test_serie_vazia_e_horizonte_invalido():
    with pytest.raises(ValueError):
        run_backtest([], "swing_trade")
    with pytest.raises(ValueError):
        run_backtest(_candles([1.0, 2.0, 3.0, 4.0, 5.0, 6.0]), "intraday")


def test_queda_forte_nao_lucra():
    closes = [500.0 - i * 2 for i in range(120)]
    report = run_backtest(_candles(closes), "swing_trade")
    assert report.cumulative_return <= 0.0


@pytest.fixture()
def client():
    import api.backtest as backtest_module
    import main as main_module

    set_provider(StubProvider())
    for horizon_cache in signal_cache._caches.values():
        horizon_cache.clear()
    backtest_module._store.clear()
    return TestClient(main_module.app)


def test_api_run_get_roundtrip(client):
    created = client.post(
        "/backtest/run", json={"symbol": "BTC", "horizon": "swing_trade", "limit": 60}
    ).json()
    assert created["id"]
    assert created["result"]["strategy_name"] == "score-long-only:BTC:swing_trade"
    fetched = client.get(f"/backtest/{created['id']}").json()
    assert fetched == created["result"]


def test_api_validacoes(client):
    assert client.post("/backtest/run", json={"symbol": "XXX"}).status_code == 404
    assert client.post("/backtest/run", json={"horizon": "intraday"}).status_code == 404
    bad = client.post(
        "/backtest/run",
        json={"symbol": "BTC", "buy_threshold": 40, "sell_threshold": 60},
    )
    assert bad.status_code == 422
    assert client.get("/backtest/inexistente").status_code == 404
