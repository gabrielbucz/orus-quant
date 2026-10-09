"""Indicadores técnicos em Python puro (sem rede, sem pandas) — SDD §2.3.

Toda função recebe `closes`/`candles` e devolve float 0–100, pronto para o
motor de regras (`strategy/scoring.py`). Séries curtas degradam com
grace (janelas encurtadas), nunca quebram — exceto lista vazia.
"""

from __future__ import annotations

from models.schemas import Candle


def closes_of(candles: list[Candle]) -> list[float]:
    return [c.close for c in candles]


def volumes_of(candles: list[Candle]) -> list[float]:
    return [c.volume for c in candles]


def clamp01_100(value: float) -> float:
    return max(0.0, min(100.0, value))


def sma(values: list[float], period: int) -> float:
    if not values:
        raise ValueError("série vazia")
    window = values[-max(1, min(period, len(values))):]
    return sum(window) / len(window)


def ema(values: list[float], period: int) -> float:
    """EMA com seed na SMA dos primeiros `period` pontos."""
    if not values:
        raise ValueError("série vazia")
    period = max(1, min(period, len(values)))
    seed = values[:period]
    avg = sum(seed) / len(seed)
    multiplier = 2.0 / (period + 1)
    for price in values[period:]:
        avg = (price - avg) * multiplier + avg
    return avg


def rsi(closes: list[float], period: int = 14) -> float:
    """RSI de Wilder (0–100) com smoothing sobre toda a série. Sem movimento → 50."""
    if len(closes) < 2:
        return 50.0
    period = max(1, min(period, len(closes) - 1))
    deltas = [curr - prev for prev, curr in zip(closes[:-1], closes[1:])]
    gains = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for g, loss in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_gain == 0 and avg_loss == 0:
        return 50.0
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def atr(candles: list[Candle], period: int = 14) -> float:
    """Average True Range simplificado (sem smoothing Wilder completo)."""
    if not candles:
        raise ValueError("série vazia")
    period = max(1, min(period, len(candles)))
    window = candles[-period:]
    total, prev_close = 0.0, window[0].close
    for c in window:
        total += max(c.high - c.low, abs(c.high - prev_close), abs(c.low - prev_close))
        prev_close = c.close
    return total / len(window)


def vwap(candles: list[Candle]) -> float:
    """VWAP por preço típico × volume. Sem volume (ex: OHLC sem volume) → SMA(20)."""
    if not candles:
        raise ValueError("série vazia")
    window = candles[-20:]
    num = sum(((c.high + c.low + c.close) / 3.0) * c.volume for c in window)
    den = sum(c.volume for c in window)
    if den <= 0:
        return sma([c.close for c in window], len(window))
    return num / den


def distance_score(last: float, ref: float, pct_for_full_scale: float = 5.0) -> float:
    """Mapeia distância % (last vs ref) em 0–100 centrado em 50."""
    if ref <= 0:
        return 50.0
    pct = (last - ref) / ref * 100.0
    return clamp01_100(50.0 + pct / pct_for_full_scale * 50.0)


def volume_spike_score(volumes: list[float], period: int = 20) -> float:
    """Compara o último volume com a média. Sem dados de volume → 50."""
    if not volumes:
        return 50.0
    window = volumes[-max(1, min(period, len(volumes))):-1] or volumes[-1:]
    avg = sum(window) / len(window)
    if avg <= 0:
        return 50.0
    return clamp01_100(50.0 + (volumes[-1] / avg - 1.0) * 50.0)


def macd_score(closes: list[float]) -> float:
    """Normaliza o histograma MACD(12,26,9) pelo ATR relativo ao preço."""
    if len(closes) < 2:
        return 50.0
    macd_line = ema(closes, 12) - ema(closes, 26)
    # Linha de sinal aproximada: EMA(9) da série de MACD reconstruída
    seed_len = min(9, len(closes))
    macd_series = [ema(closes[: len(closes) - seed_len + 1 + i], 12) - ema(closes[: len(closes) - seed_len + 1 + i], 26) for i in range(seed_len)]
    signal = ema(macd_series, min(9, len(macd_series)))
    hist = macd_line - signal
    denom = max(abs(closes[-1]) * 0.005, 1e-9)
    return clamp01_100(50.0 + hist / denom * 50.0)


def ma_cross_score(closes: list[float], fast: int = 50, slow: int = 200) -> float:
    """Cruzamento de médias: fast vs slow em % mapeado para 0–100."""
    if not closes:
        raise ValueError("série vazia")
    fast_ma = sma(closes, min(fast, len(closes)))
    slow_ma = sma(closes, min(slow, len(closes)))
    return distance_score(fast_ma, slow_ma, pct_for_full_scale=2.5)


def range_position_score(closes: list[float], period: int = 50) -> float:
    """Posição do último close dentro da máxima/mínima recente (0–100)."""
    if not closes:
        raise ValueError("série vazia")
    window = closes[-max(1, min(period, len(closes))):]
    high, low = max(window), min(window)
    if high == low:
        return 50.0
    return clamp01_100((closes[-1] - low) / (high - low) * 100.0)
