"""Locking, atomic writes, ledgers and the shared local SparkSession."""

from contextlib import contextmanager
import fcntl
import hashlib
import json
import logging
import os
from pathlib import Path
import time

log = logging.getLogger("custbill_spark")


class LockBusy(RuntimeError):
    """Another run holds the stage lock (max_active_runs=1)."""


@contextmanager
def stage_lock(settings, name):
    """Real mutual exclusion: flock is released by the kernel when the process dies."""
    path = settings.control / "locks" / f"{name}.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise LockBusy(f"{name}: lock {path} is held by another run") from exc
        handle.seek(0)
        handle.truncate()
        handle.write(f"{os.getpid()} {time.strftime('%Y-%m-%dT%H:%M:%S%z')}\n")
        handle.flush()
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def write_atomic(path, data):
    """Write bytes to a temp file beside the target and rename into place."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        with tmp.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def write_ledger(settings, stage, name, payload):
    path = settings.control / stage / f"{name}.json"
    payload = dict(payload, stage=stage, written_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    write_atomic(path, (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode())
    return path


def purge_older_than(directory, pattern, days):
    """Retention: remove matching files older than `days` (never a newer run's data)."""
    removed = []
    if days <= 0 or not directory.is_dir():
        return removed
    cutoff = time.time() - days * 86400
    for path in sorted(directory.glob(pattern)):
        if path.is_file() and path.stat().st_mtime < cutoff:
            path.unlink()
            removed.append(path.name)
    return removed


def split_lines(data):
    """Byte-transparent line split: decode latin-1 so every byte is one character.

    Mirrors sed/cut/awk in the C locale: CR is content, a trailing newline does
    not start an empty record, and a final unterminated line still counts.
    """
    text = data.decode("latin-1")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def encode_lines(lines):
    return "".join(line + "\n" for line in lines).encode("latin-1")


def build_session(settings, app_name):
    from pyspark.sql import SparkSession

    session = (SparkSession.builder.master(settings.spark_master).appName(app_name)
               .config("spark.ui.enabled", "false")
               .config("spark.sql.ansi.enabled", "false")
               .config("spark.sql.session.timeZone", "UTC")
               .config("spark.sql.shuffle.partitions", "4")
               .getOrCreate())
    session.sparkContext.setLogLevel("WARN")
    return session


def read_file_lines(spark, paths):
    """RDD of (file name, line index, line) for whole files, order preserved per file."""
    if not paths:
        return spark.sparkContext.emptyRDD()
    uris = ",".join(Path(p).resolve().as_uri() for p in paths)
    return spark.sparkContext.binaryFiles(uris).flatMap(
        lambda item: [(os.path.basename(item[0]), index, line)
                      for index, line in enumerate(split_lines(item[1]))])
