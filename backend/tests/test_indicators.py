"""Engine de indicadores: tendências claras, valores neutros e robustez — spec.md §4.2."""

from datetime import datetime, timezone

import pytest

from indicators import core, engine
from models.schemas import Candle
from strategy.config import WEIGHTS


def _candles(closes: list[float], volume: float = 100.0) -> list[Candle]:
    now = datetime.now(timezone.utc)
    return [
        Candle(
            timestamp=now, open=c - 1, high=c + 1, low=c - 2, close=c, volume=volume
        )
        for c in closes
    ]


def _uptrend(n: int = 60) -> list[float]:
    return [100.0 + i for i in range(n)]


def _downtrend(n: int = 60) -> list[float]:
    return [200.0 - i for i in range(n)]


def test_chaves_batem_com_pesos():
    candles = _candles(_uptrend())
    for horizon, fn in [
        ("day_trade", engine.compute_day_trade),
        ("swing_trade", engine.compute_swing_trade),
        ("hold", engine.compute_hold),
    ]:
        assert set(fn(candles)) == set(WEIGHTS[horizon])


def test_tudo_entre_0_e_100():
    for series in (_uptrend(), _downtrend(), [100.0] * 30):
        for indicators in engine.compute_all(_candles(series)).values():
            for value in indicators.values():
                assert 0.0 <= value <= 100.0


def test_alta_forte_pontua_mais_que_queda():
    up = engine.compute_all(_candles(_uptrend()))
    down = engine.compute_all(_candles(_downtrend()))
    for horizon in ("day_trade", "swing_trade", "hold"):
        assert sum(up[horizon].values()) > sum(down[horizon].values())


def test_rsi_extremos():
    assert core.rsi(_uptrend(30), 14) > 70
    assert core.rsi(_downtrend(30), 14) < 30
    assert core.rsi([100.0] * 20, 14) == 50.0


def test_sem_volume_vira_neutro():
    candles = _candles(_uptrend(), volume=0.0)  # caso CoinGecko OHLC
    assert engine.compute_day_trade(candles)["volume_spike"] == 50.0


def test_serie_curta_nao_quebra():
    candles = _candles([100.0, 101.0])
    for indicators in engine.compute_all(candles).values():
        for value in indicators.values():
            assert 0.0 <= value <= 100.0


def test_serie_vazia_erro_claro():
    with pytest.raises(ValueError):
        engine.compute_day_trade([])
    with pytest.raises(ValueError):
        engine.compute_swing_trade([])
    with pytest.raises(ValueError):
        engine.compute_hold([])
