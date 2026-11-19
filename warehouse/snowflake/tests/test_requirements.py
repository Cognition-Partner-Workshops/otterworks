
import sys as _run_sys
from pathlib import Path as _RunPath
_run_sys.path.insert(0, str(_RunPath(__file__).resolve().parents[3]))
from warehouse.run_config import render as _run_render

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def pinned():
    names = set()
    for line in _run_render((ROOT / "snowflake/requirements.txt").read_text()).splitlines():
        line = line.split("#")[0].strip()
        if line:
            names.add(re.split(r"[=<>!~\[ ;]", line, maxsplit=1)[0].lower())
    return names


def test_snowpark_imports_are_pinned():
    users = [path for path in (ROOT / "snowpark").glob("*.py") if "snowflake.snowpark" in _run_render(path.read_text())]
    users += [path for path in (ROOT / "snowflake/tests").glob("test_*.py")
              if path.name != "test_requirements.py" and "snowflake.snowpark" in _run_render(path.read_text())]
    assert users
    assert "snowflake-snowpark-python" in pinned()
