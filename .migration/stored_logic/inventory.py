"""Checks that every PL/SQL object in the estate has a disposition, and that it is real.

Parity proves the converted routines behave like the Oracle ones for the recorded scenarios.
It says nothing about the objects no scenario calls -- the triggers, the two scheduler jobs,
the five sequences. This closes that gap: the source tree is parsed for every package,
routine, trigger, job and sequence, each is matched to an entry in `dispositions.json`, and
every entry that claims a target symbol has to resolve to code that actually exists.

Fail-closed, per the unit contract: an empty or short parse is a failed extraction, not an
empty estate, and it exits nonzero rather than reporting a vacuous pass.

Usage:
    inventory.py [--out .migration/recon/stored_logic/inventory.json]
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib
import json
import pathlib
import re
import sys

import billing_logic  # noqa: F401 - imported so target symbols resolve
import mongo_store  # noqa: F401

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ORACLE_DB = ROOT / "services" / "legacy-billing" / "db" / "oracle"
DISPOSITIONS = HERE / "dispositions.json"
DEFAULT_OUT = ROOT / ".migration" / "recon" / "stored_logic" / "inventory.json"

PACKAGE = re.compile(r"CREATE OR REPLACE PACKAGE\s+(?!BODY)(\w+)", re.IGNORECASE)
ROUTINE = re.compile(r"^\s+(FUNCTION|PROCEDURE)\s+(\w+)", re.IGNORECASE | re.MULTILINE)
TRIGGER = re.compile(r"CREATE OR REPLACE TRIGGER\s+(\w+)", re.IGNORECASE)
SEQUENCE = re.compile(r"CREATE SEQUENCE\s+(\w+)", re.IGNORECASE)
JOB = re.compile(r"job_name\s*=>\s*'(\w+)'", re.IGNORECASE)


def scan():
    """Read the estate's DDL. The package spec is the declaration of record for a routine --
    the body repeats it -- so routines are taken from the spec half of each package file."""
    objects = {"packages": [], "routines": [], "triggers": [], "jobs": [], "sequences": []}
    for path in sorted(ORACLE_DB.rglob("*.sql")):
        text = path.read_text()
        objects["triggers"] += [t.lower() for t in TRIGGER.findall(text)]
        objects["sequences"] += [s.lower() for s in SEQUENCE.findall(text)]
        objects["jobs"] += JOB.findall(text)
        packages = PACKAGE.findall(text)
        objects["packages"] += [p.lower() for p in packages]
        if not packages:
            continue
        package = packages[0].lower()
        spec = text.split("CREATE OR REPLACE PACKAGE BODY")[0]
        objects["routines"] += [f"{package}.{name.lower()}" for _, name in ROUTINE.findall(spec)]
    return {kind: sorted(set(names)) for kind, names in objects.items()}


def resolve(target):
    """`module.attr` or `module.Class.attr`, as written in dispositions.json."""
    parts = target.split(".")
    try:
        obj = importlib.import_module(parts[0])
    except ModuleNotFoundError:
        return False
    for part in parts[1:]:
        obj = getattr(obj, part, None)
        if obj is None:
            return False
    return True


def check(found, dispositions):
    problems = []
    expected = dispositions["expected_inventory"]
    for kind, count in expected.items():
        if len(found[kind]) != count:
            problems.append(
                f"{kind}: parsed {len(found[kind])} ({', '.join(found[kind]) or 'none'}), the "
                f"contract expects {count}; treat this as a failed extraction, not an empty estate"
            )

    for kind in ("routines", "triggers", "jobs", "sequences"):
        declared = {entry["object"].lower(): entry for entry in dispositions[kind]}
        for name in found[kind]:
            if name.lower() not in declared:
                problems.append(f"{kind}: {name} has no disposition")
        for name in declared:
            if name not in [n.lower() for n in found[kind]]:
                problems.append(f"{kind}: {name} is dispositioned but not present in the source")

    for entry in dispositions["routines"]:
        if entry["disposition"] != "converted":
            problems.append(f"routine {entry['object']}: only 'converted' is an accepted "
                            f"disposition, got {entry['disposition']!r}")
        elif not resolve(entry["target"]):
            problems.append(f"routine {entry['object']}: target {entry['target']} does not exist")

    for entry in dispositions["triggers"]:
        if entry["disposition"] not in ("reproduced", "retired"):
            problems.append(f"trigger {entry['object']}: unknown disposition "
                            f"{entry['disposition']!r}")
        if not entry.get("reason") or not entry.get("effect"):
            problems.append(f"trigger {entry['object']}: needs both its effect and a reason")

    for entry in dispositions["jobs"]:
        if not entry.get("replacement"):
            problems.append(f"job {entry['object']}: no named replacement")
    ttl = [e for e in dispositions["jobs"] if e["object"] == "JOB_PURGE_AUDIT_LOG"]
    if not ttl or "TTL index" not in ttl[0]["replacement"]:
        problems.append("job JOB_PURGE_AUDIT_LOG: the contract requires a TTL index replacement")

    for entry in dispositions["sequences"]:
        if entry["disposition"] != "retired" or not entry.get("natural_key"):
            problems.append(f"sequence {entry['object']}: must be retired in favour of a named "
                            "natural key")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    found = scan()
    if not any(found.values()):
        sys.exit(f"no PL/SQL objects parsed from {ORACLE_DB}; refusing to report a vacuous pass")
    dispositions = json.loads(DISPOSITIONS.read_text())
    problems = check(found, dispositions)

    report = {
        "unit": "stored_logic",
        "generated_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "source_tree": str(ORACLE_DB.relative_to(ROOT)),
        "verdict": "FAIL" if problems else "PASS",
        "counts": {kind: len(names) for kind, names in found.items()},
        "objects": found,
        "problems": problems,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    counts = ", ".join(f"{k} {v}" for k, v in report["counts"].items())
    print(f"stored_logic inventory {report['verdict']}: {counts} -> {args.out.relative_to(ROOT)}")
    for problem in problems:
        print(f"  {problem}")
    if problems:
        sys.exit(1)


if __name__ == "__main__":
    main()
