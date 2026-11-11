#!/usr/bin/env python3
"""Recompute the batch baseline from the compressed event logs."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from eventlog import read_events


ROOT = Path(__file__).resolve().parent


def utc(milliseconds):
    return datetime.fromtimestamp(milliseconds / 1000, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def number(value):
    try:
        return int(str(value).replace(",", ""))
    except (ValueError, TypeError):
        return None


def summarize(events):
    application = None
    end = None
    executors = {}
    failed_tasks = memory_spill = disk_spill = 0
    file_metric_ids = set()
    accumulator_values = {}

    def accumulators(node):
        if isinstance(node, dict):
            name = node.get("Name", node.get("name", ""))
            identity = node.get("ID", node.get("Accumulator ID", node.get("accumulatorId")))
            if identity is not None:
                identity = str(identity)
                if name == "number of written files":
                    file_metric_ids.add(identity)
                value = number(node.get("Value", node.get("value")))
                if value is not None:
                    accumulator_values[identity] = max(value, accumulator_values.get(identity, 0))
            for child in node.values():
                accumulators(child)
        elif isinstance(node, list):
            for child in node:
                accumulators(child)

    for event in events:
        kind = event.get("Event", "")
        if kind == "SparkListenerApplicationStart":
            application = event
        elif kind == "SparkListenerApplicationEnd":
            end = event["Timestamp"]
        elif kind == "SparkListenerExecutorAdded" and event["Executor ID"] != "driver":
            executors.setdefault(str(event["Executor ID"]), {
                "start": event["Timestamp"], "end": None,
                "cores": event["Executor Info"]["Total Cores"],
            })
        elif kind == "SparkListenerExecutorRemoved":
            identity = str(event["Executor ID"])
            if identity in executors:
                executors[identity]["end"] = event["Timestamp"]
        elif kind == "SparkListenerTaskEnd":
            reason = event.get("Task End Reason", {}).get("Reason", "Success")
            info = event.get("Task Info", {})
            if info.get("Failed") or reason not in ("Success", "TaskKilled"):
                failed_tasks += 1
            metrics = event.get("Task Metrics", {})
            memory_spill += metrics.get("Memory Bytes Spilled", 0)
            disk_spill += metrics.get("Disk Bytes Spilled", 0)
        if kind.endswith("SparkListenerDriverAccumUpdates"):
            for identity, value in event.get("accumUpdates", []):
                value = number(value)
                if value is not None:
                    identity = str(identity)
                    accumulator_values[identity] = max(value, accumulator_values.get(identity, 0))
        accumulators(event)

    if application is None or end is None:
        raise ValueError("Event log must contain application start and end")
    start = application["Timestamp"]
    if end < start:
        raise ValueError("Application end precedes start")
    executor_ms = core_ms = 0
    for executor in executors.values():
        duration = max(0, min(executor["end"] if executor["end"] is not None else end, end) - max(executor["start"], start))
        executor_ms += duration
        core_ms += duration * executor["cores"]
    output_files = [accumulator_values[identity] for identity in file_metric_ids if identity in accumulator_values]
    return application["App Name"], {
        "app_id": application["App ID"],
        "start": utc(start), "end": utc(end),
        "runtime_seconds": round((end - start) / 1000, 6),
        "executor_count": len(executors),
        "executor_hours": round(executor_ms / 3600000, 9),
        "core_hours": round(core_ms / 3600000, 9),
        "failed_tasks": failed_tasks,
        "memory_bytes_spilled": memory_spill,
        "disk_bytes_spilled": disk_spill,
        "output_files_written": sum(output_files) if output_files else None,
    }


def compute(directory, expected_jobs):
    jobs = {}
    for path in sorted(directory.glob("*.zstd")):
        name, summary = summarize(read_events(path))
        if name in jobs:
            raise ValueError(f"More than one application for {name}")
        if path.name != summary["app_id"] + ".zstd":
            raise ValueError(f"Filename does not match application id: {path.name}")
        jobs[name] = summary
    if set(jobs) != set(expected_jobs):
        raise ValueError(f"Job inventory differs: missing={sorted(set(expected_jobs) - set(jobs))}, extra={sorted(set(jobs) - set(expected_jobs))}")
    jobs = {name: jobs[name] for name in expected_jobs}
    totals = {"applications": len(jobs)}
    for field in ("runtime_seconds", "executor_count", "executor_hours", "core_hours",
                  "failed_tasks", "memory_bytes_spilled", "disk_bytes_spilled"):
        value = sum(job[field] for job in jobs.values())
        totals[field] = round(value, 9) if isinstance(value, float) else value
    totals["output_files_written"] = sum(job["output_files_written"] or 0 for job in jobs.values())
    totals["jobs_with_output_file_metrics"] = sum(job["output_files_written"] is not None for job in jobs.values())
    return {
        "generated_from": "eventlogs/*.zstd; Spark listener events; executor lifetimes capped at application end; task metrics include failed attempts; output files use final SQL accumulator values where present",
        "jobs": jobs,
        "totals": totals,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-dir", type=Path, default=ROOT / "eventlogs")
    parser.add_argument("--output", type=Path, default=ROOT / "baseline.json")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        expected_jobs = (ROOT.parent / "jobs.txt").read_text().splitlines()
        baseline = compute(args.log_dir, expected_jobs)
        if args.check:
            if not args.output.exists() or json.loads(args.output.read_text()) != baseline:
                print("Baseline differs from event logs; run compute_baseline.py", file=sys.stderr)
                return 1
            print(f"Baseline matches {len(baseline['jobs'])} applications.")
        else:
            args.output.write_text(json.dumps(baseline, indent=2) + "\n")
            print(f"Wrote {args.output}: {len(baseline['jobs'])} applications.")
    except (ValueError, OSError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
