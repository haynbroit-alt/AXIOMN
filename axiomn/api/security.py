"""API key auth and rate limiting for the AXIOMN API.

Both are opt-in and fail open by default: an unconfigured deployment (no
`AXIOMN_API_KEYS` set) behaves exactly as before, which is what keeps the
existing test suite and local `curl`/`/ui/` usage working without any
setup. Set `AXIOMN_API_KEYS` before exposing this outside your own
machine — right now `/intent` has no auth at all, which is a real gap for
anything beyond local development.
"""
import os
import time
from collections import defaultdict, deque

from fastapi import Header, HTTPException, status


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
    """A simple in-memory sliding-window limiter, keyed per client."""

    def __init__(self, max_requests: int = 60, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)

    def check(self, client_id: str) -> None:
        now = time.monotonic()
        hits = self._hits[client_id]
        while hits and now - hits[0] > self.window_seconds:
            hits.popleft()
        if len(hits) >= self.max_requests:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")
        hits.append(now)
