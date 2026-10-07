"""Engine: candles → indicadores normalizados por horizonte (spec.md §4.2).

As chaves de cada dict batem exatamente com `strategy/config.py::WEIGHTS`,
para alimentar `strategy/scoring.py::compute_score` direto.
"""

from __future__ import annotations

from models.schemas import Candle

from . import core


def compute_day_trade(candles: list[Candle]) -> dict[str, float]:
    if not candles:
        raise ValueError("sem candles")
    closes = core.closes_of(candles)
    last = closes[-1]
    return {
        "rsi_short": core.rsi(closes, period=7),
        "vwap_distance": core.distance_score(last, core.vwap(candles)),
        "volume_spike": core.volume_spike_score(core.volumes_of(candles)),
    }


def compute_swing_trade(candles: list[Candle]) -> dict[str, float]:
    if not candles:
        raise ValueError("sem candles")
    closes = core.closes_of(candles)
    return {
        "macd": core.macd_score(closes),
        "ma_cross": core.ma_cross_score(closes),
        "rsi_daily": core.rsi(closes, period=14),
        "support_resistance": core.range_position_score(closes, period=50),
    }


def compute_hold(candles: list[Candle]) -> dict[str, float]:
    if not candles:
        raise ValueError("sem candles")
    closes = core.closes_of(candles)
    last = closes[-1]
    return {
        # Tendência de longo prazo: distância do preço à SMA-200.
        "long_trend": core.distance_score(last, core.sma(closes, 200)),
        # Posição no ciclo: onde o preço está na amplitude total disponível.
        "cycle_position": core.range_position_score(closes, period=len(closes)),
        # Agregados (dominância etc.) — fora da v1, neutro até ter fonte.
        "aggregates": 50.0,
    }


def compute_all(candles: list[Candle]) -> dict[str, dict[str, float]]:
    return {
        "day_trade": compute_day_trade(candles),
        "swing_trade": compute_swing_trade(candles),
        "hold": compute_hold(candles),
    }
