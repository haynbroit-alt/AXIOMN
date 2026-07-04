"""Shared state: atomic, expiring counters. In-memory by default; the same
contract a Redis backend fulfills so limits hold across processes.
"""
from axiomn.store import InMemoryStore, RedisStore, build_store


def test_in_memory_incr_and_get():
    s = InMemoryStore()
    assert s.get("k") == 0.0
    assert s.incr("k", 2.0) == 2.0
    assert s.incr("k", 3.0) == 5.0
    assert s.get("k") == 5.0


def test_in_memory_expiry(monkeypatch):
    s = InMemoryStore()
    clock = [1000.0]
    monkeypatch.setattr("axiomn.store.time.monotonic", lambda: clock[0])
    s.incr("k", 1.0, ttl_seconds=60.0)
    clock[0] = 1059.0
    assert s.get("k") == 1.0  # still inside the window
    clock[0] = 1061.0
    assert s.get("k") == 0.0  # expired -> reset


class _FakeRedis:
    """Minimal redis-py surface backed by a dict, for testing RedisStore."""

    def __init__(self):
        self.data: dict[str, float] = {}
        self.ttls: dict[str, int] = {}

    def incrbyfloat(self, key, amount):
        self.data[key] = self.data.get(key, 0.0) + amount
        return self.data[key]

    def expire(self, key, ttl):
        self.ttls[key] = ttl

    def get(self, key):
        return self.data.get(key)


def test_redis_store_uses_the_client_and_sets_ttl_once():
    fake = _FakeRedis()
    s = RedisStore(fake)
    assert s.incr("k", 1.0, ttl_seconds=60) == 1.0
    assert fake.ttls["k"] == 60  # ttl set on creation
    fake.ttls.clear()
    assert s.incr("k", 1.0, ttl_seconds=60) == 2.0
    assert "k" not in fake.ttls  # not re-set on later hits
    assert s.get("k") == 2.0
    assert s.get("missing") == 0.0


def test_build_store_is_in_memory_without_redis(monkeypatch):
    monkeypatch.delenv("AXIOMN_REDIS_URL", raising=False)
    assert isinstance(build_store(), InMemoryStore)
