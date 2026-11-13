import argparse
import json
from pathlib import Path

import yaml

from .adapters import connection, read_table
from .core import compare


def run(config, left_kind, right_kind, out):
    objects = []
    connection_error = False

    def failure(spec, exc):
        return {"name": spec.get("name", spec["left_table"]), "status": "red", "error": type(exc).__name__}

    try:
        with connection(left_kind, config["connections"]["left"]) as left:
            with connection(right_kind, config["connections"]["right"]) as right:
                for spec in config["objects"]:
                    try:
                        columns = list(dict.fromkeys(spec.get("keys", []) + spec["compare"]))
                        objects.append(compare(
                            spec, read_table(left, spec["left_table"], columns),
                            read_table(right, spec["right_table"], columns),
                        ))
                    except Exception as exc:
                        objects.append(failure(spec, exc))
    except Exception as exc:
        connection_error = True
        objects = [failure(spec, exc) for spec in config["objects"]]
    summary = {status: sum(o["status"] == status for o in objects) for status in ("green", "amber", "red")}
    report = {"summary": summary, "objects": objects}
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "parity.json").write_text(json.dumps(report, indent=2) + "\n")
    lines = ["# Warehouse parity", "", f"Green: {summary['green']}; amber: {summary['amber']}; red: {summary['red']}",
             "", "| Object | Status | Checks that differ | Owner | Open question |", "|---|---|---|---|---|"]
    for obj in objects:
        failed = ", ".join(k for k, v in obj.get("checks", {}).items() if not v) or obj.get("error", "")
        cells = [obj["name"], obj["status"], failed, obj.get("owner") or "", obj.get("open_question") or ""]
        lines.append("| " + " | ".join(str(c).replace("|", "\\|").replace("\n", " ") for c in cells) + " |")
    (out / "parity.md").write_text("\n".join(lines) + "\n")
    print(lines[2])
    return int(connection_error or summary["red"] > 0)


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("run")
    command.add_argument("--config", required=True)
    command.add_argument("--left", choices=["oracle", "snowflake", "duckdb"], required=True)
    command.add_argument("--right", choices=["oracle", "snowflake", "duckdb"], required=True)
    command.add_argument("--out", required=True)
    args = parser.parse_args()
    with open(args.config) as handle:
        config = yaml.safe_load(handle)
    return run(config, args.left, args.right, args.out)


if __name__ == "__main__":
    raise SystemExit(main())
