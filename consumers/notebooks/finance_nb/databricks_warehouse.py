"""Live Databricks read transport for finance-notebook."""
import sys
from pathlib import Path

for parent in Path(__file__).resolve().parents:
    kit = parent / "consumers" / "contract-kit"
    if kit.is_dir():
        sys.path.insert(0, str(kit))
        break
else:
    raise RuntimeError("consumer contract kit not found")

import re

from databricks_client import execute as _execute


def execute(native_sql, parameters=(), *, step="contract", label=None):
    if label is not None:
        if not re.fullmatch(r"[A-Za-z0-9_:.-]+", label):
            raise ValueError("invalid statement label")
        native_sql += f"\n/* q={label} */"
    return _execute(native_sql, parameters, consumer="finance-notebook", step=step)
