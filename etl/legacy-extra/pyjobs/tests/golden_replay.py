"""Replay a committed golden capture against a Python port, byte for byte.

A capture (written by `tools/parity.sh golden`) lives in
tests/golden/<job>/<ns>/{before,after}/ with the same layout parity.sh
compares: tree/ (the run root), manifest, stdout, stderr, exit_code, locks.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

PYJOBS = Path(__file__).resolve().parents[1]
GOLDEN = Path(__file__).resolve().parent / "golden"
GOLDEN_NOW = "2026-01-15 00:00:00"
LOCK_NAMES = ("sftp_ingest.lock", "parse_custbill.lock", "finance_report.lock")
ROOT_TOKEN = "$OTTERWORKS_LEGACY_ROOT"


def golden_namespaces(job: str) -> list[str]:
    base = GOLDEN / job
    return sorted(p.name for p in base.iterdir() if p.is_dir()) if base.is_dir() else []


def manifest(root: Path) -> bytes:
    lines = []
    for p in sorted(root.rglob("*"), key=lambda q: q.relative_to(root).as_posix().encode()):
        rel = p.relative_to(root).as_posix()
        lines.append(f"{rel} d -\n" if p.is_dir() else f"{rel} f {p.stat().st_size}\n")
    return "".join(lines).encode()


def run_port(job: str, root: Path, lock_dir: Path, now: str = GOLDEN_NOW) -> subprocess.CompletedProcess:
    env = dict(os.environ, OTTERWORKS_LEGACY_ROOT=str(root), CUSTBILL_NOW=now,
               CUSTBILL_LOCK_DIR=str(lock_dir), TZ="UTC", LC_ALL="C", LANG="C")
    return subprocess.run([sys.executable, str(PYJOBS / f"{job}.py")], env=env,
                          capture_output=True, check=False)


def snapshot(proc: subprocess.CompletedProcess, root: Path, lock_dir: Path) -> dict[str, bytes]:
    def redact(b: bytes) -> bytes:
        return b.replace(str(root).encode(), ROOT_TOKEN.encode())

    locks = "".join(f"{n} {'present' if (lock_dir / n).is_file() else 'absent'}\n" for n in LOCK_NAMES)
    snap = {"stdout": redact(proc.stdout), "stderr": redact(proc.stderr),
            "exit_code": f"{proc.returncode}\n".encode(), "locks": locks.encode(),
            "manifest": manifest(root)}
    for p in root.rglob("*"):
        if p.is_file():
            snap["tree/" + p.relative_to(root).as_posix()] = p.read_bytes()
    return snap


def load_capture(path: Path) -> dict[str, bytes]:
    snap = {name: (path / name).read_bytes() for name in ("stdout", "stderr", "exit_code", "locks", "manifest")}
    tree = path / "tree"
    for p in tree.rglob("*"):
        if p.is_file():
            snap["tree/" + p.relative_to(tree).as_posix()] = p.read_bytes()
    return snap


def replay(job: str, ns: str, tmp_path: Path) -> tuple[dict[str, bytes], dict[str, bytes]]:
    """Run the port from the golden before-state; return (expected, actual)."""
    case = GOLDEN / job / ns
    root = tmp_path / "root"
    lock_dir = tmp_path / "locks"
    lock_dir.mkdir()
    shutil.copytree(case / "before" / "tree", root, symlinks=True)
    for line in (case / "before" / "locks").read_text().splitlines():
        name, state = line.split()
        if state == "present":
            (lock_dir / name).touch()
    proc = run_port(job, root, lock_dir)
    return load_capture(case / "after"), snapshot(proc, root, lock_dir)


def assert_matches(expected: dict[str, bytes], actual: dict[str, bytes]) -> None:
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    differ = sorted(k for k in set(expected) & set(actual) if expected[k] != actual[k])
    assert not (missing or extra or differ), (
        f"golden mismatch: missing={missing} extra={extra} differ={differ}\n"
        + "".join(f"--- {k}\nexpected={expected[k][:400]!r}\nactual  ={actual[k][:400]!r}\n" for k in differ[:3])
    )
