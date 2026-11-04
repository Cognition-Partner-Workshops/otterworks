from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from snowflake.connector import errors

from app.config import SnowflakeConfig
from app.services.insights_repository import build_connection_params
from app.services.snowflake_pool import (
    BackendUnavailable,
    PoolTimeout,
    QueryTimeout,
    SnowflakeConnectionPool,
)


class FakeCursor:
    description = [("VALUE",)]

    def __init__(self, error=None):
        self.error = error
        self.sql = None
        self.parameters = None
        self.timeout = None
        self.closed = False

    def execute(self, sql, parameters, timeout):
        self.sql = sql
        self.parameters = parameters
        self.timeout = timeout
        if self.error:
            raise self.error

    def fetchall(self):
        return [(42,)]

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, error=None):
        self.cursor_instance = FakeCursor(error)
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def is_closed(self):
        return self.closed

    def close(self):
        self.closed = True


def test_retry_then_success_discards_failed_connection_and_jitters(monkeypatch):
    failed = FakeConnection(errors.OperationalError(msg="connection failed", errno=250001))
    succeeded = FakeConnection()
    connections = iter([failed, succeeded])
    delays = []
    monkeypatch.setattr("app.services.snowflake_pool.random.random", lambda: 0.5)
    pool = SnowflakeConnectionPool(
        connect_fn=lambda _params: next(connections),
        size=1,
        max_retries=2,
        backoff_base=0.2,
        backoff_max=2,
        sleep=delays.append,
    )

    assert pool.run_query("select 1", {"key": "value"}) == [{"value": 42}]
    assert failed.closed is True
    assert succeeded.cursor_instance.timeout == 15
    assert succeeded.cursor_instance.parameters == {"key": "value"}
    assert delays == [0.1]


def test_programming_error_is_not_retried():
    calls = []
    connection = FakeConnection(errors.ProgrammingError(msg="bad SQL", errno=1003))
    pool = SnowflakeConnectionPool(
        connect_fn=lambda _params: calls.append(True) or connection,
        size=1,
        sleep=lambda _delay: pytest.fail("non-transient error must not sleep"),
    )

    with pytest.raises(errors.ProgrammingError):
        pool.run_query("select broken")
    assert len(calls) == 1
    assert connection.closed is True


def test_retry_exhaustion_raises_backend_unavailable(monkeypatch):
    calls = []
    delays = []
    monkeypatch.setattr("app.services.snowflake_pool.random.random", lambda: 0.5)
    pool = SnowflakeConnectionPool(
        connect_fn=lambda _params: calls.append(True)
        or FakeConnection(errors.OperationalError(msg="connection failed", errno=250001)),
        size=1,
        max_retries=2,
        backoff_base=0.2,
        backoff_max=2,
        sleep=delays.append,
    )

    with pytest.raises(BackendUnavailable):
        pool.run_query("select 1")
    assert len(calls) == 3
    assert delays == [0.1, 0.2]


def test_statement_timeout_errno_is_not_retried():
    calls = []
    pool = SnowflakeConnectionPool(
        connect_fn=lambda _params: calls.append(True)
        or FakeConnection(errors.DatabaseError(msg="statement timed out", errno=604)),
        size=1,
        sleep=lambda _delay: pytest.fail("statement timeout must not retry"),
    )

    with pytest.raises(QueryTimeout):
        pool.run_query("select slow")
    assert len(calls) == 1


def test_pool_is_bounded_and_times_out_when_all_connections_are_checked_out():
    calls = []
    pool = SnowflakeConnectionPool(connect_fn=lambda _params: calls.append(True) or FakeConnection(), size=1)

    with pool.acquire(timeout=0.02):
        with pytest.raises(PoolTimeout):
            with pool.acquire(timeout=0.01):
                pass
    assert len(calls) == 1


def test_pool_never_creates_more_than_its_size():
    entered = threading.Event()
    release = threading.Event()
    calls = []

    def connect(_params):
        calls.append(True)
        return FakeConnection()

    pool = SnowflakeConnectionPool(connect_fn=connect, size=2)

    def hold_connection():
        with pool.acquire():
            entered.set()
            release.wait(timeout=1)

    with ThreadPoolExecutor(max_workers=3) as executor:
        first = executor.submit(hold_connection)
        assert entered.wait(timeout=1)
        second = executor.submit(hold_connection)
        third = executor.submit(hold_connection)
        release.set()
        first.result(timeout=1)
        second.result(timeout=1)
        third.result(timeout=1)
    assert len(calls) <= 2


def test_runtime_connection_params_are_attributed_and_keep_statement_timeout(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_HOST", "wrong-account.example")
    config = SnowflakeConfig(
        account="sf-account",
        private_key_file="/not-read/private-key.p8",
        deployed_commit="a" * 40,
        query_phase="runtime",
        query_timeout=17,
    )

    params = build_connection_params(config)
    tag_text = params["session_parameters"]["QUERY_TAG"]
    tag = json.loads(tag_text)

    assert params["user"] == "SFNFR_20261104_SVC_CS_DOC_SEARCH_API_TOP_ITEMS"
    assert params["authenticator"] == "SNOWFLAKE_JWT"
    assert params["application"] == "Devin_Demo"
    assert list(tag) == ["csid", "workload", "phase", "commit", "run_id"]
    assert tag["phase"] == "runtime"
    assert "session_url" not in tag
    assert params["session_parameters"]["STATEMENT_TIMEOUT_IN_SECONDS"] == 17
    assert "SNOWFLAKE_HOST" not in __import__("os").environ
