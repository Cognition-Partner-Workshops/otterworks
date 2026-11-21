"""Pull the SQL SELECT blocks out of a Qlik load script and run them on an engine."""
import re
from pathlib import Path

BLOCK = re.compile(r"^(\w+):\s*\n\s*LOAD[^;]*;\s*\n\s*SQL\s+(SELECT.*?);", re.S | re.M | re.I)


def blocks(path):
    return [(m.group(1), m.group(2).strip()) for m in BLOCK.finditer(Path(path).read_text())]


def run(engine, path):
    return {name: engine.query(sql) for name, sql in blocks(path)}
