#!/usr/bin/env python3
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parents[3]
with ZipFile(root / ".cache" / "common.zip", "w", ZIP_DEFLATED) as archive:
    for path in sorted((root / "jobs" / "py" / "common").glob("*.py")):
        if path.name != "package.py":
            archive.write(path, "common/" + path.name)
