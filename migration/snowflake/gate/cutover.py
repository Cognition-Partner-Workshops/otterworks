"""Stop the legacy replay, verify parity, and resume the Snowflake task graph."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def sqlserver_service(compose_path: Path) -> str | None:
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    services: dict[str, Any] = compose.get("services", {})
    for name, service in services.items():
        image = str(service.get("image", "")).lower()
        if "mssql" in name.lower() or "sqlserver" in name.lower() or "mssql/server" in image:
            return name
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"sfm-\d{8}-[a-z0-9]{2,8}", args.run):
        print("run token does not look like sfm-<yyyymmdd>-<suffix>", file=sys.stderr)
        return 2
    compose_path = ROOT / "migration" / "snowflake" / "compose.yaml"
    if compose_path.is_file():
        service = sqlserver_service(compose_path)
        if service is None:
            print(f"No SQL Server service was found in {compose_path}", file=sys.stderr)
        else:
            result = subprocess.run(
                ["docker", "compose", "-f", str(compose_path), "stop", service],
                cwd=ROOT,
                check=False,
            )
            if result.returncode:
                return result.returncode
    else:
        print(f"Compose file not present; no replay service stopped: {compose_path}")

    backend_path = ROOT / "migration" / "snowflake" / ".backend.env"
    backend_path.write_text("UBW_BACKEND=snowflake\n", encoding="utf-8")
    print(f"Wrote {backend_path}: UBW_BACKEND=snowflake")
    ledger_path = HERE / "out" / "ledger.json"
    if not ledger_path.is_file():
        print(f"No parity ledger is available to reread: {ledger_path}", file=sys.stderr)
        return 2
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    result = subprocess.run(
        [  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-tainted-env-args.dangerous-subprocess-use-tainted-env-args  # noqa: E501
            sys.executable,
            str(HERE / "parity.py"),
            "--run",
            args.run,
            "--date",
            str(ledger.get("date", "")),
            "--reread",
        ],
        cwd=ROOT,
        check=False,
    )
    if result.returncode:
        return result.returncode
    result = subprocess.run(
        [  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-tainted-env-args.dangerous-subprocess-use-tainted-env-args  # noqa: E501
            sys.executable,
            str(ROOT / "migration" / "snowflake" / "target" / "tasks" / "tasks.py"),
            "--run",
            args.run,
            "resume",
        ],
        cwd=ROOT,
        check=False,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
