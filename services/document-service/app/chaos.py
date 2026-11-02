"""Runtime feature/chaos flags backed by the tenant's Redis.

Flag reads are cached in-process for a short window so request handlers do not
pay a Redis round trip per call, and an unreachable Redis costs at most one
bounded connect attempt per flag per back-off window rather than stalling
every request. Flags read as off whenever Redis cannot be reached.

A flag only counts as active while its key carries an expiry. Every sanctioned
way of arming a flag (admin-service ``POST /api/v1/admin/chaos``,
``scripts/inject-bug.sh``, the incident harness) uses ``SETEX``; a key written
without a TTL would otherwise degrade the service until someone noticed, so it
is ignored and logged instead. The current state of each flag is exported as
``otterworks_chaos_flag_active`` so a latency page can be traced to its cause
from the dashboard without a Redis shell.
"""

import os
import time

import redis as redis_lib
import structlog

from app.telemetry import CHAOS_FLAG_ACTIVE, SERVICE

logger = structlog.get_logger()

_redis_client: redis_lib.Redis | None = None
_flag_cache: dict[str, tuple[float, bool]] = {}

FLAG_SLOW_QUERIES = "chaos:document-service:slow_queries"
FLAG_REQUEST_LOG = "chaos:document-service:request_log"
FLAG_RENDER_CACHE = "chaos:document-service:render_cache"

FLAG_CACHE_SECONDS = 2.0
FLAG_FAILURE_BACKOFF_SECONDS = 15.0
REDIS_TIMEOUT_SECONDS = 0.25

_PTTL_MISSING = -2
_PTTL_NO_EXPIRY = -1


def get_redis() -> redis_lib.Redis:
    """Return a shared Redis client (lazy-initialised)."""
    global _redis_client
    if _redis_client is None:
        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", "6379"))
        _redis_client = redis_lib.Redis(
            host=host,
            port=port,
            decode_responses=True,
            socket_timeout=REDIS_TIMEOUT_SECONDS,
            socket_connect_timeout=REDIS_TIMEOUT_SECONDS,
        )
    return _redis_client


def _read_flag(key: str) -> bool:
    """One Redis round trip: active only if the key exists *and* will expire."""
    ttl_ms = int(get_redis().pttl(key))
    if ttl_ms == _PTTL_MISSING:
        return False
    if ttl_ms == _PTTL_NO_EXPIRY:
        logger.warning("chaos_flag_without_expiry_ignored", flag=key)
        return False
    return True


def _record_state(key: str, active: bool, previous: bool | None) -> None:
    CHAOS_FLAG_ACTIVE.labels(SERVICE, key).set(1 if active else 0)
    if active and not previous:
        logger.warning("chaos_flag_active", flag=key)
    elif previous and not active:
        logger.info("chaos_flag_cleared", flag=key)


def flag_active(key: str) -> bool:
    """Return True if the given flag is set in Redis (cached; off when Redis is unreachable)."""
    now = time.monotonic()
    cached = _flag_cache.get(key)
    if cached is not None and cached[0] > now:
        return cached[1]
    try:
        active = _read_flag(key)
        ttl = FLAG_CACHE_SECONDS
    except Exception:
        active = False
        ttl = FLAG_FAILURE_BACKOFF_SECONDS
    _record_state(key, active, cached[1] if cached is not None else None)
    _flag_cache[key] = (now + ttl, active)
    return active
