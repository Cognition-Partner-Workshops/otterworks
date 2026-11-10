"""Contract target ports; replay is the default until remote adapters exist."""
import json
import os
from pathlib import Path
from typing import Protocol

ROOT = Path(__file__).parent


class Warehouse(Protocol):
    def query(self, sql: str) -> list[dict]: ...


class EmulatorWarehouse:
    def __init__(self, queries):
        self.names = {sql: name for name, sql in queries.items()}

    def query(self, sql):
        if os.getenv("TD_EMULATOR_URL"):
            return self.execute_endpoint(os.environ["TD_EMULATOR_URL"], sql)
        name = self.names[sql]
        data = json.loads((ROOT / "recorded" / "teradata" / f"{name}.json").read_text())
        return [dict(zip(data["columns"], row, strict=True)) for row in data["rows"]]

    def execute_endpoint(self, endpoint, sql):
        raise NotImplementedError("emulator endpoint not configured")


class SnowflakeWarehouse:
    DATABASE = "SFX_D1110_AFTER"
    SCHEMA = "COMPAT"
    QUERY_TAG = '{"run":"sfx-d1110","act":"consumers","consumer":"bi-semantic"}'

    def __init__(self):
        self.credentials = {
            key: os.getenv(f"SNOWFLAKE_{key}")
            for key in ("ACCOUNT", "USER", "ROLE", "WAREHOUSE", "PRIVATE_KEY")
        }

    def query(self, sql):
        if not all(self.credentials.values()):
            raise ValueError("Snowflake environment not configured")
        raise NotImplementedError(
            f"Snowflake adapter not installed; execute supplied SQL in "
            f"{self.DATABASE}.{self.SCHEMA} with QUERY_TAG={self.QUERY_TAG}"
        )


def target(queries):
    name = os.getenv("WAREHOUSE_CONTRACT_TARGET", "teradata-emulator")
    if name == "teradata-emulator":
        return EmulatorWarehouse(queries)
    if name == "snowflake":
        return SnowflakeWarehouse()
    raise ValueError(f"unknown warehouse contract target: {name}")
