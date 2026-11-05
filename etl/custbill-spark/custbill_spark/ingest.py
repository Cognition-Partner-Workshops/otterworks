"""Stage 1: drop -> incoming (+archive). Replaces jobs/sftp_ingest_poll.ksh.

Completion is decided by file structure (a TRL trailer or a .sha256 manifest),
not by three one-second size samples; files that are not complete stay in the
drop for the next run instead of being staged half-written.
"""

import logging
import os
import shutil
import time

from .config import FILE_GLOB
from .support import purge_older_than, sha256, split_lines, stage_lock, write_atomic, write_ledger

log = logging.getLogger("custbill_spark.ingest")


def completeness(name, data, drop):
    """Return None when the file is complete, otherwise the reason it is not."""
    if name.endswith((".part", ".tmp", ".filepart")):
        return "upload in progress (partial suffix)"
    manifest = drop / f"{name}.sha256"
    if manifest.exists():
        expected = manifest.read_text().split()[0].lower() if manifest.read_text().split() else ""
        return None if expected == sha256(data) else "sha256 manifest mismatch"
    lines = split_lines(data)
    if not lines:
        return None  # an empty file is a complete, empty feed (legacy staged it too)
    if not lines[0].startswith("HDR"):
        return "missing HDR record"
    if not lines[-1].startswith("TRL"):
        return "missing TRL record (upload still in progress?)"
    return None


def run(settings, spark=None):
    with stage_lock(settings, "ingest"):
        return _run(settings, spark)


def _run(settings, spark):
    for directory in (settings.drop, settings.incoming, settings.archive):
        directory.mkdir(parents=True, exist_ok=True)
    candidates = sorted(p for p in settings.drop.glob(FILE_GLOB) if p.is_file())
    files = {}
    if spark is not None and candidates:
        from .support import read_file_lines
        rows = (read_file_lines(spark, candidates)
                .map(lambda row: (row[0], 1)).reduceByKey(lambda a, b: a + b).collect())
        files = dict(rows)
    stamp = time.strftime("%Y%m%d%H%M%S")
    staged, deferred, failed = [], [], []
    for source in candidates:
        try:
            data = source.read_bytes()
            reason = completeness(source.name, data, settings.drop)
            if reason:
                deferred.append({"file": source.name, "reason": reason})
                log.warning("deferring %s: %s", source.name, reason)
                continue
            target = settings.incoming / source.name
            write_atomic(target, data)
            shutil.copystat(source, target)
            archived = settings.archive / f"{source.name}.{stamp}"
            write_atomic(archived, data)
            os.remove(source)
            manifest = settings.drop / f"{source.name}.sha256"
            if manifest.exists():
                manifest.unlink()
            staged.append({"file": source.name, "bytes": len(data), "sha256": sha256(data),
                           "lines": files.get(source.name, len(split_lines(data))),
                           "archived_as": archived.name})
            log.info("staged %s (%d bytes)", source.name, len(data))
        except OSError as exc:
            failed.append({"file": source.name, "error": str(exc)})
            log.error("failed to stage %s: %s", source.name, exc)
    purged = purge_older_than(settings.archive, "CUSTBILL*", settings.archive_retention_days)
    ledger = {"staged": staged, "deferred": deferred, "failed": failed, "archive_purged": purged,
              "drop": str(settings.drop)}
    write_ledger(settings, "ingest", stamp, ledger)
    if failed:
        raise RuntimeError(f"ingest: {len(failed)} file(s) could not be staged")
    return ledger
