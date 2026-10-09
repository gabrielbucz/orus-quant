"""Engine de backtesting long-only baseado em score — spec.md §7 / SDD §2.6.

Regra: com o score do horizonte em cada candle, compra quando
`score >= buy_threshold` e vende quando `score <= sell_threshold`
(posição 0/100% do capital, sem alavancagem).

Convenção de execução: ordem executada no **fechamento** do candle em que
o sinal foi gerado (sem look-ahead). O retorno da barra de entrada NÃO
entra na curva; o da barra de saída ENTRA.

Escopo honesto (não é validação estatística completa): este backtest é
**exploratório**. Dividir em janelas e repetir os mesmos parâmetros NÃO
prova significância nem lucratividade futura. Para qualquer afirmação de
desempenho:

- ajuste pesos/limiares só no período de desenvolvimento (in-sample) e
  declare o desempenho no período reservado fora da amostra (out-of-sample,
  `test_windows` finais, intocados durante o ajuste);
- considere sempre os retornos **líquidos de custos** (`cost_bps` por lado,
  fee + slippage) — o padrão da API inclui estimativa;
- avalie a **estabilidade** (`per_window_returns`, `windows_positive`,
  Sharpe/retorno IS vs OOS): resultado concentrado numa janela ou que some
  no OOS não sustenta decisão real.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
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

#: Texto padrão de honestidade metodológica, reutilizado pela API/docs.
ASSUMPTIONS_NOTE = (
    "Backtest exploratório long-only, execução no fechamento, sem alavancagem. "
    "Retornos líquidos de custos estimados (fee+slippage por lado). "
    "Últimas janelas reservadas como out-of-sample: não ajuste parâmetros nelas. "
    "Walk-forward com mesmos parâmetros não é prova estatística nem garantia "
    "de lucro futuro — avalie estabilidade entre janelas/regimes."
)


@dataclass
class Trade:
    entry_index: int
    exit_index: int
    entry_price: float
    exit_price: float
    cost_bps: float = 0.0  # custo one-way (fee + slippage) em basis points

    @property
    def return_pct(self) -> float:
        """Retorno **líquido** do trade: (exit/entry) * (1-c)^2 - 1."""
        if self.entry_price == 0:
            return -1.0
        rate = self.cost_bps / 10_000.0
        gross = self.exit_price / self.entry_price
        return gross * (1.0 - rate) ** 2 - 1.0

    @property
    def gross_return_pct(self) -> float:
        if self.entry_price == 0:
            return -1.0
        return self.exit_price / self.entry_price - 1.0


@dataclass
class WindowMetrics:
    win_rate: float
    cumulative_return: float  # líquido de custos
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
    cost_bps: float = 0.0,
) -> tuple[list[Trade], list[float]]:
    """Roda a regra numa janela; devolve trades e curva de equity (base 1.0).

    Custos: `cost_bps` one-way aplicado na entrada e na saída
    (`equity *= (1 - c)` em cada ponta). `Trade.return_pct` já é líquido,
    de modo que `equity[-1] - 1` coincide com o produto dos retornos dos
    trades da janela.
    """
    if cost_bps < 0:
        raise ValueError("cost_bps >= 0")
    closes = [c.close for c in candles]
    trades: list[Trade] = []
    equity = [1.0]
    rate = cost_bps / 10_000.0
    position: tuple[int, float] | None = None  # (entry_index, entry_price)

    for i in range(len(candles)):
        price = closes[i]
        # 1) Apropria a variação close[i-1] -> close[i] se estava posicionado
        # no fechamento anterior (a decisão de i só vale para a próxima barra).
        if i == 0 or position is None:
            equity.append(equity[-1])
        else:
            prev = closes[i - 1]
            equity.append(equity[-1] * (price / prev) if prev else equity[-1])
        # 2) Avalia o sinal do fechamento i e executa a mercado nesse close.
        score = scores[i]
        if score is None:
            # Sem sinal: mantém exposição atual (se posicionado, continua
            # apropriando o mercado nas próximas barras).
            continue
        if position is None and score >= buy_threshold:
            position = (i, price)
            if rate:
                equity[-1] *= 1.0 - rate  # custo de entrada
        elif position is not None and score <= sell_threshold:
            entry_index, entry_price = position
            if rate:
                equity[-1] *= 1.0 - rate  # custo de saída
            trades.append(Trade(entry_index, i, entry_price, price, cost_bps))
            position = None

    if position is not None:  # fecha no último candle
        entry_index, entry_price = position
        if rate:
            equity[-1] *= 1.0 - rate  # custo de saída forçada
        trades.append(Trade(entry_index, len(candles) - 1, entry_price, closes[-1], cost_bps))
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


def _concat_equity(equities: list[list[float]]) -> list[float]:
    """Concatena curvas por janela rebaseando (para Sharpe do subconjunto)."""
    full = [1.0]
    for equity in equities:
        base = full[-1]
        full.extend(v * base for v in equity[1:])
    return full


@dataclass
class BacktestReport:
    strategy_name: str
    win_rate: float
    cumulative_return: float  # full-sample líquido (otimista se houve ajuste nele)
    sharpe_ratio: float  # full-sample
    max_drawdown: float  # pior janela (full-sample)
    period_start: date
    period_end: date
    trades: int
    windows: int
    # --- Separação desenvolvimento (IS) vs avaliação (OOS) ---
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
    # --- Estabilidade entre janelas/regimes ---
    per_window_returns: list[float] = field(default_factory=list)
    windows_positive: int = 0
    assumptions: str = ASSUMPTIONS_NOTE


def run_backtest(
    candles: list[Candle],
    horizon: str,
    strategy_name: str = "score-long-only",
    buy_threshold: float = 60.0,
    sell_threshold: float = 40.0,
    n_windows: int = 3,
    test_windows: int = 1,
    cost_bps: float = 10.0,
) -> BacktestReport:
    """Roda o backtest com split desenvolvimento vs avaliação.

    - As primeiras `n_windows - test_windows` janelas são o período de
      **desenvolvimento (in-sample)**: único lugar onde se pode comparar
      limiares/pesos.
    - As últimas `test_windows` janelas são a **avaliação fora da amostra
      (out-of-sample)**: reservadas, intocadas no ajuste; é nelas que se
      declara o desempenho final.
    - `cost_bps` (one-way, fee + slippage) é aplicado em todas as janelas.
    - `per_window_returns` / `windows_positive` expõem a estabilidade: lucro
      concentrado numa janela ou OOS negativo invalida leitura otimista do
      agregado full-sample.
    """
    if not candles:
        raise ValueError("sem candles")
    if horizon not in _COMPUTE:
        raise ValueError(f"horizonte desconhecido: {horizon}")
    if n_windows < 1:
        raise ValueError("n_windows >= 1")
    if not 0 <= test_windows < n_windows:
        raise ValueError("exigido 0 <= test_windows < n_windows")
    if cost_bps < 0:
        raise ValueError("cost_bps >= 0")

    # Fronteira de dados: ordena, deduplica e descarta OHLC inválido antes de
    # qualquer cálculo (indicador sobre dado errado continua errado).
    # Sem corte de forming aqui: a série histórica recebida já é o universo
    # de análise (o corte de forming vale para o sinal ao vivo).
    from data.validation import sanitize_candles

    candles, _ = sanitize_candles(candles, timeframe=None, drop_forming=False)
    if not candles:
        raise ValueError("sem candles válidos")

    scores = _scores(candles, horizon)
    n = len(candles)
    chunk = max(MIN_HISTORY + 1, n // n_windows)

    window_slices: list[tuple[int, int]] = []
    window_trades: list[list[Trade]] = []
    window_equities: list[list[float]] = []
    window_metrics: list[WindowMetrics] = []
    full_equity = [1.0]
    win_rates, cumrets, drawdowns = [], [], []
    for w in range(n_windows):
        start = w * chunk
        end = min(n, (w + 1) * chunk) if w < n_windows - 1 else n
        if end - start < MIN_HISTORY + 1:
            continue
        trades, equity = _run_window(
            candles[start:end], scores[start:end], buy_threshold, sell_threshold, cost_bps
        )
        metrics = _window_metrics(trades, equity)
        window_slices.append((start, end))
        window_trades.append(trades)
        window_equities.append(equity)
        window_metrics.append(metrics)
        win_rates.append(metrics.win_rate)
        cumrets.append(metrics.cumulative_return)
        drawdowns.append(metrics.max_drawdown)
        # concatena equity (rebaseada) para o Sharpe global
        base = full_equity[-1]
        full_equity.extend(v * base for v in equity[1:])

    evaluated = len(window_metrics)
    n_oos = min(test_windows, evaluated)
    n_is = evaluated - n_oos
    is_cumrets = cumrets[:n_is]
    oos_cumrets = cumrets[n_is:]
    is_equities = window_equities[:n_is]
    oos_equities = window_equities[n_is:]
    is_trades = sum(len(t) for t in window_trades[:n_is])
    oos_trades = sum(len(t) for t in window_trades[n_is:])

    def _prod(rs: list[float]) -> float:
        return math.prod(1 + r for r in rs) - 1.0 if rs else 0.0

    is_equity = _concat_equity(is_equities)
    oos_equity = _concat_equity(oos_equities)
    oos_start: date | None = None
    oos_end: date | None = None
    if n_oos and window_slices:
        oos_start = candles[window_slices[n_is][0]].timestamp.date()
        oos_end = candles[window_slices[-1][1] - 1].timestamp.date()

    return BacktestReport(
        strategy_name=strategy_name,
        win_rate=sum(win_rates) / len(win_rates) if win_rates else 0.0,
        cumulative_return=_prod(cumrets),
        sharpe_ratio=_sharpe_from_equity(full_equity),
        max_drawdown=min(drawdowns) if drawdowns else 0.0,
        period_start=candles[0].timestamp.date(),
        period_end=candles[-1].timestamp.date(),
        trades=sum(len(t) for t in window_trades),
        windows=n_windows,
        cost_bps=cost_bps,
        test_windows=test_windows,
        in_sample_return=_prod(is_cumrets),
        out_of_sample_return=_prod(oos_cumrets),
        in_sample_sharpe=_sharpe_from_equity(is_equity),
        out_of_sample_sharpe=_sharpe_from_equity(oos_equity),
        in_sample_max_drawdown=min(
            (m.max_drawdown for m in window_metrics[:n_is]), default=0.0
        ),
        out_of_sample_max_drawdown=min(
            (m.max_drawdown for m in window_metrics[n_is:]), default=0.0
        ),
        in_sample_trades=is_trades,
        out_of_sample_trades=oos_trades,
        oos_period_start=oos_start,
        oos_period_end=oos_end,
        per_window_returns=list(cumrets),
        windows_positive=sum(1 for r in cumrets if r > 0),
        assumptions=ASSUMPTIONS_NOTE,
    )
