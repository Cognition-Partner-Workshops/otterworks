#!/usr/bin/env python3
"""Set one application's event-log date relative to the other applications."""
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re

from eventlog import read_events, write_events


TIME_FIELDS = {
    "timestamp", "submissiontime", "completiontime", "launchtime",
    "gettingresulttime", "finishtime", "starttime", "endtime", "time",
    "registrationtime", "requesttime",
    "spark.app.starttime", "spark.app.submittime",
}


def shift_value(value, offset, old_id, new_id, field=""):
    normalized = field.lower().replace(" ", "").replace("_", "")
    if isinstance(value, dict):
        return {key: shift_value(child, offset, old_id, new_id, key) for key, child in value.items()}
    if isinstance(value, list):
        return [shift_value(child, offset, old_id, new_id, field) for child in value]
    if normalized in TIME_FIELDS:
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 100000000000:
            return value + offset
        if isinstance(value, str) and value.isdigit() and int(value) >= 100000000000:
            return str(int(value) + offset)
    if isinstance(value, str):
        return value.replace(old_id, new_id)
    return value


def shift_log(path, reference, days):
    events = list(read_events(path))
    application = next(event for event in events if event["Event"] == "SparkListenerApplicationStart")
    start = datetime.fromtimestamp(application["Timestamp"] / 1000, timezone.utc)
    target_date = datetime.fromtimestamp(reference / 1000, timezone.utc).date() - timedelta(days=days)
    target = start.replace(year=target_date.year, month=target_date.month, day=target_date.day)
    offset = round((target - start).total_seconds() * 1000)
    old_id = application["App ID"]
    match = re.fullmatch(r"app-(\d{14})-(.+)", old_id)
    if not match:
        raise ValueError(f"Unsupported application id: {old_id}")
    stamp = datetime.strptime(match[1], "%Y%m%d%H%M%S") + timedelta(milliseconds=offset)
    new_id = f"app-{stamp:%Y%m%d%H%M%S}-{match[2]}"
    destination = path.with_name(new_id + ".zstd")
    if not offset:
        return path
    if destination != path and destination.exists():
        raise ValueError(f"Destination already exists: {destination}")
    temporary = destination.with_suffix(".zstd.tmp")
    write_events(temporary, [shift_value(event, offset, old_id, new_id) for event in events])
    temporary.replace(destination)
    if destination != path:
        path.unlink()
    return destination


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path, nargs="?", default=Path(__file__).resolve().parent / "eventlogs")
    parser.add_argument("--job", default="docs_folder_legacy_report")
    parser.add_argument("--days", type=int, default=118)
    args = parser.parse_args()
    applications = []
    for path in sorted(args.directory.glob("*.zstd")):
        application = next((event for event in read_events(path) if event["Event"] == "SparkListenerApplicationStart"), None)
        if application:
            applications.append((path, application))
    selected = [path for path, app in applications if app["App Name"] == args.job]
    others = [app["Timestamp"] for _, app in applications if app["App Name"] != args.job]
    if len(selected) != 1 or not others:
        parser.error("Expected one selected application and at least one other application")
    destination = shift_log(selected[0], max(others), args.days)
    print(f"{args.job}: {destination.name}")


if __name__ == "__main__":
    main()
