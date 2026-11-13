import os
import re
from contextlib import contextmanager


def identifier(value):
    parts = value.split(".")
    if not parts or any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", part) for part in parts):
        raise ValueError("Invalid SQL identifier")
    return ".".join('"' + part + '"' for part in parts)


@contextmanager
def connection(kind, settings):
    if kind == "duckdb":
        import duckdb

        conn = duckdb.connect(settings["path"], read_only=True)
    elif kind == "oracle":
        import oracledb

        oracledb.defaults.fetch_decimals = True
        conn = oracledb.connect(
            user=os.environ[settings.get("user_env", "ORACLE_USER")],
            password=os.environ[settings.get("password_env", "ORACLE_PASSWORD")],
            dsn=os.environ[settings.get("dsn_env", "ORACLE_DSN")],
        )
    elif kind == "snowflake":
        import snowflake.connector

        conn = snowflake.connector.connect(
            account=os.environ["SNOWFLAKE_ACCOUNT"], user=os.environ["SNOWFLAKE_USER"],
            authenticator="SNOWFLAKE_JWT", private_key_file=os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"],
            private_key_file_pwd=os.environ.get("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE"),
            database=settings.get("database"), schema=settings.get("schema", "PUBLIC"),
            warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE"),
        )
    else:
        raise ValueError("Unsupported adapter")
    try:
        yield conn
    finally:
        conn.close()


def read_table(conn, table, columns):
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT {', '.join(identifier(c) for c in columns)} FROM {identifier(table)}")
        while rows := cursor.fetchmany(10000):
            yield from rows
    finally:
        cursor.close()
