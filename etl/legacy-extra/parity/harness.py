"""Compare CUSTBILL chain artifacts without importing a candidate implementation."""

import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile

ESTATE = Path(__file__).resolve().parents[1]
REPO = ESTATE.parents[1]
CASES = ("dev", "qa", "edges", "empty")
JOBS = (("ksh", "sftp_ingest_poll.ksh"),
        ("bash", "parse_custbill_fixedwidth.sh"),
        ("perl", "finance_excel_report.pl"))


def environment(root):
    return dict(os.environ, OTTERWORKS_LEGACY_ROOT=str(root), RUN_ALL_SLEEP="0",
                LC_ALL="C", TZ="UTC")


def seed(root, case):
    drop = root / "sftp-drop/upload"
    drop.mkdir(parents=True)
    if case in ("dev", "qa"):
        subprocess.run(["perl", str(ESTATE / "tools/gen_sample_data.pl"), case, "2", "8"],
                       env=environment(root), check=True, capture_output=True)
    elif case == "edges":
        for path in sorted((ESTATE / "parity/fixtures").glob("*.dat")):
            shutil.copyfile(path, drop / path.name)


def execute(root, candidate, log, timeout):
    commands = ([list((interpreter, str(ESTATE / "jobs" / job)))
                 for interpreter, job in JOBS] if candidate == "legacy"
                else [["/bin/sh", "-c", candidate]])
    try:
        with log.open("wb") as stream:
            for command in commands:
                with subprocess.Popen(command, cwd=REPO, env=environment(root),
                                      stdout=stream, stderr=subprocess.STDOUT,
                                      start_new_session=True) as process:
                    try:
                        returncode = process.wait(timeout=timeout)
                    except subprocess.TimeoutExpired:
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        process.wait()
                        raise
                    if returncode:
                        return f"exit {returncode} (see {log.name})"
    except (OSError, subprocess.TimeoutExpired) as exc:
        return str(exc)
    return None


def files(root, pattern):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.glob(pattern) if p.is_file()}


def difference(left, right):
    if left == right:
        return None
    if left is None or right is None:
        return {"line": 1, "legacy": "missing" if left is None else "present",
                "candidate": "missing" if right is None else "present"}
    a, b = left.splitlines(keepends=True), right.splitlines(keepends=True)
    for index in range(max(len(a), len(b))):
        x = a[index] if index < len(a) else b""
        y = b[index] if index < len(b) else b""
        if x != y:
            return {"line": index + 1, "legacy": repr(x), "candidate": repr(y)}


def compare(case, left, right):
    rows = []
    for stage, pattern in (("ingest/drop", "sftp-drop/upload/**/*"),
                           ("ingest/incoming", "incoming/**/*"),
                           ("parse", "parsed/**/*"),
                           ("report/csv", "reports/finance_billing_*.csv"),
                           ("report/xls", "reports/finance_billing_*.xls")):
        a, b = files(left, pattern), files(right, pattern)
        valid = True
        if stage.startswith("report/"):
            valid = len(a) == len(b) == 1
            # Compare the single report regardless of localtime's filename stamp.
            a = {"report": next(iter(a.values()))} if len(a) == 1 else a
            b = {"report": next(iter(b.values()))} if len(b) == 1 else b
        comparisons = [{"file": name, "byte_identical": a.get(name) == b.get(name),
                        "first_difference": difference(a.get(name), b.get(name))}
                       for name in sorted(a.keys() | b.keys())]
        rows.append({"case": case, "stage": stage, "files": comparisons,
                     "byte_identical": valid and all(f["byte_identical"] for f in comparisons)})
    return rows


def run(candidate, output, cases=CASES, timeout=120):
    for interpreter, _ in JOBS:
        if shutil.which(interpreter) is None:
            raise RuntimeError(f"required interpreter unavailable: {interpreter}")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    # Keep roots and logs beside the table so failures can be inspected.
    work = Path(tempfile.mkdtemp(prefix="run-", dir=output))
    for case in cases:
        a, b = work / case / "legacy", work / case / "candidate"
        seed(a, case)
        shutil.copytree(a, b)
        errors = [execute(a, "legacy", work / f"{case}-legacy.log", timeout),
                  execute(b, candidate, work / f"{case}-candidate.log", timeout)]
        expected = {p.name for p in (ESTATE / "parity/fixtures").glob("*.dat")} if case == "edges" else (
            {f"CUSTBILL_{case.upper()}_{n:03d}.dat" for n in (1, 2)}
            if case in ("dev", "qa") else set())
        for root in (a, b):
            if (set(files(root, "incoming/**/*")) != {f"incoming/{n}.done" for n in expected}
                    or set(files(root, "parsed/**/*")) != {f"parsed/{n[:-4]}.psv" for n in expected}
                    or files(root, "sftp-drop/upload/**/*")):
                errors.append(f"unexpected staged/parsed inventory or nonempty drop: {root}")
        rows.extend(compare(case, a, b))
        rows.append({"case": case, "stage": "execution", "files": [],
                     "byte_identical": not any(errors), "errors": errors})
    passed = all(row["byte_identical"] for row in rows)
    (output / "parity.json").write_text(json.dumps({"passed": passed, "work": str(work),
                                                  "rows": rows}, indent=2) + "\n")
    table = ["| Case | Stage | Files compared | Byte-identical | First difference |",
             "| --- | --- | --- | --- | --- |"]
    for row in rows:
        details = [f"{f['file']}: {f['first_difference']}" for f in row["files"]
                   if f["first_difference"]]
        details.extend(str(e) for e in row.get("errors", []) if e)
        table.append(f"| {row['case']} | {row['stage']} | {len(row['files'])} | "
                     f"{'yes' if row['byte_identical'] else 'NO'} | "
                     + "; ".join(details).replace("|", "&#124;") + " |")
    (output / "parity.md").write_text("\n".join(table) + "\n")
    print("\n".join(table))
    print(f"parity: {'PASS' if passed else 'FAIL'}; reports: {output}")
    return 0 if passed else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", default=os.environ.get("CANDIDATE"))
    parser.add_argument("--output", type=Path, default=ESTATE / "reports/parity")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    if not args.candidate:
        parser.error("set CANDIDATE to legacy or a trusted shell command")
    return run(args.candidate, args.output, timeout=args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
