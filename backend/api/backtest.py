"""Endpoints de backtest — spec.md §3."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.signals import HORIZON_SERIES
from backtest.engine import run_backtest
from data.provider import get_provider
from models.schemas import BacktestResult
from strategy.config import ASSETS

router = APIRouter(prefix="/backtest", tags=["backtest"])

_store: dict[str, BacktestResult] = {}


class BacktestRequest(BaseModel):
    symbol: str = Field(default="BTC")
    horizon: str = Field(default="swing_trade")
    interval: str | None = None
    limit: int = Field(default=365, ge=10, le=1000)
    buy_threshold: float = Field(default=60.0, ge=0, le=100)
    sell_threshold: float = Field(default=40.0, ge=0, le=100)
    n_windows: int = Field(default=3, ge=1, le=12)


class BacktestCreated(BaseModel):
    id: str
    result: BacktestResult


@router.post("/run", response_model=BacktestCreated)
def run_backtest_endpoint(payload: BacktestRequest) -> BacktestCreated:
    symbol = payload.symbol.upper()
    if symbol not in ASSETS:
        raise HTTPException(status_code=404, detail=f"ativo desconhecido: {symbol}")
    if payload.horizon not in HORIZON_SERIES:
        raise HTTPException(status_code=404, detail=f"horizonte desconhecido: {payload.horizon}")
    if payload.sell_threshold >= payload.buy_threshold:
        raise HTTPException(
            status_code=422, detail="sell_threshold deve ser menor que buy_threshold"
        )
    default_interval = HORIZON_SERIES[payload.horizon][0]
    try:
        candles = get_provider().get_ohlc(
            symbol, payload.interval or default_interval, payload.limit
        )
        report = run_backtest(
            candles,
            payload.horizon,
            buy_threshold=payload.buy_threshold,
            sell_threshold=payload.sell_threshold,
            n_windows=payload.n_windows,
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"fonte de dados indisponível: {exc}") from exc
    result = BacktestResult(
        strategy_name=f"score-long-only:{symbol}:{payload.horizon}",
        win_rate=report.win_rate,
        cumulative_return=report.cumulative_return,
        sharpe_ratio=report.sharpe_ratio,
        max_drawdown=report.max_drawdown,
        period_start=report.period_start,
        period_end=report.period_end,
    )
    run_id = uuid.uuid4().hex[:12]
    _store[run_id] = result
    return BacktestCreated(id=run_id, result=result)


@router.get("/{run_id}", response_model=BacktestResult)
def get_backtest(run_id: str) -> BacktestResult:
    result = _store.get(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"backtest desconhecido: {run_id}")
    return result
