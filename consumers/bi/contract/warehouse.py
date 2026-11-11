"""Read-only contract warehouse targets."""
import os
import re
import sys
from pathlib import Path
from typing import Protocol

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[2] / "consumers" / "contract-kit"))
from contract_client import execute as execute_contract


class Warehouse(Protocol):
    def query(self, sql: str) -> list[dict]: ...


class EmulatorWarehouse:
    def __init__(self, queries):
        name = os.getenv("WAREHOUSE_CONTRACT_TARGET", "teradata-emulator")
        if name != "replay":
            user = os.environ.setdefault("TD_USER", "svc_exit_parity")
            if user == "svc_bi_semantic":
                raise ValueError("svc_bi_semantic is retired; use svc_exit_parity")
            if user != "svc_exit_parity":
                raise ValueError("emulator targets require TD_USER=svc_exit_parity")
        self.names = {sql: name for name, sql in queries.items()}

    def query(self, sql):
        data = execute_contract(sql, ROOT, self.names[sql])
        return [dict(zip(data["columns"], row, strict=True)) for row in data["rows"]]


class SnowflakeWarehouse:
    DATABASE = "SFX_D1110_AFTER"
    SCHEMA = "COMPAT"
    WAREHOUSE = "SFX_D1110_PARITY_WH"
    QUERY_TAG = '{"run":"sfx-d1110","act":"consumers","consumer":"bi-semantic"}'

    def __init__(self):
        self.credentials = {
            key: os.getenv(f"SNOWFLAKE_{key}")
            for key in ("ACCOUNT", "USER", "ROLE", "PRIVATE_KEY")
        }
        self.connection = None
        self.query_ids = []
        self.columns = []

    def query(self, sql, name="query"):
        if not all(self.credentials.values()):
            raise ValueError("Snowflake environment not configured")
        if not re.match(r"^\s*(SELECT|WITH)\b", sql, re.I) or ";" in sql:
            raise ValueError("only single read-only SELECT queries are allowed")
        if self.connection is None:
            import snowflake.connector
            from cryptography.hazmat.primitives import serialization

            key = serialization.load_pem_private_key(
                self.credentials["PRIVATE_KEY"].encode(), password=None
            )
            self.connection = snowflake.connector.connect(
                account=self.credentials["ACCOUNT"],
                user=self.credentials["USER"],
                role=self.credentials["ROLE"],
                authenticator="SNOWFLAKE_JWT",
                private_key=key.private_bytes(
                    serialization.Encoding.DER,
                    serialization.PrivateFormat.PKCS8,
                    serialization.NoEncryption(),
                ),
                database=self.DATABASE,
                schema=self.SCHEMA,
                warehouse=self.WAREHOUSE,
                session_parameters={"QUERY_TAG": self.QUERY_TAG, "TIMEZONE": "UTC"},
            )
        with self.connection.cursor() as cursor:
            try:
                cursor.execute(sql)
            finally:
                if cursor.sfqid:
                    self.query_ids.append((name, cursor.sfqid))
                    print(f"snowflake query_id {name} {cursor.sfqid}", flush=True)
            self.columns = [column[0] for column in cursor.description]
            return [dict(zip(self.columns, row, strict=True)) for row in cursor.fetchall()]

    def close(self):
        if self.connection is not None:
            self.connection.close()


def target(queries):
    name = os.getenv("WAREHOUSE_CONTRACT_TARGET", "teradata-emulator")
    if name in {"teradata-emulator", "replay", "snowflake-semantics"}:
        return EmulatorWarehouse(queries)
    if name == "snowflake":
        return SnowflakeWarehouse()
    raise ValueError(f"unknown warehouse contract target: {name}")
