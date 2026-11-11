import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[2] / 'consumers' / 'contract-kit'))
from contract_client import execute as execute_contract
from finance_nb.warehouse import QUERY_TAG, connect, default_config

PARITY_TD_USER = "svc_exit_parity"
# Frozen pre-migration Teradata statements; only parity tooling replays them.
TERADATA_BASELINE = {path.stem: path.read_text() for path in sorted((ROOT / "teradata").glob("*.sql"))}


class EmulatorWarehouse:
    def __init__(self, name):
        if name != "replay":
            user = os.environ.setdefault("TD_USER", PARITY_TD_USER)
            if user != PARITY_TD_USER:
                raise ValueError(f"emulator comparisons must run as TD_USER={PARITY_TD_USER}")

    def query(self, name):
        data = execute_contract(TERADATA_BASELINE[name], ROOT, name)
        return [dict(zip(data["columns"], row, strict=True)) for row in data["rows"]]

    def close(self):
        pass


class SnowflakeWarehouse:
    DATABASE = "SFX_D1110_AFTER"
    SCHEMA = "COMPAT"
    WAREHOUSE = "SFX_D1110_PARITY_WH"
    QUERY_TAG = QUERY_TAG

    def __init__(self, queries):
        self.queries = queries
        self.query_ids = {}
        self.credentials = {
            key: os.getenv(f"SNOWFLAKE_{key}") for key in ("ACCOUNT", "USER", "ROLE", "PRIVATE_KEY")
        }
        self._connection = None

    @property
    def configured(self):
        return all(self.credentials.values())

    @property
    def connection(self):
        if self._connection is None:
            if not self.configured:
                raise ValueError("Snowflake environment not configured")
            self._connection = connect(default_config({**os.environ, "SNOWFLAKE_WAREHOUSE": self.WAREHOUSE}))
        return self._connection

    def _execute(self, sql):
        with self.connection.cursor() as cursor:
            cursor.execute(sql)
            columns = [item[0] for item in cursor.description]
            return cursor.sfqid, [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]

    def session(self):
        _, rows = self._execute(
            "SELECT CURRENT_DATABASE() AS DATABASE_NAME, CURRENT_SCHEMA() AS SCHEMA_NAME, "
            "CURRENT_WAREHOUSE() AS WAREHOUSE_NAME")
        _, tag = self._execute("SHOW PARAMETERS LIKE 'QUERY_TAG' IN SESSION")
        return {**rows[0], "QUERY_TAG": tag[0]["value"]}

    def query(self, name):
        query_id, rows = self._execute(self.queries[name])
        self.query_ids[name] = query_id
        return rows

    def close(self):
        if self._connection is not None:
            self._connection.close()
            self._connection = None


def target(queries):
    name = os.getenv("WAREHOUSE_CONTRACT_TARGET", "teradata-emulator")
    if name in {"teradata-emulator", "replay", "snowflake-semantics"}:
        return EmulatorWarehouse(name)
    if name == "snowflake":
        return SnowflakeWarehouse(queries)
    raise ValueError(f"unknown warehouse contract target: {name}")
