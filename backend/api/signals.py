"""Endpoints de sinais — spec.md §3 / SDD §2–§3.

Pipeline real: provider → candles → indicadores → scoring → cor/label.
Cache com TTL por horizonte; em falha da fonte, serve o último sinal
conhecido (mesmo expirado) com `data_age_seconds` honesto (spec.md §6).
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from data import cache as signal_cache
from data.provider import get_provider
from indicators import engine as indicators_engine
from models.schemas import SignalScore
from strategy import scoring
from strategy.config import ASSETS

router = APIRouter(prefix="/signals", tags=["signals"])

HORIZONS = ("day_trade", "swing_trade", "hold")

# Granularidade da série por horizonte (intervalos aceitos pelo provider).
HORIZON_SERIES: dict[str, tuple[str, int]] = {
    "day_trade": ("30d", 200),
    "swing_trade": ("365d", 400),
    "hold": ("max", 500),
}

_COMPUTE = {
    "day_trade": indicators_engine.compute_day_trade,
    "swing_trade": indicators_engine.compute_swing_trade,
    "hold": indicators_engine.compute_hold,
}

# Último sinal conhecido por (horizonte, ativo) — fallback além do TTL.
_LAST_KNOWN: dict[tuple[str, str], SignalScore] = {}


def _namespace(horizon: str) -> str:
    return f"signals:{horizon}"


def _build_signal(symbol: str, horizon: str) -> SignalScore:
    interval, limit = HORIZON_SERIES[horizon]
    candles = get_provider().get_ohlc(symbol, interval, limit)
    indicators = _COMPUTE[horizon](candles)
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
    signal_cache.cache_set(horizon, symbol, signal, namespace=_namespace(horizon))
    _LAST_KNOWN[(horizon, symbol)] = signal
    return signal


def _validate(symbol: str, horizon: str) -> str:
    symbol = symbol.upper()
    if symbol not in ASSETS:
        raise HTTPException(status_code=404, detail=f"ativo desconhecido: {symbol}")
    if horizon not in HORIZONS:
        raise HTTPException(status_code=404, detail=f"horizonte desconhecido: {horizon}")
    return symbol


def _refresh_age(signal: SignalScore, horizon: str) -> SignalScore:
    signal.data_age_seconds = signal_cache.data_age_seconds(
        _namespace(horizon), signal.symbol, fallback=signal.data_age_seconds
    )
    return signal


def _get_signal(symbol: str, horizon: str) -> SignalScore:
    symbol = _validate(symbol, horizon)
    cached = signal_cache.cache_get(horizon, symbol)
    if cached is not None:
        return _refresh_age(cached, horizon)
    try:
        return _build_signal(symbol, horizon)
    except (KeyError, ValueError):
        raise
    except Exception as exc:
        stale = _LAST_KNOWN.get((horizon, symbol))
        if stale is not None:
            return _refresh_age(stale, horizon)
        raise HTTPException(status_code=502, detail=f"fonte de dados indisponível: {exc}") from exc


@router.get("", response_model=list[SignalScore])
def list_signals() -> list[SignalScore]:
    return [_get_signal(symbol, horizon) for symbol in ASSETS for horizon in HORIZONS]


@router.get("/{symbol}", response_model=list[SignalScore])
def signals_by_symbol(symbol: str) -> list[SignalScore]:
    return [_get_signal(symbol, horizon) for horizon in HORIZONS]


@router.get("/{symbol}/{horizon}", response_model=SignalScore)
def signal_detail(symbol: str, horizon: str) -> SignalScore:
    return _get_signal(symbol, horizon)
