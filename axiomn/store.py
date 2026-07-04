"""Shared state, so AXIOMN survives more than one process.

The rate limiter and the intelligence budget need counters that are correct
across *every* instance serving traffic — otherwise two Fly machines each grant
a full budget and the guarantee leaks. This module is that seam: a tiny `Store`
of atomic, expiring counters, with an in-memory default (single process, zero
dependencies, unchanged behavior) and an optional Redis backend for horizontal
scale.

Opt-in and fail-open, like every AXIOMN edge: `build_store()` returns the
in-memory store unless `AXIOMN_REDIS_URL` is set, and a Redis that can't be
reached at startup falls back to in-memory rather than refusing to boot.

Not yet migrated here: the metrics collector and the Router's trust scores are
still per-process (documented in the README). This `Store` is the contract they
will adopt next; the pieces that gate spend move first because that's where a
per-process count actually costs money.
"""
from __future__ import annotations

import threading
import time
from typing import Optional, Protocol


class Store(Protocol):
    def incr(self, key: str, amount: float = 1.0, ttl_seconds: Optional[float] = None) -> float:
        """Atomically add `amount` to `key` and return the new total. When the
        key is first created (or has expired), `ttl_seconds` sets its lifetime."""
        ...

    def get(self, key: str) -> float:
        """Current value of `key`, or 0.0 if absent/expired."""
        ...


class InMemoryStore:
    """Thread-safe counters with per-key expiry. Correct within one process."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._values: dict[str, tuple[float, Optional[float]]] = {}  # key -> (value, expiry)

    def _live(self, key: str, now: float) -> Optional[float]:
        entry = self._values.get(key)
        if entry is None:
            return None
        value, expiry = entry
        if expiry is not None and now >= expiry:
            del self._values[key]
            return None
        return value

    def incr(self, key: str, amount: float = 1.0, ttl_seconds: Optional[float] = None) -> float:
        now = time.monotonic()
        with self._lock:
            current = self._live(key, now)
            if current is None:
                expiry = now + ttl_seconds if ttl_seconds is not None else None
                self._values[key] = (amount, expiry)
                return amount
            value, expiry = self._values[key][0] + amount, self._values[key][1]
            self._values[key] = (value, expiry)
            return value

    def get(self, key: str) -> float:
        with self._lock:
            return self._live(key, time.monotonic()) or 0.0


class RedisStore:
    """Counters shared across processes, backed by Redis. `client` is any object
    exposing `incrbyfloat`, `expire`, and `get` (the redis-py contract), so it
    can be injected with a fake in tests and never hard-imports redis."""

    def __init__(self, client: object) -> None:
        self._r = client

    def incr(self, key: str, amount: float = 1.0, ttl_seconds: Optional[float] = None) -> float:
        value = float(self._r.incrbyfloat(key, amount))  # type: ignore[attr-defined]
        # Set the expiry only when the key was just created (value == amount),
        # so a window's lifetime isn't extended by every hit inside it.
        if ttl_seconds is not None and value == amount:
            self._r.expire(key, int(ttl_seconds))  # type: ignore[attr-defined]
        return value

    def get(self, key: str) -> float:
        raw = self._r.get(key)  # type: ignore[attr-defined]
        return float(raw) if raw is not None else 0.0


def build_store(redis_url: Optional[str] = None) -> Store:
    """In-memory by default; Redis when `AXIOMN_REDIS_URL` is set and reachable.

    Fail-open: any problem importing or connecting to redis degrades to the
    in-memory store with a warning rather than crashing the runtime.
    """
    import os

    url = redis_url or os.environ.get("AXIOMN_REDIS_URL")
    if not url:
        return InMemoryStore()
    try:
        import redis

        client = redis.Redis.from_url(url, decode_responses=True)
        client.ping()
        return RedisStore(client)
    except Exception as exc:  # noqa: BLE001 — degrade, never fail to boot
        from .observability import logger

        logger.warning("store.redis_unavailable", extra={"error": str(exc)})
        return InMemoryStore()
