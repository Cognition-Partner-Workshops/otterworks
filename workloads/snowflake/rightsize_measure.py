"""Measure fixed dbt builds; report query-attributed credits, never estimated idle cost."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "workloads/attribution"))
import sf_attribution as attr  # noqa: E402

SESSION_URL = "https://partner-workshops.devinenterprise.com/sessions/1272f6d4e9084a498e379e429132553c"
WORKLOADS = {
    "doc_usage_dashboard": "account_usage",
    "doc_search_api": "top_items",
    "churn_model": "account_score",
}
DEFAULT_RESULTS = Path(__file__).with_name("rightsize_results.json")


@contextmanager
def credentials():
    os.environ.pop("SNOWFLAKE_HOST", None)
    with tempfile.NamedTemporaryFile(dir="/dev/shm", suffix=".pem") as key:
        os.fchmod(key.fileno(), 0o600)
        key.write(os.environ["SFNFR_PRIVATE_KEY"].encode())
        key.flush()
        for target, source in (("ACCOUNT", "ACCOUNT"), ("USER", "USER"), ("ROLE", "ROLE")):
            os.environ[f"SNOWFLAKE_{target}"] = os.environ[f"SFNFR_{source}"]
        os.environ["SNOWFLAKE_PRIVATE_KEY_FILE"] = key.name
        if os.environ["SFNFR_ROLE"] != "SFNFR_20261104_BUILDER":
            raise ValueError("Only the run's builder role is permitted")
        yield key.name


def connect(workload, key):
    import snowflake.connector

    params = attr.connection_params(
        attr.Endpoint("platform", "rightsize"), account=os.environ["SFNFR_ACCOUNT"],
        private_key_file=key, phase="dev", commit=attr.current_commit(str(ROOT)),
        run_id=attr.make_run_id("platform", "dev"), session_url=SESSION_URL,
        role=os.environ["SFNFR_ROLE"],
    )
    params["user"] = os.environ["SFNFR_USER"]
    params.update(warehouse=attr.MIGRATIONS_WAREHOUSE, database=attr.GOVERNANCE_DATABASE, schema="SCHEMACHANGE")
    return snowflake.connector.connect(**params)


def settings(con, warehouse):
    cur = con.cursor()
    cur.execute("SHOW WAREHOUSES LIKE %s", (warehouse,))
    rows = [dict(zip((d[0] for d in cur.description), row)) for row in cur.fetchall()]
    return next(row for row in rows if row["name"] == warehouse)


def build(workload, code_root, run_id, commit):
    sys.path.insert(0, str(code_root / "workloads/pipeline"))
    spec = importlib.util.spec_from_file_location("rightsize_dbt", code_root / "workloads/dbt/run.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    tag = attr.query_tag_json(
        attr.Endpoint(workload, WORKLOADS[workload]), phase="dev", commit=commit,
        run_id=run_id, session_url=SESSION_URL,
    )
    original = subprocess.check_output

    def output(command, **kwargs):
        if isinstance(command, list) and len(command) > 2 and command[2] == "tag":
            return tag + "\n"
        return original(command, **kwargs)

    selected = {workload: runner.CONSUMERS[workload]}
    with patch.object(runner, "SESSION_URL", SESSION_URL), patch.object(runner, "CONSUMERS", selected), \
            patch.object(runner.attr, "make_run_id", return_value=run_id), \
            patch.object(subprocess, "check_output", side_effect=output), \
            patch.object(sys, "argv", [str(code_root / "workloads/dbt/run.py"), "--workload", workload]):
        import pipeline
        with patch.object(pipeline, "SESSION_URL", SESSION_URL), patch.object(pipeline, "CONSUMERS", selected):
            result = runner.main()
    if result:
        raise RuntimeError(f"dbt build failed: {result}")


def run(args, con):
    if args.label == "declared" and args.workload != "doc_search_api":
        raise ValueError("The declared-size comparison is only for doc_search_api")
    code_root = args.code_root.resolve()
    commit = attr.current_commit(str(code_root))
    run_id = attr.make_run_id(args.workload, "dev")
    warehouse = attr.warehouse_name(args.workload)
    record = {"workload": args.workload, "warehouse": warehouse, "label": args.label,
              "run_id": run_id, "commit": commit,
              "started_at": datetime.now(timezone.utc).isoformat()}
    try:
        if args.label == "declared":
            con.cursor().execute(f"ALTER WAREHOUSE {warehouse} SET WAREHOUSE_SIZE = 'LARGE'")
        record["settings"] = settings(con, warehouse)
        started = time.monotonic()
        try:
            build(args.workload, code_root, run_id, commit)
            record["status"] = "succeeded"
        except Exception:
            record["status"] = "failed"
            raise
        finally:
            record["wall_seconds"] = time.monotonic() - started
            records = json.loads(args.results.read_text()) if args.results.exists() else []
            records.append(record)
            args.results.write_text(json.dumps(records, indent=2, default=str) + "\n")
            print(json.dumps(record, default=str))
    finally:
        if args.label == "declared":
            con.cursor().execute(f"ALTER WAREHOUSE {warehouse} SET WAREHOUSE_SIZE = 'XSMALL'")
            restored = settings(con, warehouse)
            print("Restored warehouse:", json.dumps(restored, default=str))
            if restored["size"] != "X-Small":
                raise RuntimeError("Declared-size comparison did not restore X-Small")


def usage(con, record):
    run_id = record["run_id"]
    cur = con.cursor()
    cur.execute(
        "SELECT COUNT(*), SUM(TOTAL_ELAPSED_TIME)/1000.0 "
        "FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY "
        "WHERE START_TIME >= TO_TIMESTAMP_TZ(%s) "
        "AND TRY_PARSE_JSON(QUERY_TAG):run_id::STRING = %s", (record["started_at"], run_id),
    )
    count, elapsed = cur.fetchone()
    source = "ACCOUNT_USAGE"
    if not count:
        cur.execute(
            "SELECT QUERY_TAG,TOTAL_ELAPSED_TIME FROM TABLE(INFORMATION_SCHEMA.QUERY_HISTORY_BY_WAREHOUSE("
            "WAREHOUSE_NAME=>%s, END_TIME_RANGE_START=>TO_TIMESTAMP_LTZ(%s), RESULT_LIMIT=>10000))",
            (record["warehouse"], record["started_at"]),
        )
        rows = cur.fetchall()
        if len(rows) == 10000:
            raise RuntimeError("Information-schema history may be truncated")
        matched = []
        for tag, milliseconds in rows:
            try:
                if json.loads(tag).get("run_id") == run_id:
                    matched.append(milliseconds)
            except (ValueError, AttributeError, TypeError):
                continue
        count, elapsed = len(matched), sum(matched) / 1000 if matched else None
        source = "INFORMATION_SCHEMA"
    cur.execute(
        "SELECT COUNT(*), SUM(CREDITS_ATTRIBUTED_COMPUTE + COALESCE(CREDITS_USED_QUERY_ACCELERATION,0)) "
        "FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_ATTRIBUTION_HISTORY "
        "WHERE START_TIME >= TO_TIMESTAMP_TZ(%s) "
        "AND TRY_PARSE_JSON(QUERY_TAG):run_id::STRING = %s", (record["started_at"], run_id),
    )
    attributed_count, credits = cur.fetchone()
    return count or "pending", elapsed if count else "pending", credits if attributed_count else "pending", source


def report(args, con):
    print("| warehouse | label | size | auto-suspend | QAS | queries | elapsed s (sum) | wall s | credits |")
    print("|---|---|---|---|---|---|---|---|---|")
    sources = []
    for record in json.loads(args.results.read_text()) if args.results.exists() else []:
        count, elapsed, credits, source = usage(con, record)
        s = record["settings"]
        values = [record["warehouse"], record["label"], s["size"], s["auto_suspend"],
                  s["enable_query_acceleration"], count, elapsed, round(record["wall_seconds"], 3), credits]
        print("| " + " | ".join(str(value) for value in values) + " |")
        sources.append(f"{record['run_id']}: {source}; status={record['status']}")
    print("\nQuery-history sources (credits always ACCOUNT_USAGE.QUERY_ATTRIBUTION_HISTORY):")
    print("\n".join(sources) or "No recorded runs.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--workload", choices=WORKLOADS, required=True)
    run_parser.add_argument("--label", choices=("before", "after", "declared"), required=True)
    run_parser.add_argument("--code-root", type=Path, required=True, help="Pipeline branch git worktree")
    sub.add_parser("report")
    args = parser.parse_args()
    with credentials() as key:
        con = connect(getattr(args, "workload", "doc_usage_dashboard"), key)
        try:
            run(args, con) if args.command == "run" else report(args, con)
        finally:
            con.close()


if __name__ == "__main__":
    main()
