
import sys as _run_sys
from pathlib import Path as _RunPath
_run_sys.path.insert(0, str(_RunPath(__file__).resolve().parents[5]))
from warehouse.run_config import render as _run_render

#!/usr/bin/env python3
import os
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parents[3]
cache = root / ".cache" / os.environ.get("NS", _run_render("__BEFORE_NAMESPACE__"))
cache.mkdir(parents=True, exist_ok=True)
with ZipFile(cache / "common.zip", "w", ZIP_DEFLATED) as archive:
    for path in sorted((root / "jobs" / "py" / "common").glob("*.py")):
        if path.name != "package.py":
            archive.write(path, "common/" + path.name)
