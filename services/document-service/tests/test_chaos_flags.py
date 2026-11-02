"""Chaos flag reads are cached and fail closed when Redis is unreachable."""

import pytest
import redis as redis_lib

from app import chaos
from app.telemetry import CHAOS_FLAG_ACTIVE, SERVICE


class _CountingRedis:
    """Fake Redis answering PTTL: -2 missing, -1 no expiry, else ms remaining."""

    def __init__(self, active: bool, ttl_ms: int = 600_000) -> None:
        self.active = active
        self.ttl_ms = ttl_ms
        self.calls = 0

    def pttl(self, key: str) -> int:
        self.calls += 1
        return self.ttl_ms if self.active else -2


class _DownRedis:
    calls = 0

    def pttl(self, key: str) -> int:
        self.calls += 1
        raise redis_lib.ConnectionError("connection refused")


def _gauge(key: str) -> float:
    return CHAOS_FLAG_ACTIVE.labels(SERVICE, key)._value.get()


@pytest.fixture(autouse=True)
def clear_flag_cache() -> None:
    chaos._flag_cache.clear()


def test_flag_read_is_cached_within_window(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _CountingRedis(active=True)
    monkeypatch.setattr(chaos, "get_redis", lambda: fake)
    now = 1000.0
    monkeypatch.setattr(chaos.time, "monotonic", lambda: now)

    assert chaos.flag_active("k") is True
    assert chaos.flag_active("k") is True
    assert fake.calls == 1

    now += chaos.FLAG_CACHE_SECONDS + 0.01
    fake.active = False
    assert chaos.flag_active("k") is False
    assert fake.calls == 2


def test_unreachable_redis_reads_off_and_backs_off(monkeypatch: pytest.MonkeyPatch) -> None:
    down = _DownRedis()
    monkeypatch.setattr(chaos, "get_redis", lambda: down)
    now = 1000.0
    monkeypatch.setattr(chaos.time, "monotonic", lambda: now)

    assert chaos.flag_active("k") is False
    for _ in range(50):
        assert chaos.flag_active("k") is False
    assert down.calls == 1

    now += chaos.FLAG_FAILURE_BACKOFF_SECONDS + 0.01
    assert chaos.flag_active("k") is False
    assert down.calls == 2


def test_redis_client_uses_bounded_timeouts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chaos, "_redis_client", None)
    client = chaos.get_redis()
    kwargs = client.connection_pool.connection_kwargs
    assert kwargs["socket_timeout"] == chaos.REDIS_TIMEOUT_SECONDS
    assert kwargs["socket_connect_timeout"] == chaos.REDIS_TIMEOUT_SECONDS
    assert chaos.REDIS_TIMEOUT_SECONDS < 1


def test_flag_without_expiry_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    """A key written with SET instead of SETEX must not degrade the service indefinitely."""
    forever = _CountingRedis(active=True, ttl_ms=-1)
    monkeypatch.setattr(chaos, "get_redis", lambda: forever)

    assert chaos.flag_active("chaos:document-service:slow_queries") is False
    assert forever.calls == 1
    assert _gauge("chaos:document-service:slow_queries") == 0


def test_flag_state_is_exported_as_a_gauge(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _CountingRedis(active=True)
    monkeypatch.setattr(chaos, "get_redis", lambda: fake)
    now = 1000.0
    monkeypatch.setattr(chaos.time, "monotonic", lambda: now)

    assert chaos.flag_active("gauge-flag") is True
    assert _gauge("gauge-flag") == 1

    now += chaos.FLAG_CACHE_SECONDS + 0.01
    fake.active = False
    assert chaos.flag_active("gauge-flag") is False
    assert _gauge("gauge-flag") == 0
