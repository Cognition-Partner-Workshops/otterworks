"""Publication rules for the converted transcript set.

A transcript directory is only gradable while its manifest says so. The manifest is written
last, names the run that produced it, and carries a digest of every transcript in the set, so
three things become impossible: grading a set no run published, grading a set an interrupted
run left half-written, and grading a file that was edited after it was recorded.

`mongo_record.py` invalidates the manifest before it records anything and republishes it only
after the whole selected scenario set came back; `mongo_parity.py` refuses to grade without
one that matches the files on disk.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import pathlib
import shutil
import sys

MANIFEST = "manifest.json"


def digest(record):
    return hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()


def invalidate(out):
    """Withdraw the current publication. Called before recording: from here until a run
    republishes, the transcripts on disk are not evidence of anything."""
    (pathlib.Path(out) / MANIFEST).unlink(missing_ok=True)


def _write(path, payload):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, path)


def publish(records, out, run_id, selection, expected_scenarios):
    """Stage the whole set, then move it into place and write the manifest last.

    `expected_scenarios` is what the selection asked for; a run that came back with anything
    else is a failed recording and publishes nothing.
    """
    out = pathlib.Path(out)
    recorded = sorted(record["scenario"] for record in records)
    if recorded != sorted(expected_scenarios):
        sys.exit(f"recorded {recorded} but the selection asked for "
                 f"{sorted(expected_scenarios)}; refusing to publish a partial set")

    staging = out.parent / f".{out.name}.{run_id}"
    shutil.rmtree(staging, ignore_errors=True)
    staged = []
    for record in records:
        path = staging / record["module"] / f"{record['scenario']}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        _write(path, record)
        staged.append((path, out / record["module"] / f"{record['scenario']}.json"))

    for source, destination in staged:
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, destination)
    shutil.rmtree(staging, ignore_errors=True)

    manifest = {
        "run_id": run_id,
        "recorded_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "selection": selection,
        "digests": {record["scenario"]: digest(record) for record in records},
    }
    _write(out / MANIFEST, manifest)
    return manifest


def published(root):
    """The transcripts of the last complete run, or an exit explaining why there are none."""
    root = pathlib.Path(root)
    path = root / MANIFEST
    if not path.exists():
        sys.exit(f"{path} is missing: no complete recording has been published, so there is "
                 "nothing to grade (run mongo_record.py)")
    manifest = json.loads(path.read_text())

    records = {}
    for transcript in sorted(root.glob("*/*.json")):
        payload = json.loads(transcript.read_text())
        name = payload["scenario"]
        expected = manifest["digests"].get(name)
        if expected is None:
            sys.exit(f"{transcript} is not part of published run {manifest['run_id']}; it is "
                     "left over from an earlier recording and would be graded as current")
        if digest(payload) != expected:
            sys.exit(f"{transcript} does not match the digest run {manifest['run_id']} "
                     "published for it")
        records[name] = payload

    missing = sorted(set(manifest["digests"]) - set(records))
    if missing:
        sys.exit(f"published run {manifest['run_id']} is incomplete on disk: {missing}")
    return manifest, records
