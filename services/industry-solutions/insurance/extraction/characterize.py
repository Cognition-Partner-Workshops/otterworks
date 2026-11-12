#!/usr/bin/env python3
"""Run the catalog's assertions in real SQL*Plus; no emulation or expected failures."""

import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]

PRELUDE = """
WHENEVER OSERROR EXIT FAILURE
WHENEVER SQLERROR EXIT FAILURE ROLLBACK
SET SERVEROUTPUT ON SIZE UNLIMITED
SET FEEDBACK OFF VERIFY OFF HEADING OFF PAGESIZE 0 LINESIZE 240
ALTER SESSION SET NLS_DATE_FORMAT = 'YYYY-MM-DD';
ALTER SESSION SET NLS_NUMERIC_CHARACTERS = '.,';
DECLARE
    v NUMBER;
    w NUMBER;
    rid NUMBER;
    txt VARCHAR2(4000);
    checks PLS_INTEGER := 0;
    PROCEDURE ok(b BOOLEAN, detail VARCHAR2) IS
    BEGIN
        IF b IS NULL OR NOT b THEN
            RAISE_APPLICATION_ERROR(-20999, detail);
        END IF;
        checks := checks + 1;
        DBMS_OUTPUT.PUT_LINE('OBS|' || detail);
    END;
    PROCEDURE err(stmt VARCHAR2, expected NUMBER) IS
        actual NUMBER := 0;
    BEGIN
        BEGIN EXECUTE IMMEDIATE stmt;
        EXCEPTION WHEN OTHERS THEN actual := SQLCODE;
        END;
        ok(actual = expected, 'expected error ' || expected || '; actual ' || actual);
    END;
BEGIN
"""


def sqlplus(container, schema, sql):
    return subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            container,
            "sqlplus",
            "-L",
            "-s",
            f"{schema}/{schema}@localhost:1521/FREEPDB1",
        ],
        input=sql,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--allow-disposable-fixture", action="store_true", required=True
    )
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9]+", args.namespace):
        parser.error("namespace must be alphanumeric")
    container = f"otterworks-insurance-{args.namespace}-insurance-oracle-1"
    rules = json.loads((HERE / "rules.json").read_text())
    cases = json.loads((HERE / "cases.json").read_text())
    if {r["test"] for r in rules} != {c["id"] for c in cases}:
        raise ValueError("catalog/test coverage must be exact")
    args.output.mkdir(parents=True, exist_ok=True)
    version = sqlplus(
        container,
        "commission_pay",
        "SET HEADING OFF\nSELECT product || ' ' || version_full FROM product_component_version;\nEXIT;\n",
    )
    print(f"Live fixture: {container}", flush=True)
    rows = []
    for rule, case in zip(rules, cases, strict=True):
        if case["id"] != rule["test"]:
            raise ValueError("cases must follow catalog order")
        sentinel = f"PASS|{case['id']}"
        sql = (
            PRELUDE
            + case["sql"]
            + f"""
    ok(checks > 0, 'at least one assertion executed');
    DBMS_OUTPUT.PUT_LINE('{sentinel}');
END;
/
EXIT SUCCESS
"""
        )
        proc = sqlplus(container, case["schema"], sql)
        output = proc.stdout + proc.stderr
        passed = proc.returncode == 0 and sentinel in output.splitlines()
        (args.output / f"{case['id']}.sql").write_text(sql)
        (args.output / f"{case['id']}.log").write_text(output)
        detail = "; ".join(s[4:] for s in output.splitlines() if s.startswith("OBS|"))
        row = {
            "id": rule["id"],
            "classification": rule["status"],
            "test": case["id"],
            "result": "PASS" if passed else "FAIL",
            "observations": detail if passed else output.strip(),
        }
        rows.append(row)
        print(
            f"{row['result']} {rule['status'].upper()} {rule['id']}: {rule['sentence']}",
            flush=True,
        )
        print(detail if passed else output, flush=True)
    source_files = sorted((HERE.parent / "db").rglob("*.sql"))
    source_files += [
        HERE.parent / "spec/cp114-commission-spec-scan.pdf",
        HERE / "rules.json",
        HERE / "cases.json",
        HERE / "product-config.json",
        HERE / "render.py",
        Path(__file__),
    ]
    hashes = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in source_files
    }
    image = subprocess.run(
        ["docker", "inspect", container, "--format", "{{.Image}}"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    report = {
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "container": container,
        "image_id": image,
        "oracle_version_query": version.stdout.strip(),
        "source_sha256": hashes,
        "rows": rows,
    }
    (args.output / "test-run.json").write_text(json.dumps(report, indent=2) + "\n")
    with (args.output / "test-run.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "# Live Oracle characterization report",
        "",
        f"UTC: {report['time_utc']}",
        f"Container: `{container}`",
        f"Image: `{image}`",
        "",
        "Green = no identified contradiction; amber = owner decision required, NOT a failed test or approval.",
        "PASS means the existing database behavior was observed, not that it matches the specification.",
        "These tests mutate only a disposable fixture. Use a fresh namespace; do not run on a shared database.",
        "",
        "| Rule | Color | Test | Result | Observations |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                str(row[k]).replace("|", "/").replace("\n", " ")
                for k in ["id", "classification", "test", "result", "observations"]
            )
            + " |"
        )
    failures = sum(r["result"] != "PASS" for r in rows)
    amber = sum(r["classification"] == "amber" for r in rows)
    decisions = len({r["decision"].split(":", 1)[0] for r in rules if r["decision"]})
    summary = f"{len(rows) - failures}/{len(rows)} PASS; {amber} amber rules; {decisions} owner decisions; {failures} failed tests"
    lines += [
        "",
        summary,
        "",
        "Source and test SHA-256 fingerprints and full SQL*Plus logs are in the JSON and per-test files beside this report.",
    ]
    (args.output / "test-run.md").write_text("\n".join(lines) + "\n")
    print(summary, flush=True)
    return bool(failures)


if __name__ == "__main__":
    sys.exit(main())
