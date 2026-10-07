"""Byte-preserving port of parse_custbill_fixedwidth.sh (CBCUST01).

Legacy contract, including intentionally unvalidated records:
* Host otterworks-etl-prod-01 uses /data/otterworks; otterworks-etl-uat
  uses /data2/otterworks_uat; others use OTTERWORKS_LEGACY_ROOT, with an
  unset/empty value falling back to /tmp/otterworks-legacy.
* Touch /tmp/parse_custbill.lock, never remove it. If it is already a file,
  print "parse lock exists, probably stale, proceeding" and continue.
  CUSTBILL_LOCK_DIR redirects the lock for tests; touch errors are swallowed.
* Create parsed/ even on a fresh root; do not create incoming/. Process only
  regular incoming/CUSTBILL*.dat files (including symlinks to files) in C
  locale byte-sorted glob order. Leave other names and directories alone.
* For each input, remove lines starting with HDR or TRL, slice bytes 1-10,
  11-40, 41-48, 49-60, 61-63 and 64-65, and join with pipes. Embedded pipes
  are not escaped: awk splits them again and can produce more than six fields.
  Trim trailing ASCII spaces only in fields 1, 2 and 5 (not leading spaces,
  tabs, date or record type). Convert field 4 using awk's numeric prefix,
  divide that float by 100, and format %.2f. Reformat field 3 by substrings
  YYYY-MM-DD without validating it; short/empty records still produce rows.
  Preserve CR bytes and arbitrary non-UTF-8 bytes; ignore bytes beyond 65.
  Emit a newline per body record, including an unterminated last record.
* Overwrite parsed/<basename-without-.dat>.psv, with no header. Count its
  nonempty lines using grep -c .; trailer text is every TRL line's bytes
  4-13 with leading zeroes removed, joined with newlines. Empty trailer
  text (including all-zero counts) is "?". Counts are only logged, never
  reconciled. Rename input to <input>.done even after a failed parse,
  replacing an existing file (or moving inside an existing .done directory).
* stdout: bare-date stamp plus " parse_custbill starting", then stamp plus
  " parsed <basename>: <count> records (trailer says <text>)" per input,
  then stamp plus " parse_custbill done". Stamp is date(1)'s format, e.g.
  Thu Jan 15 00:00:00 UTC 2026 (not Perl localtime); every read uses
  custbill_common.now_epoch() so CUSTBILL_NOW freezes it.
* Normally stderr is empty. mkdir, touch, sed, output grep, awk and mv
  errors are suppressed; partial failures still finish with exit code 0.
  Bash output-redirection failures still print the legacy script's line-59
  diagnostic; unreadable output gives an empty count (a directory gives 0).
  Input grep errors and binary-trailer warnings are not suppressed. GNU grep
  treats NUL as a line boundary for counts and suppresses binary trailer text.
  Signed inf/nan are accepted by awk; unsigned words become zero, negative
  zero is cleared by +0, and non-finite formatting includes its sign.
  The legacy uses /tmp/cb_body.$$ and removes it after each input; this port
  uses in-memory bytes instead (the explicitly allowed scratch deviation).
* No sleeps, polling passes, retries, archive writes or input validation.
  Only parsed outputs, .done renames, parsed/ and the retained lock change.
* Legacy path expansions are unquoted: split on shell whitespace and expand
  globs again in command arguments. A matching filename containing spaces
  can produce basename/grep errors, an empty .psv, and remain unrenamed.
"""

from __future__ import annotations

import glob
import math
import os
import re
import sys
from pathlib import Path

import custbill_common as cc

_NUMBER = re.compile(
    rb"[ \t\r\v\f]*([+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)"
    rb"(?:[eE][+-]?[0-9]+)?|[+-](?:inf(?:inity)?|nan))", re.IGNORECASE
)
_COLUMNS = ((0, 10), (10, 40), (40, 48), (48, 60), (60, 63), (63, 65))
_LEGACY_SCRIPT = Path(__file__).resolve().parents[1] / "jobs/parse_custbill_fixedwidth.sh"


def _lines(data: bytes) -> list[bytes]:
    if not data:
        return []
    lines = data.split(b"\n")
    return lines[:-1] if data.endswith(b"\n") else lines


def _shell_words(value: str) -> list[Path]:
    paths = []
    for word in re.split(r"[ \t\n]+", value.strip(" \t\n")):
        if word:
            paths.extend(Path(p) for p in sorted(glob.glob(word), key=os.fsencode) or [word])
    return paths


def _basename(path: Path) -> str:
    words = [str(p) for p in _shell_words(str(path))] + [".dat"]
    if len(words) > 2:
        print(f"basename: extra operand '{words[2]}'\nTry 'basename --help' for more information.",
              file=sys.stderr)
        return ""
    name = Path(words[0]).name
    return (name[:-4] if name.endswith(".dat") and name != ".dat" else name).rstrip("\n")


def _amount(field: bytes) -> bytes:
    match = _NUMBER.match(field)
    token = match[1] if match else b"0"
    value = (float(token) + 0.0) / 100
    if not math.isfinite(value):
        sign = b"-" if token.startswith(b"-") else b"+"
        return sign + (b"nan" if math.isnan(value) else b"inf")
    return ("%.2f" % value).encode("ascii")


def _parse(data: bytes) -> bytes:
    rows = []
    for line in _lines(data):
        if line.startswith((b"HDR", b"TRL")):
            continue
        fields = b"|".join(line[start:end] for start, end in _COLUMNS).split(b"|")
        for index in (0, 1, 4):
            fields[index] = fields[index].rstrip(b" ")
        fields[3] = _amount(fields[3])
        date = fields[2]
        fields[2] = date[:4] + b"-" + date[4:6] + b"-" + date[6:8]
        rows.append(b"|".join(fields) + b"\n")
    return b"".join(rows)


def _log(message: str) -> None:
    print(f"{cc.date_cmd_stamp(cc.now_epoch())} {message}")


def _count(path: Path) -> str:
    paths = _shell_words(str(path))
    counts = []
    for item in paths:
        try:
            count = str(sum(bool(line) for line in re.split(rb"[\n\x00]", item.read_bytes())))
        except IsADirectoryError:
            count = "0"
        except OSError:
            continue
        counts.append(f"{item}:{count}" if len(paths) > 1 else count)
    return "\n".join(counts)


def _trailer(path: Path) -> str:
    paths = _shell_words(str(path))
    trailers = []
    for item in paths:
        try:
            data = item.read_bytes()
        except OSError as error:
            print(f"grep: {item}: {error.strerror}", file=sys.stderr)
            continue
        matches = [line for line in re.split(rb"[\n\x00]", data) if line.startswith(b"TRL")]
        if matches and b"\x00" in data:
            print(f"grep: {item}: binary file matches", file=sys.stderr)
            continue
        prefix = os.fsencode(item) + b":" if len(paths) > 1 else b""
        trailers.extend(prefix + line for line in matches)
    text = b"\n".join(line[3:13].lstrip(b"0") for line in trailers).rstrip(b"\n")
    return os.fsdecode(text) or "?"


def _move(path: Path) -> None:
    words = _shell_words(str(path)) + _shell_words(str(path) + ".done")
    if len(words) < 2:
        return
    destination = words[-1]
    if len(words) > 2 and not destination.is_dir():
        return
    for source in words[:-1]:
        target = destination / source.name if destination.is_dir() else destination
        try:
            source.rename(target)
        except OSError:
            pass


def main() -> int:
    root = cc.legacy_root()
    cc.check_and_touch_lock(cc.lock_path("parse_custbill.lock"),
                            "parse lock exists, probably stale, proceeding")
    parsed = root / "parsed"
    for directory in _shell_words(str(parsed)):
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
    _log("parse_custbill starting")
    for path in _shell_words(str(root / "incoming/CUSTBILL*.dat")):
        if not path.is_file():
            continue
        basename = _basename(path)
        out = parsed / f"{basename}.psv"
        data = []
        for source in _shell_words(str(path)):
            try:
                data.extend(_lines(source.read_bytes()))
            except OSError:
                pass
        outputs = _shell_words(str(out))
        if len(outputs) != 1:
            print(f"{_LEGACY_SCRIPT}: line 59: $out: ambiguous redirect", file=sys.stderr)
        else:
            try:
                outputs[0].write_bytes(_parse(b"".join(line + b"\n" for line in data)))
            except OSError as error:
                print(f"{_LEGACY_SCRIPT}: line 59: {out}: {error.strerror}", file=sys.stderr)
        _log(f"parsed {basename}: {_count(out)} records (trailer says {_trailer(path)})")
        _move(path)
    _log("parse_custbill done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
