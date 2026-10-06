#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["psycopg[binary]==3.2.9"]
# ///
"""Move the billing schema and data onto the run-token RDS database.

End to end, and safe to rerun from scratch:

1. dumps the legacy ``billing`` tables (constraints and indexes — never
   routines) and their data from the local procs stack with
   ``pg_dump --schema-only`` / ``--data-only --inserts``;
2. takes the ``billing_svc`` schema from the billing-service ``db/migrations``
   and its data from the seeded target database;
3. drops and rebuilds both schemas on the run database (``<token>`` with ``-``
   as ``_`` on the private ``otterworks-postgres-dev`` instance) by invoking the
   tagged Lambda ``<token>-billing-sql`` in the instance's private subnets, all
   in one transaction — a rerun starts clean;
4. prints a legacy-vs-RDS row-count table matching what
   ``scripts/billing-baseline.py`` reports, plus the routines still present in
   the RDS ``billing`` schema (expected: none — the stored procedures stay on
   legacy).

The Lambda shares the db-init security group (no ingress, egress to Postgres
on the VPC CIDR only) and credentials travel in the invocation payload, so no
network access is opened. Run it with the engineer role assumed, since it
shells out to ``aws`` for Secrets Manager and Lambda:

    source <(cloudworker/assume.sh engineer devin-<session>)
    uv run scripts/billing-to-rds.py --ns <ns> --token lp-20261006-bd

``--counts-only`` skips the load and just prints the comparison table, e.g. to
recheck after a reload.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = ROOT / "services" / "billing-service" / "db" / "migrations"

BILLING_TABLES = (
    "tenants", "plans", "subscriptions", "usage_events", "rating_periods",
    "rating_results", "invoices", "invoice_lines", "credit_notes",
    "dunning_attempts", "notifications",
)
BILLING_SVC_TABLES = (
    "tenants", "plans", "subscriptions", "usage_events", "rating_periods",
    "rating_results",
)


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kwargs)


def docker(container: str, *args: str) -> str:
    return run(["docker", "exec", container, *args]).stdout


def pg_dump(container: str, user: str, db: str, schema: str, mode: str) -> str:
    # -t '<schema>.*' keeps the dump to tables, constraints and indexes:
    # routines in the schema are never selected, so the stored procedures
    # stay behind on legacy.
    args = [container, "pg_dump", "-U", user, "-d", db, "-t", f"{schema}.*",
            f"--{mode}", "--no-privileges"]
    if mode == "schema-only":
        args.append("--no-owner")
    else:
        args.append("--inserts")
    return docker(*args)


def split_sql(text: str) -> list[str]:
    """Split plain SQL into statements on top-level semicolons.

    Skips comments, psql meta-commands (\\restrict, \\unrestrict) and empty
    fragments; tracks single-quoted strings ('' escape) so semicolons inside
    literals stay inside their statement. The dumps this runs on never contain
    routines or dollar-quoted bodies.
    """
    statements, buf = [], []
    i, n = 0, len(text)
    in_str = in_line = in_block = False
    while i < n:
        c, nxt = text[i], text[i + 1] if i + 1 < n else ""
        if in_line:
            if c == "\n":
                in_line = False
        elif in_block:
            if c == "*" and nxt == "/":
                i += 1
                in_block = False
        elif in_str:
            buf.append(c)
            if c == "'":
                if nxt == "'":
                    buf.append(nxt)
                    i += 1
                else:
                    in_str = False
        elif c == "-" and nxt == "-":
            in_line = True
            i += 1
        elif c == "/" and nxt == "*":
            in_block = True
            i += 1
        elif c == "'":
            buf.append(c)
            in_str = True
        elif c == ";":
            statement = "".join(buf).strip()
            buf = []
            if statement:
                statements.append(statement)
        else:
            buf.append(c)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return [s for s in statements if not s.lstrip().startswith("\\")]


ROUTINE = re.compile(r"^CREATE\s+(OR\s+REPLACE\s+)?(FUNCTION|PROCEDURE)\b", re.I)
POST_DATA = re.compile(
    r"^ALTER\s+TABLE\b.*\bADD\s+CONSTRAINT\b|^CREATE\s+(UNIQUE\s+)?INDEX\b", re.I | re.S)


def classify(statements: list[str]) -> tuple[list[str], list[str], list[str]]:
    """Split statements into (pre-data DDL, post-data DDL, skipped routines).

    pg_dump emits CHECK constraints inline in CREATE TABLE but PRIMARY KEYs and
    FOREIGN KEYs as ALTER TABLE ... ADD CONSTRAINT; those (and indexes) must run
    after the data so insert order cannot violate them.
    """
    pre, post, skipped = [], [], []
    for statement in statements:
        if ROUTINE.match(statement):
            skipped.append(statement.split("(", 1)[0].strip())
        elif POST_DATA.match(statement):
            post.append(statement)
        else:
            pre.append(statement)
    return pre, post, skipped


def aws(*args: str) -> str:
    env = {**os.environ, "AWS_DEFAULT_REGION": os.environ.get("AWS_REGION", "us-east-1")}
    return run(["aws", *args], env=env).stdout


def db_creds(token: str) -> dict:
    return json.loads(aws(
        "secretsmanager", "get-secret-value",
        "--secret-id", f"otterworks-{token}/billing-db",
        "--query", "SecretString", "--output", "text",
    ))


def invoke(function: str, payload: dict) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        infile = os.path.join(tmp, "in.json")
        outfile = os.path.join(tmp, "out.json")
        Path(infile).write_text(json.dumps(payload))
        meta = json.loads(aws(
            "lambda", "invoke", "--function-name", function,
            "--payload", f"fileb://{infile}", outfile,
        ))
        body = json.loads(Path(outfile).read_text())
    if meta.get("FunctionError") or "errorMessage" in body:
        raise RuntimeError(f"lambda {function} failed: {body.get('errorMessage', body)}")
    return body


def build_statements(ns: str) -> tuple[list[str], list[str]]:
    legacy_container = f"otterworks-procs-{ns}-legacy-billing-db-1"
    svc_container = f"otterworks-procs-{ns}-billing-service-db-1"

    billing_ddl_pre, billing_ddl_post, skipped = classify(split_sql(
        pg_dump(legacy_container, "billing", f"billing_{ns}", "billing", "schema-only")
    ))
    billing_data = split_sql(pg_dump(legacy_container, "billing", f"billing_{ns}", "billing", "data-only"))
    svc_ddl_pre, svc_ddl_post, svc_skipped = classify(
        [s for path in sorted(MIGRATIONS_DIR.glob("*.sql")) for s in split_sql(path.read_text())]
    )
    svc_data = split_sql(pg_dump(svc_container, "billing_svc", f"billing_svc_{ns}", "billing_svc", "data-only"))

    statements = (
        ["DROP SCHEMA IF EXISTS billing CASCADE",
         "DROP SCHEMA IF EXISTS billing_svc CASCADE",
         "CREATE SCHEMA billing",
         "CREATE SCHEMA billing_svc"]
        + billing_ddl_pre + svc_ddl_pre
        + billing_data + svc_data
        + billing_ddl_post + svc_ddl_post
    )
    notes = [f"skipped routine definitions: {len(skipped) + len(svc_skipped)}"]
    notes += [f"  {name}" for name in skipped + svc_skipped]
    notes.append(
        f"statements: {len(statements)} "
        f"(ddl {len(billing_ddl_pre) + len(svc_ddl_pre)} pre-data, "
        f"{len(billing_ddl_post) + len(svc_ddl_post)} post-data, "
        f"data {len(billing_data) + len(svc_data)})")
    return statements, notes


def count_queries() -> list[dict]:
    queries = []
    for schema, tables in (("billing", BILLING_TABLES), ("billing_svc", BILLING_SVC_TABLES)):
        queries.append({"name": f"{schema}.tables", "sql": (
            "SELECT table_name FROM information_schema.tables "
            f"WHERE table_schema = '{schema}' AND table_type = 'BASE TABLE' ORDER BY 1")})
        for table in tables:
            queries.append({"name": f"{schema}.{table}",
                            "sql": f"SELECT count(*) FROM {schema}.{table}"})
    queries.append({"name": "billing.routines", "sql": (
        "SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
        "WHERE n.nspname = 'billing' ORDER BY 1")})
    return queries


def cell(rows) -> str:
    if isinstance(rows, dict):
        return "missing" if "42P01" in rows.get("error", "") else f"error: {rows['error']}"
    return str(rows[0][0]) if rows else "missing"


def legacy_counts(ns: str, offset: int) -> dict[str, str]:
    counts = {}
    for schema, port, dbname, user in (
        ("billing", 55432 + offset, f"billing_{ns}", "billing"),
        ("billing_svc", 56432 + offset, f"billing_svc_{ns}", "billing_svc"),
    ):
        with psycopg.connect(host="localhost", port=port, dbname=dbname,
                             user=user, password=user, connect_timeout=10) as conn:
            for table in (BILLING_TABLES if schema == "billing" else BILLING_SVC_TABLES):
                counts[f"{schema}.{table}"] = str(
                    conn.execute(f"SELECT count(*) FROM {schema}.{table}").fetchone()[0])
            routines = conn.execute(
                "SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
                f"WHERE n.nspname = '{schema}' ORDER BY 1").fetchall()
            counts[f"{schema}.routines"] = ", ".join(r[0] for r in routines) or "(none)"
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ns", default=os.getenv("NS", "dev"), help="procs stack namespace (default: NS or dev)")
    parser.add_argument("--token", required=True, help="run token, e.g. lp-20261006-bd")
    parser.add_argument("--function", help="sql-runner Lambda name (default: <token>-billing-sql)")
    parser.add_argument("--counts-only", action="store_true", help="skip the load, print the count table")
    args = parser.parse_args()

    offset = zlib.crc32(args.ns.encode()) % 1000
    function = args.function or f"{args.token}-billing-sql"
    creds = db_creds(args.token)
    db = {"host": creds["host"], "port": creds["port"], "dbname": creds["dbname"],
          "user": creds["username"], "password": creds["password"]}

    if not args.counts_only:
        statements, notes = build_statements(args.ns)
        for note in notes:
            print(note)
        result = invoke(function, {"db": db, "op": "exec", "statements": statements})
        print(f"load: executed {result['executed']} statements in one transaction")

    rds = invoke(function, {"db": db, "op": "query", "queries": count_queries()})["results"]
    local = legacy_counts(args.ns, offset)

    print("\n| schema | table | legacy | RDS |")
    print("| --- | --- | ---: | ---: |")
    mismatch = 0
    for schema, tables in (("billing", BILLING_TABLES), ("billing_svc", BILLING_SVC_TABLES)):
        present = {r[0] for r in rds.get(f"{schema}.tables", [])} \
            if isinstance(rds.get(f"{schema}.tables"), list) else set()
        for table in tables:
            name = f"{schema}.{table}"
            remote = cell(rds.get(name, []))
            leg = local[name]
            bad = leg != remote
            mismatch += bad
            print(f"| {schema} | {table} | {leg} | {remote} |{'  <-- MISMATCH' if bad else ''}")
        for extra in sorted(present - set(tables)):
            mismatch += 1
            print(f"| {schema} | {extra} | (not expected) | present |  <-- MISMATCH")
    routines = ", ".join(r[0] for r in rds.get("billing.routines", [])) or "(none)"
    print(f"\nbilling routines on legacy: {local['billing.routines']}")
    print(f"billing routines on RDS:    {routines}")
    print(f"\nresult: {'FAIL' if mismatch else 'PASS'} ({mismatch} mismatched tables)")
    return 1 if mismatch else 0


if __name__ == "__main__":
    sys.exit(main())
