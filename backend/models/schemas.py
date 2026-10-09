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
    # Idade REAL do dado: now - timestamp do último candle FECHADO usado.
    # Nunca zera por cache/fallback: dado antigo aparece como antigo.
    data_age_seconds: int = Field(ge=0)
    # Timestamp do último candle fechado que gerou o sinal (as-of do dado).
    last_updated: datetime
    # True quando a idade passa de 2× a duração do timeframe (fallback
    # defasado, fonte fora do ar): o sinal é o último conhecido, não atual.
    stale: bool = False
    # Nº de candles fechados válidos usados no cálculo.
    candles_n: int = Field(default=0, ge=0)


class BacktestResult(BaseModel):
    strategy_name: str
    win_rate: float
    cumulative_return: float
    sharpe_ratio: float
    max_drawdown: float
    period_start: date
    period_end: date
    # Custos e split desenvolvimento (IS) vs avaliação (OOS). O agregado
    # full-sample é otimista se houve ajuste nele: declare desempenho pelo OOS.
    cost_bps: float = 0.0
    test_windows: int = 0
    in_sample_return: float = 0.0
    out_of_sample_return: float = 0.0
    in_sample_sharpe: float = 0.0
    out_of_sample_sharpe: float = 0.0
    in_sample_max_drawdown: float = 0.0
    out_of_sample_max_drawdown: float = 0.0
    in_sample_trades: int = 0
    out_of_sample_trades: int = 0
    oos_period_start: date | None = None
    oos_period_end: date | None = None
    per_window_returns: list[float] = Field(default_factory=list)
    windows_positive: int = 0
    assumptions: str = ""
