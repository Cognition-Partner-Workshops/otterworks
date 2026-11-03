"""Run a static Databricks SQL file statement by statement on the policy warehouse.

`databricks experimental aitools tools query --file` accepts one statement per file, so this
splits on blank-line-terminated `;` and submits each statement, in order, as its own CLI call
(the CLI is the sanctioned ad-hoc SQL path; nothing here builds SQL text).
"""
import json
import subprocess
import sys
from pathlib import Path

WAREHOUSE = "565cd2fd713738c4"  # policy.targets.warehouse_http_path


def statements(path: Path) -> list[str]:
    out = []
    for chunk in path.read_text().split(";\n"):
        body = "\n".join(l for l in chunk.splitlines() if not l.strip().startswith("--")).strip()
        if body:
            out.append(body)
    return out


def main(argv: list[str]) -> int:
    for f in argv:
        for i, stmt in enumerate(statements(Path(f)), 1):
            r = subprocess.run(["databricks", "experimental", "aitools", "tools", "query",
                                "--warehouse", WAREHOUSE, "--output", "json", stmt],
                               capture_output=True, text=True)
            first = stmt.splitlines()[0][:90]
            if r.returncode != 0:
                print(f"{f}#{i} FAILED: {first}\n{r.stdout}\n{r.stderr}", file=sys.stderr)
                return r.returncode
            try:
                rows = json.loads(r.stdout)
            except json.JSONDecodeError:
                rows = r.stdout.strip()
            print(f"{f}#{i} ok: {first}")
            if isinstance(rows, dict) and rows.get("rows"):
                print(json.dumps(rows["rows"], indent=1))
            elif isinstance(rows, list) and rows:
                print(json.dumps(rows, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
