"""Land CUSTBILL*.dat into the governed volume, atomically and idempotently.

Replaces the write half of etl/legacy-extra/jobs/sftp_ingest_poll.ksh:

    s1=`wc -c < $f`; sleep 1; s2=`wc -c < $f`
    if [ "$s1" != "$s2" ]; then ... skipping this pass; fi
    cp $f $INCOMING/$b 2>/dev/null || true
    cp $f $ARCHIVE/$b.`date +%Y%m%d%H%M%S` 2>/dev/null || true
    rm $f 2>/dev/null || true

Four things about that are load-bearing, and three of them are reproduced:

* the double size check is a guess, not a handshake. A producer that pauses for
  more than a second between writes passes it, and the parser five minutes later
  reads a half-written file. Here the landing write is a single object PUT, so a
  record is visible only once the whole file is (**P2-D01 — the one accepted
  behaviour change in pipeline 2**).
* the archive copy is kept: the landing volume is the archive.
* the delete is not. Nothing removes the producer's file; re-landing an already
  landed file is a no-op, which is what makes the task re-runnable.
* `2>/dev/null || true` is not kept. A failed landing fails the task.

Usage:
    python3 land_custbill_files.py --source-dir <dir> [--landing-path /Volumes/...] [--dry-run]
"""

from __future__ import annotations

import argparse
import fnmatch
import io
import json
import os
import sys

DEFAULT_LANDING = "/Volumes/ow_tp/bronze/landing/custbill"
FILE_GLOB = "CUSTBILL*.dat"


def _client():
    from databricks.sdk import WorkspaceClient

    return WorkspaceClient()


def _already_landed(w, landing_path: str) -> dict[str, int]:
    """name -> size for what is already in the landing volume."""
    from databricks.sdk.errors import NotFound

    landed: dict[str, int] = {}
    try:
        for entry in w.files.list_directory_contents(landing_path):
            if entry.is_directory:
                continue
            landed[os.path.basename(entry.path)] = entry.file_size or 0
    except NotFound:
        # First landing into this volume. Any other error is fatal: an unreadable
        # landing directory must not be mistaken for an empty one.
        w.files.create_directory(landing_path)
    return landed


def land(source_dir: str, landing_path: str = DEFAULT_LANDING, dry_run: bool = False) -> dict:
    w = None if dry_run else _client()
    landed = {} if dry_run else _already_landed(w, landing_path)

    result = {"landing_path": landing_path, "landed": [], "skipped": [], "conflicts": []}
    for name in sorted(os.listdir(source_dir)):
        if not fnmatch.fnmatch(name, FILE_GLOB):
            continue
        local = os.path.join(source_dir, name)
        if not os.path.isfile(local):
            continue
        size = os.path.getsize(local)

        if name in landed:
            if landed[name] == size:
                # Already landed, same bytes: the legacy would have re-copied and
                # re-archived it under a new timestamp. Skipping is what makes the
                # task re-runnable, and Auto Loader would ignore the duplicate anyway.
                result["skipped"].append({"file": name, "bytes": size})
                continue
            # Same name, different length. Never silently overwrite: the landed
            # copy is what bronze was built from.
            result["conflicts"].append({"file": name, "landed_bytes": landed[name], "source_bytes": size})
            continue

        if dry_run:
            result["landed"].append({"file": name, "bytes": size, "dry_run": True})
            continue

        with open(local, "rb") as fh:
            payload = fh.read()
        # One PUT. On object-storage-backed volumes the object becomes visible
        # only when the write completes, so no reader can see a partial file.
        w.files.upload(f"{landing_path}/{name}", io.BytesIO(payload), overwrite=False)
        result["landed"].append({"file": name, "bytes": size})

    if result["conflicts"]:
        raise SystemExit(
            "landing conflict, nothing overwritten: "
            + json.dumps(result["conflicts"])
        )
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source-dir", required=True)
    ap.add_argument("--landing-path", default=DEFAULT_LANDING)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    result = land(args.source_dir, args.landing_path, args.dry_run)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
