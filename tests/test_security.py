import pytest

from axiomn.api.security import RateLimiter, require_api_key
from fastapi import HTTPException


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
