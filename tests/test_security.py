import pytest
from fastapi import HTTPException

from axiomn.api.security import RateLimiter, require_api_key


def test_require_api_key_allows_through_when_unconfigured(monkeypatch):
    monkeypatch.delenv("AXIOMN_API_KEYS", raising=False)
    require_api_key(x_api_key=None)  # should not raise


def test_require_api_key_rejects_missing_key_when_configured(monkeypatch):
    monkeypatch.setenv("AXIOMN_API_KEYS", "secret123")
    with pytest.raises(HTTPException) as exc_info:
        require_api_key(x_api_key=None)
    assert exc_info.value.status_code == 401


def test_require_api_key_rejects_wrong_key_when_configured(monkeypatch):
    monkeypatch.setenv("AXIOMN_API_KEYS", "secret123")
    with pytest.raises(HTTPException) as exc_info:
        require_api_key(x_api_key="wrong")
    assert exc_info.value.status_code == 401


def test_require_api_key_accepts_correct_key(monkeypatch):
    monkeypatch.setenv("AXIOMN_API_KEYS", "secret123,other-key")
    require_api_key(x_api_key="other-key")  # should not raise


def test_rate_limiter_allows_up_to_the_configured_max():
    limiter = RateLimiter(max_requests=2, window_seconds=60.0)
    limiter.check("client-a")
    limiter.check("client-a")  # still within limit


def test_rate_limiter_blocks_beyond_the_configured_max():
    limiter = RateLimiter(max_requests=2, window_seconds=60.0)
    limiter.check("client-a")
    limiter.check("client-a")
    with pytest.raises(HTTPException) as exc_info:
        limiter.check("client-a")
    assert exc_info.value.status_code == 429


def test_rate_limiter_tracks_clients_independently():
    limiter = RateLimiter(max_requests=1, window_seconds=60.0)
    limiter.check("client-a")
    limiter.check("client-b")  # separate budget, should not raise


def test_rate_limiter_window_resets_after_the_window(monkeypatch):
    limiter = RateLimiter(max_requests=1, window_seconds=60.0)
    clock = iter([0.0, 61.0])
    monkeypatch.setattr("axiomn.api.security.time.time", lambda: next(clock))
    limiter.check("client-a")
    limiter.check("client-a")  # next window bucket: the counter reset, no raise


def test_rate_limiter_shares_state_through_the_store():
    # Two limiters on the same store enforce one shared limit — the property
    # that lets the limit hold across processes when the store is Redis.
    from axiomn.store import InMemoryStore

    store = InMemoryStore()
    a = RateLimiter(max_requests=1, window_seconds=60.0, store=store)
    b = RateLimiter(max_requests=1, window_seconds=60.0, store=store)
    a.check("client-a")
    with pytest.raises(HTTPException):
        b.check("client-a")  # b sees a's count via the shared store
