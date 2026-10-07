"""CoinGeckoProvider: contrato, parsing, throttling e fallback — spec.md §6/§7."""

import pytest

from data import provider as provider_module
from data.provider import CoinGeckoProvider, StubProvider


def _fake_http_get_factory(payloads: dict, calls: list):
    def fake(url: str, params: dict, headers: dict):
        calls.append((url, params))
        for prefix, payload in payloads.items():
            if url.endswith(prefix):
                if isinstance(payload, Exception):
                    raise payload
                return payload
        raise AssertionError(f"URL inesperada: {url}")
    return fake


def test_preco_atual_parse():
    calls: list = []
    http_get = _fake_http_get_factory(
        {"/simple/price": {"bitcoin": {"usd": 67234.5}}}, calls
    )
    provider = CoinGeckoProvider(api_key="demo", min_interval_seconds=0, http_get=http_get)
    snapshot = provider.get_current_price("BTC")
    assert snapshot.symbol == "BTC"
    assert snapshot.price == 67234.5
    assert calls[0][1] == {"ids": "bitcoin", "vs_currencies": "usd"}


def test_ohlc_parse_e_limite():
    rows = [
        [1719792000000, 60000.0, 61000.0, 59000.0, 60500.0],
        [1719878400000, 60500.0, 62000.0, 60000.0, 61500.0],
        [1719964800000, 61500.0, 63000.0, 61000.0, 62500.0],
    ]
    http_get = _fake_http_get_factory({"/ohlc": rows}, [])
    provider = CoinGeckoProvider(min_interval_seconds=0, http_get=http_get)
    candles = provider.get_ohlc("BTC", "7d", 2)
    assert len(candles) == 2
    assert candles[-1].close == 62500.0
    assert candles[-1].high == 63000.0


def test_ativo_desconhecido():
    provider = CoinGeckoProvider(min_interval_seconds=0, http_get=lambda *a: {})
    with pytest.raises(KeyError):
        provider.get_current_price("XXX")


def test_fallback_em_rate_limit():
    calls: list = []
    state = {"fail": False}

    def flaky(url: str, params: dict, headers: dict):
        calls.append(url)
        if state["fail"]:
            raise RuntimeError("429 rate limit")
        return {"ethereum": {"usd": 3500.0}}

    provider = CoinGeckoProvider(min_interval_seconds=0, http_get=flaky)
    first = provider.get_current_price("ETH")
    assert first.price == 3500.0
    state["fail"] = True
    second = provider.get_current_price("ETH")
    assert second.price == 3500.0  # serviu o último dado em cache
    assert len(calls) == 2


def test_sem_fallback_propaga_erro():
    def boom(url: str, params: dict, headers: dict):
        raise RuntimeError("rede fora")

    provider = CoinGeckoProvider(min_interval_seconds=0, http_get=boom)
    with pytest.raises(RuntimeError):
        provider.get_current_price("SOL")


def test_stub_ainda_ok():
    stub = StubProvider()
    assert stub.get_current_price("BTC").price > 0
    assert len(stub.get_ohlc("BTC", "1d", 5)) == 5


def test_set_provider_troca_global(monkeypatch):
    stub = StubProvider()
    provider_module.set_provider(stub)
    assert provider_module.get_provider() is stub
