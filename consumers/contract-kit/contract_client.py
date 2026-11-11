"""Shared subprocess client for Python warehouse contracts."""
import json
import os
from pathlib import Path
import subprocess
import sys


def bind(sql, parameters):
    parts = sql.split("?")
    if len(parts) != len(parameters) + 1:
        raise ValueError("SQL parameter count does not match")
    result = parts[0]
    for value, part in zip(parameters, parts[1:]):
        literal = "NULL" if value is None else "'" + str(value).replace("'", "''") + "'"
        result += literal + part
    return result


def execute(sql, root, query, parameters=()):
    target = os.getenv("WAREHOUSE_CONTRACT_TARGET", "teradata-emulator")
    recorded = Path(root) / "recorded" / "teradata" / (query + ".json")
    if target == "replay":
        return json.loads(recorded.read_text())
    if target not in {"teradata-emulator", "snowflake-semantics"}:
        raise ValueError("unsupported bridge target: " + target)
    bridge = Path(__file__).with_name("bridge.py")
    command = [os.getenv("CONTRACT_KIT_PYTHON", sys.executable), str(bridge),
               "--target", target, "--query", query]
    if os.getenv("CONTRACT_RECORD") == "true":
        command += ["--record", str(recorded)]
    result = subprocess.run(command, input=bind(sql, parameters), text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    return json.loads(result.stdout)
