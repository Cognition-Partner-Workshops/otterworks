"""Python port of jobs/finance_excel_report.pl, byte-identical to the legacy job.

Observable behaviour of the legacy job, all reproduced here:

1. Root: hostname `otterworks-etl-prod-01` -> /data/otterworks (mail to
   finance-reports@otterworks.dev), `otterworks-etl-uat` ->
   /data2/otterworks_uat (mail to jake@otterworks.dev, which bounces), any
   other host -> $OTTERWORKS_LEGACY_ROOT, or /tmp/otterworks-legacy when that
   is unset or empty (mail to dev-null@localhost).
2. Lock /tmp/finance_report.lock (CUSTBILL_LOCK_DIR seam): if it is a regular
   file, stdout "finance report lock present, running anyway"; the run carries
   on. The lock is then (re)created empty with `open(L, ">$LOCKFILE")`, errors
   ignored, and never removed.
3. `mkdir -p $PARSED $REPORTS 2>/dev/null` through /bin/sh (word splitting
   included); failure is ignored.
4. stdout "<scalar(localtime)> finance_excel_report starting". Stamps are
   Perl's scalar(localtime) format, no zone ("Thu Jan 15 00:00:00 2026").
5. readdir(parsed): entries matching /^CUSTBILL.*\\.psv$/ (`.` excludes "\\n",
   `$` also matches before a final "\\n"), processed in Perl `sort` order
   (byte order). Opened with 2-arg open (trailing whitespace stripped from the
   name); a file that cannot be opened is skipped silently, a directory yields
   no lines. If parsed/ cannot be opened: die "cannot open $PARSED: $!" at
   line 43, exit code errno, stdout so far is still flushed.
6. Each line: chomp one "\\n", split on "|" into cust,name,dt,amt,ccy,rt
   (missing fields are ""). Lines with an empty cust are skipped. Totals keyed
   "ccy|rt": count += 1, total += Perl numeric value of amt (leading
   whitespace, sign, digits, fraction, exponent; "inf"/"nan" prefixes;
   anything else 0), accumulated as a double in file and line order.
7. Stamp YYYYMMDD from localtime. Writes reports/finance_billing_<stamp>.csv:
   header "Currency,RecordType,RecordCount,TotalAmount", then one row per key
   in byte order: "%s,%s,%d,%.2f" with RecordType INVOICE (01), CREDIT (02) or
   UNKNOWN(<rt>); Perl prints inf/nan as Inf, -Inf, NaN. On an empty root the
   report is header-only and the job still exits 0. If the CSV cannot be
   opened: die "cannot write $csv: $!" at line 65, exit code errno.
8. `cp $csv $xls 2>/dev/null` through /bin/sh: the .xls is a byte copy of the
   CSV; failure is ignored.
9. stdout "<stamp> wrote <root>/reports/finance_billing_<stamp>.xls".
10. If /usr/sbin/sendmail is executable, pipe a To/Subject/body message to
    `/usr/sbin/sendmail -t 2>/dev/null` (SIGPIPE ignored); otherwise nothing,
    silently.
11. stdout "<stamp> finance_excel_report done", exit 0. stderr is empty on a
    normal run. No temp files.
"""

from __future__ import annotations

import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import custbill_common as cc

LEGACY_SCRIPT = Path(__file__).resolve().parents[1] / "jobs" / "finance_excel_report.pl"
LOCK_NAME = "finance_report.lock"
SENDMAIL = "/usr/sbin/sendmail"
MAILTO = {"prod": "finance-reports@otterworks.dev", "uat": "jake@otterworks.dev", "dev": "dev-null@localhost"}
HEADER = b"Currency,RecordType,RecordCount,TotalAmount\n"
CUSTBILL_PSV = re.compile(rb"\ACUSTBILL[^\n]*\.psv\n?\Z")
PERL_NUMBER = re.compile(
    rb"[ \t\n\r\f\v]*([+-]?)(?:(inf)|(nan)|((?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?))", re.IGNORECASE
)


class LegacyDie(Exception):
    def __init__(self, message: str, line: int, errno: int) -> None:
        super().__init__(message)
        self.line = line
        self.errno = errno


def perl_num(value: bytes) -> float:
    """Numeric value of a string the way Perl's `+=` sees it."""
    m = PERL_NUMBER.match(value)
    if not m:
        return 0.0
    sign = -1.0 if m.group(1) == b"-" else 1.0
    if m.group(2):
        return sign * math.inf
    if m.group(3):
        return math.nan
    return sign * float(m.group(4))


def perl_f2(value: float) -> str:
    if math.isnan(value):
        return "NaN"
    if math.isinf(value):
        return "Inf" if value > 0 else "-Inf"
    return "%.2f" % value


def record_type_name(rt: bytes) -> bytes:
    if rt == b"01":
        return b"INVOICE"
    if rt == b"02":
        return b"CREDIT"
    return b"UNKNOWN(" + rt + b")"


def touch_lock(path: Path) -> None:
    if path.is_file():
        print("finance report lock present, running anyway")
    try:
        with open(path, "wb"):
            pass
    except OSError:
        pass


def shell(cmd: str) -> None:
    sys.stdout.flush()
    subprocess.run(cmd, shell=True, check=False)


def list_parsed(parsed: Path) -> list[bytes]:
    try:
        names = os.listdir(os.fsencode(parsed))
    except OSError as exc:
        raise LegacyDie(f"cannot open {parsed}: {os.strerror(exc.errno)}", 43, exc.errno) from exc
    return sorted(n for n in names if CUSTBILL_PSV.match(n))


def read_lines(path: bytes) -> list[bytes]:
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        return []
    lines = data.split(b"\n")
    if lines[-1] == b"":
        lines.pop()
    return lines


def accumulate(parsed: Path, names: list[bytes]) -> tuple[dict[bytes, float], dict[bytes, int]]:
    tot: dict[bytes, float] = {}
    cnt: dict[bytes, int] = {}
    for name in names:
        for line in read_lines(os.fsencode(parsed) + b"/" + name.rstrip(b" \t\n\r\f")):
            fields = (line.split(b"|") + [b""] * 6)[:6]
            cust, _name, _dt, amt, ccy, rt = fields
            if cust == b"":
                continue
            key = ccy + b"|" + rt
            tot[key] = tot.get(key, 0.0) + perl_num(amt)
            cnt[key] = cnt.get(key, 0) + 1
    return tot, cnt


def render(tot: dict[bytes, float], cnt: dict[bytes, int]) -> bytes:
    rows = [HEADER]
    for key in sorted(tot):
        ccy, _, rt = key.partition(b"|")
        rows.append(b"%s,%s,%d,%s\n" % (ccy, record_type_name(rt), cnt[key], perl_f2(tot[key]).encode()))
    return b"".join(rows)


def send_mail(mailto: str, stamp: str, xls: Path) -> None:
    if not os.access(SENDMAIL, os.X_OK):
        return
    msg = f"To: {mailto}\nSubject: [AUTO] Finance billing report {stamp}\n\nAttached... well, saved to {xls} on the ETL box.\n"
    sys.stdout.flush()
    try:
        proc = subprocess.Popen(f"{SENDMAIL} -t 2>/dev/null", shell=True, stdin=subprocess.PIPE)
    except OSError:
        return
    try:
        proc.stdin.write(os.fsencode(msg))
        proc.stdin.close()
    except BrokenPipeError:
        pass
    proc.wait()


def run() -> int:
    profile = cc.host_profile()
    root = cc.legacy_root(profile)
    parsed = root / "parsed"
    reports = root / "reports"

    touch_lock(cc.lock_path(LOCK_NAME))
    shell(f"mkdir -p {parsed} {reports} 2>/dev/null")
    print(cc.perl_localtime_stamp(cc.now_epoch()), "finance_excel_report starting")

    tot, cnt = accumulate(parsed, list_parsed(parsed))

    stamp = time.strftime("%Y%m%d", time.localtime(cc.now_epoch()))
    csv = reports / f"finance_billing_{stamp}.csv"
    xls = reports / f"finance_billing_{stamp}.xls"
    try:
        with open(csv, "wb") as out:
            out.write(render(tot, cnt))
    except OSError as exc:
        raise LegacyDie(f"cannot write {csv}: {os.strerror(exc.errno)}", 65, exc.errno) from exc

    shell(f"cp {csv} {xls} 2>/dev/null")
    print(cc.perl_localtime_stamp(cc.now_epoch()), f"wrote {xls}")

    send_mail(MAILTO[profile], stamp, xls)

    print(cc.perl_localtime_stamp(cc.now_epoch()), "finance_excel_report done")
    return 0


def main() -> int:
    try:
        return run()
    except LegacyDie as die:
        sys.stdout.flush()
        sys.stderr.write(f"{die} at {LEGACY_SCRIPT} line {die.line}.\n")
        return die.errno or 255


if __name__ == "__main__":
    sys.exit(main())
