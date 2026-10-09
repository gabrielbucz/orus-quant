"""Endpoints de sinais — spec.md §3 / SDD §2–§3.

Pipeline real: provider → saneamento (ordena/dedup/valida, exclui candle em
formação) → indicadores → scoring → cor/label. Cache com TTL por horizonte;
em falha da fonte, serve o último sinal conhecido (mesmo expirado) com
`data_age_seconds` honesto e `stale=True` (spec.md §6): fallback nunca finge
dado atual.

`last_updated` é o as-of do dado (timestamp do último candle fechado usado),
não a hora do cálculo — logo `data_age_seconds = now - last_updated` cresce
mesmo com o sinal em cache.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from data import cache as signal_cache
from data.provider import get_provider
from data.validation import data_age_seconds, is_stale, sanitize_candles
from indicators import engine as indicators_engine
from models.schemas import SignalScore
from strategy import scoring
from strategy.config import ASSETS

router = APIRouter(prefix="/signals", tags=["signals"])

HORIZONS = ("day_trade", "swing_trade", "hold")

# Granularidade ccxt por horizonte (arquitetura.md §2.1). BinanceProvider aceita
# timeframes ccxt direto; CoinGeckoProvider legado faz fallback.
HORIZON_SERIES: dict[str, tuple[str, int]] = {
    "day_trade": ("1h", 200),
    "swing_trade": ("1d", 365),
    "hold": ("1w", 200),
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
    raw = get_provider().get_ohlc(symbol, interval, limit)
    candles, _ = sanitize_candles(raw, timeframe=interval, drop_forming=True)
    if not candles:
        raise ValueError(f"sem candles fechados válidos para {symbol}/{horizon}")
    indicators = _COMPUTE[horizon](candles)
    score = scoring.compute_score(indicators, horizon)
    color, label = scoring.score_to_color_label(score)
    asof = candles[-1].timestamp
    if asof.tzinfo is None:
        asof = asof.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    signal = SignalScore(
        symbol=symbol,
        horizon=horizon,  # type: ignore[arg-type]
        score=score,
        color=color,  # type: ignore[arg-type]
        label=label,
        data_age_seconds=data_age_seconds(candles, now),
        last_updated=asof,
        stale=is_stale(candles, interval, now),
        candles_n=len(candles),
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
    """Recomputa a idade a partir do as-of do dado (não da hora do cache).

    Um sinal em cache envelhece de verdade; se passar de 2× o timeframe,
    passa a ser marcado `stale` mesmo tendo nascido fresco.
    """
    interval = HORIZON_SERIES[horizon][0]
    now = datetime.now(timezone.utc)
    asof = signal.last_updated
    if asof.tzinfo is None:
        asof = asof.replace(tzinfo=timezone.utc)
    signal.data_age_seconds = max(0, int((now - asof).total_seconds()))
    if _stale_age(signal, interval, now):
        signal.stale = True
    return signal


def _stale_age(signal: SignalScore, interval: str, now: datetime) -> bool:
    from data.validation import timeframe_seconds

    tf = timeframe_seconds(interval)
    if tf is None:
        return signal.stale
    return signal.data_age_seconds > tf * 2.0


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
            refreshed = _refresh_age(stale, horizon)
            refreshed.stale = True  # veio de fallback, não da fonte
            return refreshed
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
