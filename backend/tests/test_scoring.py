"""Motor de regras: testes unitários com indicadores mockados (sem rede) — spec.md §7."""

import pytest

from strategy import scoring
from strategy.config import WEIGHTS


def _uniform(horizon: str, value: float) -> dict[str, float]:
    return {name: value for name in WEIGHTS[horizon]}


@pytest.mark.parametrize("horizon", ["day_trade", "swing_trade", "hold"])
def test_score_alto_medio_baixo(horizon):
    assert scoring.compute_score(_uniform(horizon, 90), horizon) == 90
    assert scoring.compute_score(_uniform(horizon, 50), horizon) == 50
    assert scoring.compute_score(_uniform(horizon, 10), horizon) == 10


def test_score_ponderado_swing_trade():
    indicators = {"macd": 80.0, "ma_cross": 60.0, "rsi_daily": 50.0, "support_resistance": 40.0}
    # 0.3*80 + 0.3*60 + 0.2*50 + 0.2*40 = 60
    assert scoring.compute_score(indicators, "swing_trade") == 60


@pytest.mark.parametrize(
    "score,color,label",
    [
        (0, "red", "Fraco"),
        (20, "red", "Fraco"),
        (21, "orange", "Fraco+"),
        (40, "orange", "Fraco+"),
        (41, "yellow", "Neutro"),
        (60, "yellow", "Neutro"),
        (61, "light_green", "Bom"),
        (80, "light_green", "Bom"),
        (81, "green", "Forte"),
        (100, "green", "Forte"),
    ],
)
def test_faixas_cor_label(score, color, label):
    assert scoring.score_to_color_label(score) == (color, label)


def test_horizonte_desconhecido():
    with pytest.raises(ValueError):
        scoring.compute_score({"x": 50.0}, "intraday")


def test_indicadores_incompativeis():
    with pytest.raises(ValueError):
        scoring.compute_score({"macd": 50.0}, "swing_trade")


def test_indicador_fora_da_faixa():
    bad = _uniform("hold", 50)
    bad["long_trend"] = 101
    with pytest.raises(ValueError):
        scoring.compute_score(bad, "hold")


def test_score_fora_da_faixa():
    with pytest.raises(ValueError):
        scoring.score_to_color_label(101)
