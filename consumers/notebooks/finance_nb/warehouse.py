"""Lazy Snowflake connection and dataframe query port."""
import os
from collections.abc import Callable, Mapping
from typing import Any, Protocol

import pandas as pd

class Connection(Protocol):
    def cursor(self): ...
    def close(self): ...

DATABASE = "SFX_D1110_AFTER"
SCHEMA = "COMPAT"
QUERY_TAG = '{"run":"sfx-d1110","act":"consumers","consumer":"finance-notebook"}'
SETTINGS = ("ACCOUNT", "USER", "ROLE", "WAREHOUSE", "PRIVATE_KEY")


class WarehouseUnavailable(RuntimeError):
    pass


def default_config(environ: Mapping[str, str] | None = None) -> dict:
    environ = os.environ if environ is None else environ
    values = {name.lower(): environ.get(f"SNOWFLAKE_{name}") for name in SETTINGS}
    if not all(values.values()):
        raise WarehouseUnavailable("finance warehouse not configured")
    return {
        **values,
        "database": DATABASE,
        "schema": SCHEMA,
        "authenticator": "SNOWFLAKE_JWT",
        "session_parameters": {"QUERY_TAG": QUERY_TAG, "TIMEZONE": "UTC"},
    }


def _der_private_key(key: str | bytes) -> bytes:
    if isinstance(key, bytes):
        return key
    from cryptography.hazmat.primitives import serialization

    pem = serialization.load_pem_private_key(key.encode(), password=None)
    return pem.private_bytes(
        serialization.Encoding.DER,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )


def connect(config: Mapping[str, Any] | None = None, *,
            connector: Callable[..., Connection] | None = None) -> Connection:
    if os.getenv("FINANCE_WAREHOUSE_ENABLED", "true").lower() not in {"true", "1", "yes"}:
        raise RuntimeError("finance warehouse is disabled")
    config = default_config() if config is None else dict(config)
    config["session_parameters"] = {
        **config.get("session_parameters", {}), "QUERY_TAG": QUERY_TAG, "TIMEZONE": "UTC",
    }
    try:
        if "private_key" in config:
            config["private_key"] = _der_private_key(config["private_key"])
        if connector is None:
            import snowflake.connector

            connector = snowflake.connector.connect
        return connector(**config)
    except Exception as error:
        raise WarehouseUnavailable("finance warehouse unavailable") from error


def run_query(connection: Connection, sql: str) -> pd.DataFrame:
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql)
            columns = [item[0] for item in cursor.description]
            return pd.DataFrame.from_records(cursor.fetchall(), columns=columns)
    except Exception as error:
        raise WarehouseUnavailable("finance query failed") from error
