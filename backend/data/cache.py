"""Cache in-memory com TTL por horizonte — SDD §2.2 / spec.md §5."""

import time

from cachetools import TTLCache

from strategy.config import CACHE_TTL_SECONDS

_caches: dict[str, TTLCache] = {
    horizon: TTLCache(maxsize=256, ttl=ttl)
    for horizon, ttl in CACHE_TTL_SECONDS.items()
}

# Timestamp da última escrita por chave, para calcular data_age_seconds
# mesmo quando o valor vem do fallback (spec.md §6).
_last_write: dict[str, float] = {}


def _key(namespace: str, key: str) -> str:
    return f"{namespace}:{key}"


def cache_get(horizon: str, key: str):
    return _caches[horizon].get(key)


def cache_set(horizon: str, key: str, value, namespace: str = "signals") -> None:
    _caches[horizon][key] = value
    _last_write[_key(namespace, key)] = time.time()


def data_age_seconds(namespace: str, key: str, fallback: float = 0.0) -> int:
    ts = _last_write.get(_key(namespace, key))
    if ts is None:
        return int(fallback)
    return max(0, int(time.time() - ts))
