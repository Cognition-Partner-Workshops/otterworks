"""Byte-identical port of jobs/sftp_ingest_poll.ksh (including its quirks).

* Host otterworks-etl-prod-01 uses /data/otterworks and
  /sftp/mainframe/upload; otterworks-etl-uat uses /data2/otterworks_uat and
  /sftp_uat/mainframe/upload. Other hosts use OTTERWORKS_LEGACY_ROOT, or
  /tmp/otterworks-legacy when unset/empty, and ROOT/sftp-drop/upload.
* Touch /tmp/sftp_ingest.lock, never remove it. A regular-file lock prints
  "lock file present, another ingest may be running, continuing anyway"
  before running anyway. CUSTBILL_LOCK_DIR redirects this in tests.
* Create incoming/, archive/, and the drop directory (including parents),
  swallowing mkdir and lock-touch errors. No temporary files are created.
* Three passes glob drop/CUSTBILL*.dat in C-locale byte order. Ignore
  nonmatching names, directories and dangling symlinks; follow file symlinks.
  Re-glob each pass so newly arriving files can be picked up.
* Preserve unquoted shell word splitting and globbing in mkdir, the drop
  glob, basename, cp and rm. Whitespace in names can truncate basename or
  make copies/removal fail, leaving the file to be retried three times.
  basename errors are unsuppressed. wc redirections do not split/glob.
* Count bytes, sleep 1 second, count again. Unequal counts print
  "DATE BASENAME still growing, skipping this pass"; retry on later passes.
  Equal sizes (even empty files or same-size rewrites) are deemed settled.
* Independently copy the settled file to incoming/BASENAME (overwrite) and
  archive/BASENAME.YYYYMMDDHHMMSS (overwrite), then unlink the drop entry.
  cp/rm errors are swallowed; failed copies do not prevent deletion or the
  "DATE ingested BASENAME (COUNT bytes)" line. COUNT reads incoming, so a
  failed overwrite can report stale bytes; failed reads yield an empty COUNT.
* Sleep 2 seconds after passes one and two, even with no files; no sleep
  after pass three. Polling/settle timings are not optimized away.
* Stdout starts with "DATE sftp_ingest_poll starting, drop=DROP" (after any
  lock warning), followed by growing/ingested lines in processing order,
  then "DATE sftp_ingest_poll done". Each line has a trailing newline.
  DATE is bare date's C-locale format, e.g. Thu Jan 15 00:00:00 UTC 2026,
  not Perl localtime. All clock reads use custbill_common.now_epoch(),
  allowing CUSTBILL_NOW to freeze both DATE and the archive suffix.
* Stderr is normally empty. Failed wc input redirections still emit ksh's
  path/line diagnostic (redirection occurs before 2>/dev/null); the final
  incoming wc is also unsuppressed (a directory reports 0 bytes and
  "wc: 'standard input': Is a directory"). File-operation failures otherwise stay
  silent. Exit 0 even with partial failures; leave the lock in place.
"""

from __future__ import annotations

import glob
import os
import re
import shutil
import sys
import time
from pathlib import Path

import custbill_common as cc


def drop_directory(profile: str, root: Path) -> Path:
    if profile == "prod":
        return Path("/sftp/mainframe/upload")
    if profile == "uat":
        return Path("/sftp_uat/mainframe/upload")
    return root / "sftp-drop" / "upload"


def _stamp() -> str:
    return cc.date_cmd_stamp(cc.now_epoch())


def _shell_words(value: str) -> list[Path]:
    words = []
    for word in re.findall(r"[^ \t\n]+", value):
        words.extend(Path(p) for p in sorted(glob.glob(word), key=os.fsencode) or [word])
    return words


def _basename(source: Path) -> str:
    words = _shell_words(str(source))
    if len(words) > 2:
        print(f"basename: extra operand '{words[2]}'", file=sys.stderr)
        print("Try 'basename --help' for more information.", file=sys.stderr)
        return ""
    name = words[0].name
    if len(words) == 2:
        suffix = str(words[1])
        if suffix != name and name.endswith(suffix):
            name = name[:-len(suffix)]
    return name


def _byte_count(path: Path, line: int, suppress_read_error: bool = False) -> str:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError as exc:
        legacy = Path(__file__).resolve().parent.parent / "jobs" / "sftp_ingest_poll.ksh"
        print(f"{legacy}[{line}]: {path}: cannot open [{exc.strerror}]", file=sys.stderr)
        return ""
    count = 0
    try:
        while chunk := os.read(fd, 1024 * 1024):
            count += len(chunk)
    except OSError as exc:
        if not suppress_read_error:
            print(f"wc: 'standard input': {exc.strerror}", file=sys.stderr)
    finally:
        os.close(fd)
    return str(count)


def _copy_file(source: Path, destination: Path) -> None:
    try:
        if destination.is_dir():
            destination /= source.name
        if destination.is_symlink() and not destination.exists():
            return
        shutil.copyfile(source, destination)
    except OSError:
        pass


def _copy(source: Path, destination: Path) -> None:
    words = _shell_words(str(source)) + _shell_words(str(destination))
    try:
        if len(words) < 2 or (len(words) > 2 and not words[-1].is_dir()):
            return
    except OSError:
        return
    for source_word in words[:-1]:
        _copy_file(source_word, words[-1])


def _is_file(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        return False


def main() -> int:
    profile = cc.host_profile()
    root = cc.legacy_root(profile)
    drop = drop_directory(profile, root)
    incoming = root / "incoming"
    archive = root / "archive"
    try:
        cc.check_and_touch_lock(
            cc.lock_path("sftp_ingest.lock"),
            "lock file present, another ingest may be running, continuing anyway",
        )
    except OSError:
        pass
    directories = _shell_words(str(incoming)) + _shell_words(str(archive)) + _shell_words(str(drop))
    for directory in directories:
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
    print(f"{_stamp()} sftp_ingest_poll starting, drop={drop}")
    for poll in range(3):
        for source in _shell_words(str(drop / "CUSTBILL*.dat")):
            if not _is_file(source):
                continue
            name = _basename(source)
            before = _byte_count(source, 51, suppress_read_error=True)
            time.sleep(1)
            after = _byte_count(source, 53, suppress_read_error=True)
            if before != after:
                print(f"{_stamp()} {name} still growing, skipping this pass")
                continue
            _copy(source, incoming / name)
            suffix = time.strftime("%Y%m%d%H%M%S", time.localtime(cc.now_epoch()))
            _copy(source, archive / (name + "." + suffix))
            for word in _shell_words(str(source)):
                try:
                    word.unlink()
                except OSError:
                    pass
            stamp = _stamp()
            count = _byte_count(incoming / name, 61)
            print(f"{stamp} ingested {name} ({count} bytes)")
        if poll < 2:
            time.sleep(2)
    print(f"{_stamp()} sftp_ingest_poll done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
