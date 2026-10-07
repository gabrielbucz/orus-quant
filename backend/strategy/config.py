"""Configuração central do motor de regras — fonte: spec.md §4.1/§4.2/§5.

Pesos ficam aqui (não espalhados no código) para recalibração via backtest.
"""

ASSETS: list[str] = ["BTC", "ETH", "SOL"]

# Pesos por horizonte; cada dict deve somar 1.0.
WEIGHTS: dict[str, dict[str, float]] = {
    "day_trade": {
        "rsi_short": 0.35,
        "vwap_distance": 0.35,
        "volume_spike": 0.30,
    },
    "swing_trade": {
        "macd": 0.30,
        "ma_cross": 0.30,
        "rsi_daily": 0.20,
        "support_resistance": 0.20,
    },
    "hold": {
        "long_trend": 0.50,
        "cycle_position": 0.30,
        "aggregates": 0.20,
    },
}

# TTL do cache por horizonte, em segundos (spec.md §5).
CACHE_TTL_SECONDS: dict[str, int] = {
    "day_trade": 120,
    "swing_trade": 900,
    "hold": 21600,
}

# Faixas score -> (cor, label), spec.md §4.3.
SCORE_BANDS: list[tuple[int, int, str, str]] = [
    (0, 20, "red", "Fraco"),
    (21, 40, "orange", "Fraco+"),
    (41, 60, "yellow", "Neutro"),
    (61, 80, "light_green", "Bom"),
    (81, 100, "green", "Forte"),
]
