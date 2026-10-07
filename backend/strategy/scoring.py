"""Motor de regras: combina indicadores normalizados (0-100) em score 0-100.

Python puro, sem rede — testável isoladamente (RNF05).
Fórmula: score = Σ (peso_i × indicador_normalizado_i), spec.md §4.1.
"""

from .config import SCORE_BANDS, WEIGHTS


def compute_score(indicators: dict[str, float], horizon: str) -> int:
    """Calcula o score 0-100 para um horizonte a partir de indicadores 0-100."""
    if horizon not in WEIGHTS:
        raise ValueError(f"horizonte desconhecido: {horizon}")
    weights = WEIGHTS[horizon]
    if set(indicators) != set(weights):
        raise ValueError(
            f"indicadores incompatíveis com '{horizon}': "
            f"esperado {sorted(weights)}, recebido {sorted(indicators)}"
        )
    total = 0.0
    for name, weight in weights.items():
        value = indicators[name]
        if not 0 <= value <= 100:
            raise ValueError(f"indicador '{name}' fora de 0-100: {value}")
        total += weight * value
    return int(round(max(0, min(100, total))))


def score_to_color_label(score: int) -> tuple[str, str]:
    """Mapeia score 0-100 para (cor, label), spec.md §4.3."""
    if not 0 <= score <= 100:
        raise ValueError(f"score fora de 0-100: {score}")
    for low, high, color, label in SCORE_BANDS:
        if low <= score <= high:
            return color, label
    raise AssertionError(f"score sem faixa: {score}")  # pragma: no cover
