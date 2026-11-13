import json
import os
import re
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from .common import identifier, literal, token_name
from .frozen import validate


def connect():
    import snowflake.connector

    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"], user=os.environ["SNOWFLAKE_USER"],
        authenticator="SNOWFLAKE_JWT", private_key_file=os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"],
        private_key_file_pwd=os.environ.get("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE"),
        role=os.environ.get("SNOWFLAKE_ROLE"),
    )


def sql_type(kind):
    if pa.types.is_decimal(kind):
        if kind.precision > 38:
            raise ValueError("Snowflake decimal precision exceeds 38")
        return f"NUMBER({kind.precision},{kind.scale})"
    if pa.types.is_integer(kind):
        return "NUMBER(38,0)"
    if pa.types.is_floating(kind):
        return "DOUBLE"
    if pa.types.is_timestamp(kind):
        return "TIMESTAMP_NTZ" if kind.tz is None else "TIMESTAMP_TZ"
    if pa.types.is_date(kind):
        return "DATE"
    if pa.types.is_string(kind):
        return "VARCHAR"
    if pa.types.is_binary(kind):
        return "BINARY"
    if pa.types.is_boolean(kind):
        return "BOOLEAN"
    raise ValueError("Unsupported Parquet type")


def load(conn, manifest_path, token, prefix="MIGRATION"):
    # DDL identifiers use identifier(); values use literal(), including backslash escaping.
    base = token_name(token, prefix)
    manifest = validate(manifest_path)
    if manifest["token"] != token:
        raise ValueError("Manifest token differs")
    public_key = os.environ["SNOWFLAKE_RUN_PUBLIC_KEY"]
    if not re.fullmatch(r"[A-Za-z0-9+/=]+", public_key):
        raise ValueError("Public key must be base64 DER without PEM headers")
    tag = literal(json.dumps({"token": token, "prefix": prefix, "expires_at": manifest["expires_at"]}))
    database, warehouse, role, user = [identifier(base + suffix) for suffix in ("", "_WH", "_ROLE", "_USER")]
    expiry_name = re.sub(r"[^0-9]", "", manifest["expires_at"])
    monitor = identifier(base + "_RM_E" + expiry_name)
    stage = identifier(base + ".PUBLIC." + base + "_STAGE")
    with conn.cursor() as cursor:
        cursor.execute(f"CREATE RESOURCE MONITOR {monitor} WITH CREDIT_QUOTA=1 FREQUENCY=DAILY "
                       "START_TIMESTAMP=IMMEDIATELY TRIGGERS ON 100 PERCENT DO SUSPEND_IMMEDIATE")
        cursor.execute(f"CREATE WAREHOUSE {warehouse} WITH WAREHOUSE_SIZE='XSMALL' AUTO_SUSPEND=60 "
                       f"AUTO_RESUME=TRUE INITIALLY_SUSPENDED=TRUE RESOURCE_MONITOR={monitor} COMMENT={tag}")
        # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query  # noqa: E501
        cursor.execute(f"CREATE DATABASE {database} COMMENT={tag}")
        # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query  # noqa: E501
        cursor.execute(f"ALTER SCHEMA {identifier(base + '.PUBLIC')} SET COMMENT={tag}")
        # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query  # noqa: E501
        cursor.execute(f"CREATE ROLE {role} COMMENT={tag}")
        # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query  # noqa: E501
        cursor.execute(f"CREATE USER {user} TYPE=SERVICE RSA_PUBLIC_KEY={literal(public_key)} "
                       f"DEFAULT_ROLE={role} DEFAULT_WAREHOUSE={warehouse} COMMENT={tag}")
        # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query  # noqa: E501
        cursor.execute(f"GRANT ROLE {role} TO USER {user}")
        # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query  # noqa: E501
        cursor.execute(f"GRANT USAGE ON WAREHOUSE {warehouse} TO ROLE {role}")
        # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query  # noqa: E501
        cursor.execute(f"GRANT USAGE ON DATABASE {database} TO ROLE {role}")
        # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query  # noqa: E501
        cursor.execute(f"GRANT USAGE ON SCHEMA {identifier(base + '.PUBLIC')} TO ROLE {role}")
        # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query  # noqa: E501
        cursor.execute(f"USE WAREHOUSE {warehouse}")
        # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query  # noqa: E501
        cursor.execute(f"CREATE STAGE {stage} COMMENT={tag}")
        for obj in manifest["objects"]:
            path = (Path(manifest_path).parent / obj["file"]).resolve()
            schema = pq.read_schema(path)
            fields = ", ".join(f"{identifier(f.name)} {sql_type(f.type)}" for f in schema)
            target = identifier(base + ".PUBLIC." + obj["name"])
            # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query  # noqa: E501
            cursor.execute(f"CREATE TABLE {target} ({fields}) COMMENT={tag}")
            # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query  # noqa: E501
            cursor.execute(f"PUT {literal(path.as_uri())} @{stage} AUTO_COMPRESS=FALSE OVERWRITE=FALSE")
            cursor.execute(f"COPY INTO {target} FROM @{stage} FILES=({literal(path.name)}) "
                           "FILE_FORMAT=(TYPE=PARQUET USE_LOGICAL_TYPE=TRUE) MATCH_BY_COLUMN_NAME=CASE_INSENSITIVE "
                           "ON_ERROR=ABORT_STATEMENT")
            # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query  # noqa: E501
            cursor.execute(f"SELECT COUNT(*) FROM {target}")
            if cursor.fetchone()[0] != obj["rows"]:
                raise ValueError("Loaded row count differs")
            # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query  # noqa: E501
            cursor.execute(f"GRANT SELECT ON TABLE {target} TO ROLE {role}")
    return base


def inventory(cursor, token):
    token_name(token)
    found = []
    pattern = re.compile(rf"(?:^|_){re.escape(token)}(?:_|$)", re.I)
    for kind in ("DATABASES", "WAREHOUSES", "RESOURCE MONITORS", "ROLES", "USERS",
                 "OBJECTS IN ACCOUNT", "SCHEMAS IN ACCOUNT", "STAGES IN ACCOUNT"):
        # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query  # noqa: E501
        cursor.execute(f"SHOW {kind}")
        columns = [c[0].lower() for c in cursor.description]
        rows = cursor.fetchall()
        if len(rows) >= 10000:
            raise ValueError("SHOW inventory limit reached; cleanup cannot be verified")
        for values in rows:
            row = dict(zip(columns, values, strict=True))
            if (pattern.search(str(row.get("name", ""))) or pattern.search(str(row.get("database_name", "")))
                or re.search(rf'"token"\s*:\s*"{re.escape(token)}"', str(row.get("comment", "")), re.I)
            ):
                found.append({"kind": kind, "name": row.get("name"), "comment": row.get("comment"),
                              "state": row.get("state"), "database_name": row.get("database_name")})
    return found


def belongs_to_run(obj, token, prefix):
    base = token_name(token, prefix)
    name = str(obj.get("name", "")).upper()
    name_prefix, marker, suffix = name.rpartition(f"_{token.upper()}_AFTER")
    named = marker and name_prefix == prefix and (not suffix or suffix.startswith("_"))
    if named or obj.get("database_name") == base:
        return True
    try:
        comment = json.loads(obj.get("comment") or "{}")
    except (ValueError, TypeError):
        return False
    return isinstance(comment, dict) and comment.get("token") == token and comment.get("prefix") == prefix


def teardown(conn, token, prefix="MIGRATION"):
    base = token_name(token, prefix)
    failures = []
    with conn.cursor() as cursor:
        before = [obj for obj in inventory(cursor, token) if belongs_to_run(obj, token, prefix)]
        monitors = [obj["name"] for obj in before if obj["kind"] == "RESOURCE MONITORS"]
        suspends = [f"ALTER WAREHOUSE {identifier(obj['name'])} SUSPEND" for obj in before
                    if obj["kind"] == "WAREHOUSES" and obj["state"] != "SUSPENDED"]
        statements = suspends + [
            f"DROP {kind} IF EXISTS {identifier(base + suffix)}"
            for kind, suffix in (("DATABASE", ""), ("WAREHOUSE", "_WH"))
        ] + [f"DROP RESOURCE MONITOR IF EXISTS {identifier(name)}" for name in monitors] + [
            f"DROP {kind} IF EXISTS {identifier(base + suffix)}"
            for kind, suffix in (("ROLE", "_ROLE"), ("USER", "_USER"))
        ]
        for statement in statements:
            try:
                cursor.execute(statement)
            except Exception as exc:
                failures.append(type(exc).__name__)
        remaining = [obj for obj in inventory(cursor, token) if belongs_to_run(obj, token, prefix)]
    return {"remaining": remaining, "errors": failures}
