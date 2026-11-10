#!/usr/bin/env python3
"""Comparable run evidence from History Server and tagged Snowflake queries."""
import argparse
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sys
from urllib.parse import quote
from urllib.request import urlopen
import zipfile

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "history"))
from compute_baseline import summarize
from eventlog import decompress


def spark_measure(app, history="http://localhost:18080"):
    url = history.rstrip("/") + "/api/v1/applications/" + quote(app, safe="")
    # History Server endpoint is operator-supplied, not application/request input.
    # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
    with urlopen(url, timeout=60) as response:
        application = json.load(response)
    if not application["attempts"][0]["completed"]:
        raise ValueError("Application must be completed")
    # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
    with urlopen(url + "/logs", timeout=120) as response:
        archive = zipfile.ZipFile(io.BytesIO(response.read()))
    names = sorted(name for name in archive.namelist() if name.endswith(".zstd"))
    if not names:
        raise ValueError("No zstd event logs in History Server REST archive")
    events = (json.loads(line) for name in names for line in decompress(archive.read(name)).splitlines() if line)
    job, metrics = summarize(events)
    return {"engine": "spark", "job": job, "source": url, **metrics}


def busy_hours(intervals):
    end = None
    seconds = 0.0
    for start, stop in sorted(intervals):
        if stop < start:
            raise ValueError("Query end precedes start")
        seconds += max(0, (stop - max(start, end or start)).total_seconds())
        end = max(stop, end or stop)
    return seconds / 3600


def snowflake_metrics(rows, job):
    if not rows:
        raise ValueError(f"No tagged queries found for {job}")
    warehouses = {}
    for row in rows:
        if row["WAREHOUSE_NAME"]:
            warehouses.setdefault(row["WAREHOUSE_NAME"], []).append(row)
    warehouse_metrics = []
    for name, queries in sorted(warehouses.items()):
        warehouse_metrics.append({
            "warehouse": name, "sizes": sorted({row["WAREHOUSE_SIZE"] for row in queries if row["WAREHOUSE_SIZE"]}),
            "busy_hours": busy_hours([(row["START_TIME"], row["END_TIME"]) for row in queries if row["WAREHOUSE_SIZE"]]),
        })
    start = min(row["START_TIME"] for row in rows)
    end = max(row["END_TIME"] for row in rows)
    return {
        "engine": "snowflake", "job": job, "start": start.isoformat(), "end": end.isoformat(),
        "runtime_seconds": (end - start).total_seconds(),
        "summed_execution_seconds": sum(row["EXECUTION_TIME"] or 0 for row in rows) / 1000,
        "warehouse_busy_hours": sum(row["busy_hours"] for row in warehouse_metrics),
        "warehouses": warehouse_metrics, "queries": len(rows),
        "failed_queries": sum(row["EXECUTION_STATUS"] != "SUCCESS" for row in rows),
        "compute_definition": "Union of query start/end intervals per warehouse where history reports a warehouse size; metadata/cache-only queries do not use warehouse compute. Not billed hours or credits; ACCOUNT_USAGE credits arrive later.",
    }


def snowflake_measure(job, since):
    start = datetime.fromisoformat(since.replace("Z", "+00:00"))
    if start.tzinfo is None:
        raise ValueError("--since must include a timezone")
    sys.path.insert(0, str(ROOT.parents[1] / "warehouse/snowflake"))
    from sfx_conn import connect

    with connect("ops", "spark-measure", job="_measure") as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT QUERY_ID, QUERY_TAG, WAREHOUSE_NAME, WAREHOUSE_SIZE,
                       START_TIME, END_TIME, EXECUTION_TIME, EXECUTION_STATUS
                FROM TABLE(INFORMATION_SCHEMA.QUERY_HISTORY(
                    END_TIME_RANGE_START => TO_TIMESTAMP_LTZ(%s), RESULT_LIMIT => 10000))
                ORDER BY START_TIME
            """, (start,))
            columns = [column[0] for column in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    if len(rows) == 10000:
        raise ValueError("Query history reached 10000-row limit; narrow --since")
    selected = []
    for row in rows:
        try:
            tag = json.loads(row["QUERY_TAG"] or "{}")
        except (ValueError, TypeError):
            continue
        if isinstance(tag, dict) and tag.get("run") == "sfx-d1110" and tag.get("act") == "spark" and tag.get("job") == job:
            if row["START_TIME"] >= start and row["END_TIME"] is not None:
                selected.append(row)
    return snowflake_metrics(selected, job)


def compare(before, after):
    metrics = ["runtime_seconds", "executor_hours", "core_hours", "warehouse_busy_hours",
               "summed_execution_seconds", "failed_tasks", "memory_bytes_spilled",
               "disk_bytes_spilled", "output_files_written"]
    def display(value):
        return "N/A" if value is None else str(value)
    lines = ["| Metric | Before | After |", "|---|---:|---:|",
             f"| Job | {before['job']} | {after['job']} |"]
    for metric in metrics:
        if metric in before or metric in after:
            lines.append(f"| {metric} | {display(before.get(metric))} | {display(after.get(metric))} |")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="engine", required=True)
    spark = commands.add_parser("spark")
    spark.add_argument("--app", required=True)
    spark.add_argument("--history", default="http://localhost:18080")
    snowflake = commands.add_parser("snowflake")
    snowflake.add_argument("--job", required=True)
    snowflake.add_argument("--since", required=True)
    comparison = commands.add_parser("compare")
    comparison.add_argument("--before", type=Path, required=True)
    comparison.add_argument("--after", type=Path, required=True)
    args = parser.parse_args()
    if args.engine == "compare":
        print(compare(json.loads(args.before.read_text()), json.loads(args.after.read_text())))
    else:
        result = spark_measure(args.app, args.history) if args.engine == "spark" else snowflake_measure(args.job, args.since)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
