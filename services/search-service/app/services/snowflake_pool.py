"""A small lazy connection pool for Snowflake insights queries."""

from __future__ import annotations

import random
import threading
import time
from contextlib import contextmanager
from queue import Empty, LifoQueue
from typing import Any, Callable, Iterator


TRANSIENT_DATABASE_ERRNOS = frozenset(
    {
        250001,  # Snowflake connection failure
        250003,  # Snowflake request failed
        390114,  # Snowflake authentication token expired
    }
)


class PoolTimeout(TimeoutError):
    """No connection slot became available before the pool timeout."""


class QueryTimeout(TimeoutError):
    """Snowflake cancelled a statement because its execution timed out."""


class BackendUnavailable(RuntimeError):
    """The Snowflake backend could not complete a query after retries."""


def _connect_snowflake(params: dict[str, Any]):
    import snowflake.connector

    return snowflake.connector.connect(**params)


class SnowflakeConnectionPool:
    """Thread-safe bounded LIFO pool with lazy connection creation."""

    def __init__(
        self,
        connect_fn: Callable[[dict[str, Any]], Any] | None = None,
        size: int = 4,
        *,
        connection_params: dict[str, Any] | None = None,
        query_timeout: int = 15,
        max_retries: int = 3,
        backoff_base: float = 0.2,
        backoff_max: float = 2.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if size < 1:
            raise ValueError("pool size must be positive")
        self._connect_fn = connect_fn or _connect_snowflake
        self._connection_params = connection_params or {}
        self._size = size
        self.query_timeout = query_timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max
        self._sleep = sleep
        self._idle: LifoQueue[Any] = LifoQueue(maxsize=size)
        self._slots = threading.BoundedSemaphore(size)
        self._lock = threading.Lock()
        self._created = 0
        self._closed = False

    @contextmanager
    def acquire(self, timeout: float | None = None) -> Iterator[Any]:
        wait_timeout = self.query_timeout if timeout is None else timeout
        started = time.monotonic()
        if not self._slots.acquire(timeout=max(0.0, wait_timeout)):
            raise PoolTimeout("timed out waiting for a Snowflake connection")

        connection = None
        discard = False
        try:
            connection = self._get_connection(started, wait_timeout)
            try:
                yield connection
            except BaseException:
                discard = True
                raise
            finally:
                if connection is not None:
                    if discard or self._is_closed(connection) or self._closed:
                        self._discard(connection)
                    else:
                        self._idle.put(connection)
        finally:
            self._slots.release()

    def _get_connection(self, started: float, timeout: float) -> Any:
        while True:
            try:
                connection = self._idle.get_nowait()
            except Empty:
                connection = None
            if connection is not None:
                if self._is_closed(connection):
                    self._discard(connection)
                    continue
                return connection

            with self._lock:
                if self._closed:
                    raise BackendUnavailable("Snowflake connection pool is closed")
                if self._created < self._size:
                    self._created += 1
                    create = True
                else:
                    create = False
            if create:
                try:
                    connection = self._connect_fn(self._connection_params)
                except BaseException:
                    with self._lock:
                        self._created -= 1
                    raise
                if self._is_closed(connection):
                    self._discard(connection)
                    continue
                return connection

            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0:
                raise PoolTimeout("timed out waiting for a Snowflake connection")
            try:
                connection = self._idle.get(timeout=remaining)
            except Empty as exc:
                raise PoolTimeout("timed out waiting for a Snowflake connection") from exc
            if self._is_closed(connection):
                self._discard(connection)
                continue
            return connection

    @staticmethod
    def _is_closed(connection: Any) -> bool:
        try:
            return bool(connection.is_closed())
        except Exception:
            return True

    def _discard(self, connection: Any) -> None:
        try:
            connection.close()
        except Exception:
            pass
        with self._lock:
            self._created -= 1

    def close_all(self) -> None:
        with self._lock:
            self._closed = True
        while True:
            try:
                connection = self._idle.get_nowait()
            except Empty:
                break
            self._discard(connection)

    @staticmethod
    def _connector_errors():
        try:
            from snowflake.connector import errors

            return errors
        except ImportError:
            return None

    @classmethod
    def _is_transient(cls, error: Exception) -> bool:
        errors = cls._connector_errors()
        if errors is None:
            return False
        if isinstance(error, (errors.OperationalError, errors.InterfaceError)):
            return True
        return isinstance(error, errors.DatabaseError) and getattr(error, "errno", None) in TRANSIENT_DATABASE_ERRNOS

    @staticmethod
    def _is_statement_timeout(error: Exception) -> bool:
        code = getattr(error, "errno", None)
        return str(code) in {"604", "000604", "630", "000630"}

    def run_query(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        for attempt in range(self.max_retries + 1):
            try:
                with self.acquire(timeout=self.query_timeout) as connection:
                    cursor = connection.cursor()
                    try:
                        cursor.execute(sql, params, timeout=self.query_timeout)
                        records = cursor.fetchall()
                        columns = []
                        for column in cursor.description or []:
                            name = getattr(column, "name", None)
                            columns.append((name if name is not None else column[0]).lower())
                        return [
                            dict(record)
                            if isinstance(record, dict)
                            else dict(zip(columns, record))
                            for record in records
                        ]
                    finally:
                        cursor.close()
            except Exception as error:
                if self._is_statement_timeout(error):
                    raise QueryTimeout("Snowflake query timed out") from error
                if not self._is_transient(error):
                    raise
                if attempt >= self.max_retries:
                    raise BackendUnavailable("Snowflake backend remained unavailable") from error
                delay = min(self.backoff_max, self.backoff_base * (2**attempt)) * random.random()
                self._sleep(delay)
        raise BackendUnavailable("Snowflake backend remained unavailable")
