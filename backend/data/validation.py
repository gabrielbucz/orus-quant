"""Validação e saneamento de candles — dados incorretos invalidam qualquer
indicador, por melhor que seja o cálculo.

Garante, na fronteira de entrada (providers, sinais, backtest):

- ordenação por timestamp (ordena estável quando vier fora de ordem);
- sem duplicatas (mesmo timestamp → vale o último recebido);
- OHLCV válidos (finitos, preços > 0, volume >= 0, high/low consistentes);
- candle em formação excluído do cálculo (só candles fechados alimentam
  indicadores — o último candle da exchange em geral ainda está formando);
- idade real do dado (`now - último candle fechado`) e flag `stale`, para que
  fallback nunca apresente dado antigo como se fosse atual.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone

TIMEFRAME_SECONDS: dict[str, int] = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14_400,
    "1d": 86_400,
    "1w": 604_800,
}

# Tolerância relativa para consistência high/low (arredondamento das fontes).
_TOL = 1e-9


@dataclass
class SanitizeReport:
    kept: int = 0
    dropped_duplicates: int = 0
    dropped_invalid: int = 0
    dropped_forming: int = 0
    was_out_of_order: bool = False


def timeframe_seconds(timeframe: str | None) -> int | None:
    if timeframe is None:
        return None
    return TIMEFRAME_SECONDS.get(timeframe)


def is_valid_ohlc(candle) -> bool:
    """OHLCV numericamente válido e internamente consistente."""
    try:
        o, h, low, close, vol = (
            candle.open,
            candle.high,
            candle.low,
            candle.close,
            candle.volume,
        )
    except AttributeError:
        return False
    for v in (o, h, low, close, vol):
        if not isinstance(v, (int, float)) or not math.isfinite(v):
            return False
    if o <= 0 or h <= 0 or low <= 0 or close <= 0:
        return False
    if vol < 0:
        return False
    if h < low:
        return False
    ref_high = max(o, close)
    ref_low = min(o, close)
    if h + abs(h) * _TOL < ref_high:
        return False
    if low - abs(low) * _TOL > ref_low:
        return False
    return True


def _as_aware(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts


def is_forming(timestamp: datetime, timeframe: str, now: datetime) -> bool:
    """Candle ainda em formação: `open_time + duração > now`.

    Timestamps de exchange (ccxt/OHLCV) são tempos de *abertura* do candle.
    """
    tf = timeframe_seconds(timeframe)
    if tf is None:
        return False
    ts = _as_aware(timestamp)
    now = _as_aware(now)
    return (ts.timestamp() + tf) > now.timestamp()


def sanitize_candles(
    candles: list,
    timeframe: str | None = None,
    now: datetime | None = None,
    drop_forming: bool = True,
) -> tuple[list, SanitizeReport]:
    """Ordena, deduplica (último vence), valida e remove candle em formação.

    `timeframe` nos formatos ccxt (`1h`, `1d`, …); com `None` pula a detecção
    de forming (ex.: granularidade desconhecida ou série histórica pronta).
    Não levanta erro: relata tudo em `SanitizeReport`; lista vazia se nada
    prestar (o chamador decide — sinal vira 502, backtest vira ValueError).
    """
    report = SanitizeReport()
    items = list(candles)
    if not items:
        return [], report

    ordered = sorted(items, key=lambda c: _as_aware(c.timestamp))
    report.was_out_of_order = [c.timestamp for c in ordered] != [c.timestamp for c in items]

    deduped: list = []
    for c in ordered:
        if deduped and _as_aware(deduped[-1].timestamp) == _as_aware(c.timestamp):
            deduped[-1] = c  # duplicata: vale o último recebido
            report.dropped_duplicates += 1
        else:
            deduped.append(c)

    valid = []
    for c in deduped:
        if is_valid_ohlc(c):
            valid.append(c)
        else:
            report.dropped_invalid += 1

    if drop_forming and timeframe is not None and valid:
        ref = now or datetime.now(timezone.utc)
        if is_forming(valid[-1].timestamp, timeframe, ref):
            valid.pop()
            report.dropped_forming += 1

    report.kept = len(valid)
    return valid, report


def data_age_seconds(candles: list, now: datetime | None = None) -> int:
    """Idade real do dado: `now - timestamp do último candle (fechado)`."""
    if not candles:
        return 0
    ref = _as_aware(now) if now else datetime.now(timezone.utc)
    last = _as_aware(candles[-1].timestamp)
    return max(0, int((ref - last).total_seconds()))


def is_stale(
    candles: list,
    timeframe: str | None,
    now: datetime | None = None,
    max_age_mult: float = 2.0,
) -> bool:
    """Defasado se a idade passa de `max_age_mult × duração do timeframe`.

    Sem timeframe conhecido, qualquer série vazia é stale; série não vazia
    sem referência não tem como julgar → não stale (o chamador exibe a idade).
    """
    if not candles:
        return True
    tf = timeframe_seconds(timeframe)
    if tf is None:
        return False
    return data_age_seconds(candles, now) > tf * max_age_mult
