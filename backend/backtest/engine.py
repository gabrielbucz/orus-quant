"""Engine de backtesting long-only baseado em score — spec.md §7 / SDD §2.6.

Regra: com o score do horizonte em cada candle, compra quando
`score >= buy_threshold` e vende quando `score <= sell_threshold`
(posição 0/100% do capital, sem alavancagem, sem custo — v1).

Walk-forward: a série é dividida em `n_windows` janelas; as métricas são
calculadas por janela e agregadas (média de win rate/retorno, pior
drawdown, Sharpe sobre os retornos diários concatenados). Isso evita
validar numa única janela histórica (risco de overfitting, PRD §9).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from indicators import engine as indicators_engine
from models.schemas import Candle
from strategy import scoring

_COMPUTE = {
    "day_trade": indicators_engine.compute_day_trade,
    "swing_trade": indicators_engine.compute_swing_trade,
    "hold": indicators_engine.compute_hold,
}

MIN_HISTORY = 5  # candles mínimos antes do primeiro sinal


@dataclass
class Trade:
    entry_index: int
    exit_index: int
    entry_price: float
    exit_price: float

    @property
    def return_pct(self) -> float:
        return self.exit_price / self.entry_price - 1.0


@dataclass
class WindowMetrics:
    win_rate: float
    cumulative_return: float
    max_drawdown: float
    trades: int


def _scores(candles: list[Candle], horizon: str) -> list[float | None]:
    """Score por candle usando só dados até aquele ponto (sem look-ahead)."""
    compute = _COMPUTE[horizon]
    out: list[float | None] = []
    for i in range(len(candles)):
        if i + 1 < MIN_HISTORY:
            out.append(None)
            continue
        try:
            indicators = compute(candles[: i + 1])
        except ValueError:
            out.append(None)
            continue
        out.append(float(scoring.compute_score(indicators, horizon)))
    return out


def _run_window(
    candles: list[Candle],
    scores: list[float | None],
    buy_threshold: float,
    sell_threshold: float,
) -> tuple[list[Trade], list[float]]:
    """Roda a regra numa janela; devolve trades e curva de equity (base 1.0)."""
    closes = [c.close for c in candles]
    trades: list[Trade] = []
    equity = [1.0]
    position: tuple[int, float] | None = None  # (entry_index, entry_price)

    for i in range(len(candles)):
        score = scores[i]
        price = closes[i]
        if score is None:
            equity.append(equity[-1])
            continue
        if position is None and score >= buy_threshold:
            position = (i, price)
        elif position is not None and score <= sell_threshold:
            entry_index, entry_price = position
            trades.append(Trade(entry_index, i, entry_price, price))
            position = None
        # equity acompanha o preço enquanto posicionado
        if position is not None:
            equity.append(equity[-1] * (price / closes[i - 1] if i > 0 else 1.0))
        else:
            equity.append(equity[-1])

    if position is not None:  # fecha no último candle
        entry_index, entry_price = position
        trades.append(Trade(entry_index, len(candles) - 1, entry_price, closes[-1]))
    return trades, equity


def _window_metrics(trades: list[Trade], equity: list[float]) -> WindowMetrics:
    if trades:
        wins = sum(1 for t in trades if t.return_pct > 0)
        win_rate = wins / len(trades)
        cumulative = math.prod(1 + t.return_pct for t in trades) - 1.0
    else:
        win_rate, cumulative = 0.0, 0.0
    peak, max_dd = equity[0], 0.0
    for value in equity:
        peak = max(peak, value)
        if peak > 0:
            max_dd = min(max_dd, value / peak - 1.0)
    return WindowMetrics(win_rate, cumulative, max_dd, len(trades))


def _sharpe_from_equity(equity: list[float], periods_per_year: int = 365) -> float:
    if len(equity) < 3:
        return 0.0
    returns = [equity[i] / equity[i - 1] - 1.0 for i in range(1, len(equity))]
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    std = math.sqrt(var)
    if std == 0:
        return 0.0
    return mean / std * math.sqrt(periods_per_year)


@dataclass
class BacktestReport:
    strategy_name: str
    win_rate: float
    cumulative_return: float
    sharpe_ratio: float
    max_drawdown: float
    period_start: date
    period_end: date
    trades: int
    windows: int


def run_backtest(
    candles: list[Candle],
    horizon: str,
    strategy_name: str = "score-long-only",
    buy_threshold: float = 60.0,
    sell_threshold: float = 40.0,
    n_windows: int = 3,
) -> BacktestReport:
    if not candles:
        raise ValueError("sem candles")
    if horizon not in _COMPUTE:
        raise ValueError(f"horizonte desconhecido: {horizon}")
    if n_windows < 1:
        raise ValueError("n_windows >= 1")

    scores = _scores(candles, horizon)
    n = len(candles)
    chunk = max(MIN_HISTORY + 1, n // n_windows)

    all_trades: list[Trade] = []
    full_equity = [1.0]
    win_rates, cumrets, drawdowns = [], [], []
    for w in range(n_windows):
        start = w * chunk
        end = min(n, (w + 1) * chunk) if w < n_windows - 1 else n
        if end - start < MIN_HISTORY + 1:
            continue
        trades, equity = _run_window(
            candles[start:end], scores[start:end], buy_threshold, sell_threshold
        )
        metrics = _window_metrics(trades, equity)
        win_rates.append(metrics.win_rate)
        cumrets.append(metrics.cumulative_return)
        drawdowns.append(metrics.max_drawdown)
        all_trades.extend(trades)
        # concatena equity (rebaseada) para o Sharpe global
        base = full_equity[-1]
        full_equity.extend(v * base for v in equity[1:])

    return BacktestReport(
        strategy_name=strategy_name,
        win_rate=sum(win_rates) / len(win_rates) if win_rates else 0.0,
        cumulative_return=math.prod(1 + r for r in cumrets) - 1.0 if cumrets else 0.0,
        sharpe_ratio=_sharpe_from_equity(full_equity),
        max_drawdown=min(drawdowns) if drawdowns else 0.0,
        period_start=candles[0].timestamp.date(),
        period_end=candles[-1].timestamp.date(),
        trades=len(all_trades),
        windows=n_windows,
    )
