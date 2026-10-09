"""Backtest engine + endpoints: métricas sãs e walk-forward — spec.md §7."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backtest.engine import _run_window, _window_metrics, run_backtest
from data import cache as signal_cache
from data.provider import StubProvider, set_provider
from models.schemas import Candle


def _candles(closes: list[float]) -> list[Candle]:
    now = datetime.now(timezone.utc)
    n = len(closes)
    return [
        Candle(
            timestamp=datetime.fromtimestamp(
                now.timestamp() - (n - 1 - i) * 86_400, tz=timezone.utc
            ),
            open=c - 1,
            high=c + 1,
            low=c - 2,
            close=c,
            volume=100.0,
        )
        for i, c in enumerate(closes)
    ]


def test_sem_lookahead_e_metricas_sas():
    closes = [100.0 + i * 0.5 + (i % 5) for i in range(120)]
    report = run_backtest(_candles(closes), "swing_trade")
    assert 0.0 <= report.win_rate <= 1.0
    assert report.max_drawdown <= 0.0
    assert report.trades >= 0
    assert report.windows == 3
    assert report.period_start <= report.period_end


def test_serie_vazia_e_horizonte_invalido():
    with pytest.raises(ValueError):
        run_backtest([], "swing_trade")
    with pytest.raises(ValueError):
        run_backtest(_candles([1.0, 2.0, 3.0, 4.0, 5.0, 6.0]), "intraday")


def test_queda_forte_nao_lucra():
    closes = [500.0 - i * 2 for i in range(120)]
    report = run_backtest(_candles(closes), "swing_trade")
    assert report.cumulative_return <= 0.0


# --- Curva de patrimônio com execução no fechamento ---
# Convenção: sinal gerado com dados até o close[i] é executado nesse mesmo
# close[i]. Logo a barra de entrada não rende (só participa de close[i+1] /
# close[i] em diante) e a barra de saída rende (estava posicionado em
# close[i-1] -> close[i]). equity tem len(n+1), equity[0] = 1.0.

BUY = 60.0
SELL = 40.0


def test_entrada_nao_carrega_variacao_anterior():
    # Compra no close[1] = 110: a alta 100 -> 110 NÃO é da posição.
    closes = [100.0, 110.0, 120.0]
    scores: list[float | None] = [0.0, 80.0, 80.0]
    trades, equity = _run_window(_candles(closes), scores, BUY, SELL)
    assert equity == pytest.approx([1.0, 1.0, 1.0, 120.0 / 110.0])
    assert len(trades) == 1
    assert (trades[0].entry_index, trades[0].exit_index) == (1, 2)
    assert trades[0].return_pct == pytest.approx(120.0 / 110.0 - 1.0)


def test_saida_inclui_ultima_variacao():
    # Compra no close[0] = 100, vende no close[2] = 132: a alta 110 -> 132 ENTRA.
    closes = [100.0, 110.0, 132.0]
    scores: list[float | None] = [80.0, 80.0, 10.0]
    trades, equity = _run_window(_candles(closes), scores, BUY, SELL)
    assert equity == pytest.approx([1.0, 1.0, 110.0 / 100.0, 132.0 / 100.0])
    assert len(trades) == 1
    assert trades[0].return_pct == pytest.approx(132.0 / 100.0 - 1.0)
    metrics = _window_metrics(trades, equity)
    assert metrics.cumulative_return == pytest.approx(equity[-1] - 1.0)


def test_equity_consistente_com_trades_e_drawdown():
    # Um trade 100 -> 120 -> 90 -> 135 com drawdown 90/120 - 1 = -25%.
    closes = [100.0, 120.0, 90.0, 135.0]
    scores: list[float | None] = [80.0, 80.0, 80.0, 10.0]
    trades, equity = _run_window(_candles(closes), scores, BUY, SELL)
    assert equity == pytest.approx([1.0, 1.0, 1.2, 0.9, 1.35])
    assert trades[0].return_pct == pytest.approx(135.0 / 100.0 - 1.0)
    metrics = _window_metrics(trades, equity)
    assert metrics.cumulative_return == pytest.approx(0.35)
    assert metrics.max_drawdown == pytest.approx(-0.25)


def test_score_none_mantem_exposicao():
    # Sem sinal na barra 1: continua posicionado e apropria 110 -> 121.
    closes = [100.0, 110.0, 121.0]
    scores: list[float | None] = [80.0, None, 10.0]
    trades, equity = _run_window(_candles(closes), scores, BUY, SELL)
    assert equity == pytest.approx([1.0, 1.0, 1.1, 1.21])
    assert trades[0].return_pct == pytest.approx(0.21)


def test_entrada_no_ultimo_candle_tem_retorno_zero():
    closes = [100.0, 110.0]
    scores: list[float | None] = [0.0, 80.0]
    trades, equity = _run_window(_candles(closes), scores, BUY, SELL)
    assert equity == pytest.approx([1.0, 1.0, 1.0])
    assert trades[0].return_pct == pytest.approx(0.0)


# --- Custos (fee + slippage): cálculo manual ---
# cost_bps one-way aplicado na entrada e na saída:
# retorno líquido = (exit/entry) * (1-c)^2 - 1; equity sofre o mesmo drag.


def test_custo_reduz_trade_e_equity():
    closes = [100.0, 110.0, 132.0]
    scores: list[float | None] = [80.0, 80.0, 10.0]
    cost_bps = 100.0  # 1% por lado -> (0.99)^2
    trades, equity = _run_window(_candles(closes), scores, BUY, SELL, cost_bps)
    fator = 0.99**2
    assert trades[0].gross_return_pct == pytest.approx(0.32)
    assert trades[0].return_pct == pytest.approx(1.32 * fator - 1.0)
    # equity: entrada paga 1% no close[0], saída paga 1% no close[2]
    assert equity == pytest.approx([1.0, 0.99, 0.99 * 1.1, 0.99 * 1.1 * 1.2 * 0.99])
    metrics = _window_metrics(trades, equity)
    assert metrics.cumulative_return == pytest.approx(equity[-1] - 1.0)
    assert metrics.cumulative_return < 0.32  # líquido < bruto


def test_custo_na_entrada_saida_forcada_no_mesmo_candle():
    closes = [100.0, 110.0]
    scores: list[float | None] = [0.0, 80.0]
    trades, equity = _run_window(_candles(closes), scores, BUY, SELL, 100.0)
    assert trades[0].return_pct == pytest.approx(0.99**2 - 1.0)
    assert equity == pytest.approx([1.0, 1.0, 0.99**2])


def test_custo_negativo_rejeitado():
    import pytest as _pt

    with _pt.raises(ValueError):
        _run_window(_candles([100.0, 110.0]), [80.0, 10.0], BUY, SELL, -5.0)


# --- Split desenvolvimento (IS) vs avaliação (OOS) + estabilidade ---


def test_split_is_oos_recomposto_no_total():
    closes = [100.0 + i * 0.5 + (i % 5) for i in range(120)]
    report = run_backtest(_candles(closes), "swing_trade", n_windows=4, test_windows=1, cost_bps=0.0)
    assert len(report.per_window_returns) == 4
    assert report.windows_positive == sum(1 for r in report.per_window_returns if r > 0)
    assert report.in_sample_trades + report.out_of_sample_trades == report.trades
    # (1+total) == (1+IS) * (1+OOS)
    assert (1 + report.cumulative_return) == pytest.approx(
        (1 + report.in_sample_return) * (1 + report.out_of_sample_return)
    )
    assert report.oos_period_start is not None and report.oos_period_end is not None
    assert report.oos_period_start <= report.oos_period_end
    assert report.assumptions  # nota metodológica presente


def test_oos_nao_usa_mesmos_dados_para_declarar_is():
    # Com test_windows=2 de 3, IS cobre 1 janela e OOS cobre 2: disjuntos por construção.
    closes = [100.0 + i * 0.5 + (i % 5) for i in range(120)]
    report = run_backtest(_candles(closes), "swing_trade", n_windows=3, test_windows=2, cost_bps=0.0)
    assert len(report.per_window_returns) == 3
    is_n, oos_n = 1, 2
    import math as _math

    assert report.in_sample_return == pytest.approx(
        _math.prod(1 + r for r in report.per_window_returns[:is_n]) - 1.0
    )
    assert report.out_of_sample_return == pytest.approx(
        _math.prod(1 + r for r in report.per_window_returns[is_n:]) - 1.0
    )
    assert oos_n == report.test_windows


def test_test_windows_invalido():
    import pytest as _pt

    candles = _candles([100.0 + i for i in range(30)])
    with _pt.raises(ValueError):
        run_backtest(candles, "swing_trade", n_windows=3, test_windows=3)
    with _pt.raises(ValueError):
        run_backtest(candles, "swing_trade", n_windows=1, test_windows=1)


@pytest.fixture()
def client():
    import api.backtest as backtest_module
    import main as main_module

    set_provider(StubProvider())
    for horizon_cache in signal_cache._caches.values():
        horizon_cache.clear()
    backtest_module._store.clear()
    return TestClient(main_module.app)


def test_api_run_get_roundtrip(client):
    created = client.post(
        "/backtest/run", json={"symbol": "BTC", "horizon": "swing_trade", "limit": 60}
    ).json()
    assert created["id"]
    assert created["result"]["strategy_name"] == "score-long-only:BTC:swing_trade"
    fetched = client.get(f"/backtest/{created['id']}").json()
    assert fetched == created["result"]


def test_api_validacoes(client):
    assert client.post("/backtest/run", json={"symbol": "XXX"}).status_code == 404
    assert client.post("/backtest/run", json={"horizon": "intraday"}).status_code == 404
    bad = client.post(
        "/backtest/run",
        json={"symbol": "BTC", "buy_threshold": 40, "sell_threshold": 60},
    )
    assert bad.status_code == 422
    assert client.get("/backtest/inexistente").status_code == 404
