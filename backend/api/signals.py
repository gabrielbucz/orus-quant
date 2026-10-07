"""Endpoints de sinais — spec.md §3.

TODO: os valores de entrada (DEMO_TARGETS) são placeholders até o engine
de indicadores (strategy/indicators) existir. O cálculo via scoring +
mapeamento cor/label já é o definitivo.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from data import cache as signal_cache
from models.schemas import SignalScore
from strategy import scoring
from strategy.config import ASSETS, WEIGHTS

router = APIRouter(prefix="/signals", tags=["signals"])

HORIZONS = ("day_trade", "swing_trade", "hold")

# Alvos demo por (ativo, horizonte) — espelham o mock
# orus_quant_signal_heatmap_table.html e o exemplo do spec.md §3.
DEMO_TARGETS: dict[str, dict[str, int]] = {
    "BTC": {"day_trade": 18, "swing_trade": 50, "hold": 84},
    "ETH": {"day_trade": 70, "swing_trade": 70, "hold": 30},
    "SOL": {"day_trade": 90, "swing_trade": 85, "hold": 50},
}


def _build_signal(symbol: str, horizon: str) -> SignalScore:
    target = DEMO_TARGETS[symbol][horizon]
    indicators = {name: float(target) for name in WEIGHTS[horizon]}
    score = scoring.compute_score(indicators, horizon)
    color, label = scoring.score_to_color_label(score)
    now = datetime.now(timezone.utc)
    signal = SignalScore(
        symbol=symbol,
        horizon=horizon,  # type: ignore[arg-type]
        score=score,
        color=color,  # type: ignore[arg-type]
        label=label,
        data_age_seconds=0,
        last_updated=now,
    )
    signal_cache.cache_set(horizon, symbol, signal)
    return signal


def _get_signal(symbol: str, horizon: str) -> SignalScore:
    symbol = symbol.upper()
    if symbol not in ASSETS or symbol not in DEMO_TARGETS:
        raise HTTPException(status_code=404, detail=f"ativo desconhecido: {symbol}")
    if horizon not in HORIZONS:
        raise HTTPException(status_code=404, detail=f"horizonte desconhecido: {horizon}")
    cached = signal_cache.cache_get(horizon, symbol)
    if cached is not None:
        cached.data_age_seconds = signal_cache.data_age_seconds("signals", symbol)
        return cached
    return _build_signal(symbol, horizon)


@router.get("", response_model=list[SignalScore])
def list_signals() -> list[SignalScore]:
    return [
        _get_signal(symbol, horizon) for symbol in ASSETS for horizon in HORIZONS
    ]


@router.get("/{symbol}", response_model=list[SignalScore])
def signals_by_symbol(symbol: str) -> list[SignalScore]:
    return [_get_signal(symbol, horizon) for horizon in HORIZONS]


@router.get("/{symbol}/{horizon}", response_model=SignalScore)
def signal_detail(symbol: str, horizon: str) -> SignalScore:
    return _get_signal(symbol, horizon)
