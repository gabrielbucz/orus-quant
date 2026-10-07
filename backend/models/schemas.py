"""Schemas Pydantic da API — fonte: spec.md §2."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

Horizon = Literal["day_trade", "swing_trade", "hold"]
SignalColor = Literal["red", "orange", "yellow", "light_green", "green"]


class Candle(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class PriceSnapshot(BaseModel):
    symbol: str
    price: float
    timestamp: datetime


class SignalScore(BaseModel):
    symbol: str
    horizon: Horizon
    score: int = Field(ge=0, le=100)
    color: SignalColor
    label: str
    data_age_seconds: int = Field(ge=0)
    last_updated: datetime


class BacktestResult(BaseModel):
    strategy_name: str
    win_rate: float
    cumulative_return: float
    sharpe_ratio: float
    max_drawdown: float
    period_start: date
    period_end: date
