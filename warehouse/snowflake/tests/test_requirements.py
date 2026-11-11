from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def pinned():
    names = set()
    for line in (ROOT / "snowflake/requirements.txt").read_text().splitlines():
        line = line.split("#")[0].strip()
        if line:
            names.add(re.split(r"[=<>!~\[ ;]", line, maxsplit=1)[0].lower())
    return names


def test_snowpark_imports_are_pinned():
    users = [path for path in (ROOT / "snowpark").glob("*.py") if "snowflake.snowpark" in path.read_text()]
    users += [path for path in (ROOT / "snowflake/tests").glob("test_*.py")
              if path.name != "test_requirements.py" and "snowflake.snowpark" in path.read_text()]
    assert users
    assert "snowflake-snowpark-python" in pinned()
