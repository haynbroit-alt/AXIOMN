"""API key auth and rate limiting for the AXIOMN API.

Both are opt-in and fail open by default: an unconfigured deployment (no
`AXIOMN_API_KEYS` set) behaves exactly as before, which is what keeps the
existing test suite and local `curl`/`/ui/` usage working without any
setup. Set `AXIOMN_API_KEYS` before exposing this outside your own
machine — without it, `/v1/intent` has no auth at all.

Adapted from PR #5, rebased onto the v1 API.
"""
import os
import time

from fastapi import Header, HTTPException, status

from ..store import Store, InMemoryStore


def _configured_api_keys() -> set[str]:
    raw = os.environ.get("AXIOMN_API_KEYS", "")
    return {key.strip() for key in raw.split(",") if key.strip()}


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    keys = _configured_api_keys()
    if not keys:
        return  # no keys configured: auth disabled (local/dev mode)
    if x_api_key not in keys:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")


class RateLimiter:
    """A fixed-window limiter, keyed per client, backed by a `Store`.

    With the default `InMemoryStore` it counts within one process (unchanged for
    single-instance deploys); pass a `RedisStore` and the limit is enforced
    across every instance. Fixed-window (one counter per client per time bucket,
    expiring after the window) rather than sliding — the correct, atomic shape
    for a shared counter.
    """

    def __init__(self, max_requests: int = 60, window_seconds: float = 60.0, store: Store | None = None):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._store = store or InMemoryStore()

    def check(self, client_id: str) -> None:
        bucket = int(time.time() // self.window_seconds)
        key = f"ratelimit:{client_id}:{bucket}"
        count = self._store.incr(key, 1.0, ttl_seconds=self.window_seconds)
        if count > self.max_requests:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")
