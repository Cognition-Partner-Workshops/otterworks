"""Bounded, attributed Snowflake access for search insights."""

import atexit
import os
import random
import threading
import time
from contextlib import contextmanager

import sf_attribution as sf
import snowflake.connector
import structlog
from requests.exceptions import ConnectionError as RequestsConnectionError
from cryptography.hazmat.primitives import serialization
from snowflake.connector.errors import InterfaceError, OperationalError, ProgrammingError

EP = sf.endpoint("cs_doc_search_api_top_items")
logger = structlog.get_logger()
COLUMNS = (
    "window_end_date", "window_days", "account_id", "item_type", "rank", "term",
    "document_id", "document_title", "search_count", "zero_result_count", "last_searched_at",
)


class InsightsUnavailable(Exception):
    pass


class InsightsTimeout(Exception):
    pass


def is_timeout(exc):
    return isinstance(exc, TimeoutError) or getattr(exc, "errno", None) in (604, 605)


def transient(exc):
    if isinstance(exc, ProgrammingError):
        return False
    status = getattr(exc, "status_code", None)
    return isinstance(exc, (OperationalError, InterfaceError, ConnectionError, RequestsConnectionError)) or (
        isinstance(status, int) and (status == 429 or 500 <= status < 600)
    )


class InsightsClient:
    def __init__(self, config, *, private_key=None, connector=None, sleep=time.sleep):
        self.config = config
        self.private_key = private_key
        self.connector = connector or snowflake.connector.connect
        self.sleep = sleep
        self.condition = threading.Condition()
        self.idle = []
        self.count = 0
        self.closed = False
        atexit.register(self.close)

    def _connect(self):
        if self.config.user is not None and self.config.user != EP.service_user:
            logger.error("insights_identity_misconfigured", expected_user=EP.service_user)
            raise InsightsUnavailable()
        env = dict(os.environ)
        env["SNOWFLAKE_ROLE"] = self.config.role
        if self.private_key:
            env["SNOWFLAKE_PRIVATE_KEY_PATH"] = "in-memory-only"
        try:
            params = sf.params_from_env(EP, "runtime", env=env, commit=self.config.commit)
        except sf.AttributionError as exc:
            raise InsightsUnavailable() from exc
        if self.private_key:
            params.pop("private_key_file")
            key = serialization.load_pem_private_key(self.private_key, password=None)
            params["private_key"] = key.private_bytes(
                serialization.Encoding.DER, serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        params.update(login_timeout=self.config.login_timeout, network_timeout=self.config.network_timeout)
        params["session_parameters"]["STATEMENT_TIMEOUT_IN_SECONDS"] = self.config.query_timeout
        return self.connector(**params)

    @contextmanager
    def connection(self):
        deadline = time.monotonic() + self.config.pool_timeout
        with self.condition:
            while not self.closed and not self.idle and self.count >= self.config.pool_size:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise InsightsUnavailable()
                self.condition.wait(remaining)
            if self.closed:
                raise InsightsUnavailable()
            conn = self.idle.pop() if self.idle else None
            if conn is None:
                self.count += 1
        broken = False
        try:
            if conn is None:
                conn = self._connect()
            yield conn
        except BaseException:
            broken = True
            raise
        finally:
            with self.condition:
                if broken or self.closed:
                    self.count -= 1
                    if conn is not None:
                        try:
                            conn.close()
                        except Exception:
                            pass
                else:
                    self.idle.append(conn)
                self.condition.notify()

    def close(self):
        with self.condition:
            self.closed = True
            for conn in self.idle:
                try:
                    conn.close()
                except Exception:
                    pass
            self.count -= len(self.idle)
            self.idle.clear()
            self.condition.notify_all()
        self.private_key = None

    def fetch(self, account_id, item_type=None, window_end_date=None):
        for attempt in range(self.config.retries + 1):
            try:
                with self.connection() as conn, conn.cursor() as cur:
                    table = f"{EP.database}.APP.TOP_SEARCH_ITEMS"
                    date = window_end_date
                    cur.execute(
                        f"SELECT MAX(WINDOW_END_DATE) FROM {table} WHERE ACCOUNT_ID = %s",
                        (account_id,), timeout=self.config.query_timeout,
                    )
                    latest = cur.fetchone()[0]
                    if latest is None:
                        return None, []
                    if date is None:
                        date = latest
                    sql = f"SELECT {', '.join(COLUMNS)} FROM {table} WHERE ACCOUNT_ID = %s AND WINDOW_END_DATE = %s"
                    binds = [account_id, date]
                    if item_type:
                        sql += " AND ITEM_TYPE = %s"
                        binds.append(item_type)
                    cur.execute(sql + " ORDER BY ITEM_TYPE, RANK", tuple(binds), timeout=self.config.query_timeout)
                    rows = []
                    for values in cur.fetchall():
                        row = dict(zip(COLUMNS, values))
                        for name in ("window_days", "rank", "search_count", "zero_result_count"):
                            if row[name] is not None:
                                row[name] = int(row[name])
                        row["window_end_date"] = row["window_end_date"].isoformat()
                        if row["last_searched_at"] is not None:
                            row["last_searched_at"] = row["last_searched_at"].strftime("%Y-%m-%d %H:%M:%S")
                        rows.append(row)
                    return date.isoformat() if hasattr(date, "isoformat") else date, rows
            except Exception as exc:
                if is_timeout(exc):
                    raise InsightsTimeout() from exc
                if not transient(exc) or attempt == self.config.retries:
                    raise InsightsUnavailable() from exc
                self.sleep(self.config.backoff * 2 ** attempt + random.uniform(0, self.config.backoff))
