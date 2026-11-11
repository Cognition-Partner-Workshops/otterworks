"""Live Databricks read transport for bi-semantic."""
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


def execute(native_sql, parameters=()):
    return _execute(native_sql, parameters, consumer="bi-semantic")
