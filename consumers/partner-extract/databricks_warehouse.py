"""Live Databricks read transport for partner-extract."""
import sys
from pathlib import Path

for parent in Path(__file__).resolve().parents:
    kit = parent / "consumers" / "contract-kit"
    if kit.is_dir():
        sys.path.insert(0, str(kit))
        break
else:
    raise RuntimeError("consumer contract kit not found")

from databricks_client import execute as _execute

STATEMENT_IDS = []


def _statement_id(cursor):
    try:
        return cursor.query_id
    except Exception:
        return None


def _capture_statement_ids():
    from databricks.sql.client import Cursor

    if getattr(Cursor.execute, "_partner_extract", False):
        return
    original = Cursor.execute

    def execute(self, *args, **kwargs):
        try:
            return original(self, *args, **kwargs)
        finally:
            STATEMENT_IDS.append(_statement_id(self))

    execute._partner_extract = True
    Cursor.execute = execute


def execute(native_sql, parameters=(), step="contract"):
    _capture_statement_ids()
    result = _execute(native_sql, parameters, consumer="partner-extract", step=step)
    result["statement_id"] = STATEMENT_IDS[-1]
    return result
