"""API de sinais ponta a ponta com StubProvider (sem rede) — spec.md §3."""

import pytest
from fastapi.testclient import TestClient

from data import cache as signal_cache
from data.provider import StubProvider, set_provider


@pytest.fixture()
def client():
    import api.signals as signals_module
    import main as main_module

    set_provider(StubProvider())
    for horizon_cache in signal_cache._caches.values():
        horizon_cache.clear()
    signal_cache._last_write.clear()
    signals_module._LAST_KNOWN.clear()
    return TestClient(main_module.app)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_assets(client):
    assert client.get("/assets").json() == ["BTC", "ETH", "SOL"]


def test_signals_tabela_completa(client):
    data = client.get("/signals").json()
    assert len(data) == 9
    pares = {(s["symbol"], s["horizon"]) for s in data}
    assert len(pares) == 9
    for s in data:
        assert 0 <= s["score"] <= 100
        assert s["color"] in ("red", "orange", "yellow", "light_green", "green")
        assert s["data_age_seconds"] >= 0
        assert s["last_updated"]


def test_stub_flat_vira_neutro(client):
    # Stub devolve candles chapados → indicadores 50 → score 50 (amarelo).
    data = client.get("/signals/BTC/day_trade").json()
    assert data["score"] == 50
    assert data["color"] == "yellow"
    assert data["label"] == "Neutro"


def test_signals_por_ativo(client):
    data = client.get("/signals/ETH").json()
    assert {s["horizon"] for s in data} == {"day_trade", "swing_trade", "hold"}


def test_404(client):
    assert client.get("/signals/XXX").status_code == 404
    assert client.get("/signals/BTC/intraday").status_code == 404


def test_cache_segunda_chamada_igual(client):
    first = client.get("/signals/SOL/hold").json()
    second = client.get("/signals/SOL/hold").json()
    assert first["score"] == second["score"]
    assert second["data_age_seconds"] >= 0
