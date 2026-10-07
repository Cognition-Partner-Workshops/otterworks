#!/usr/bin/env python3
"""Compare a characterization run on Postgres with the Oracle golden.

    python parity.py --before golden/oracle.json --after runs/postgres.json \
        --out ../../../../docs/tech-partnerships/recon/legacy-billing-app-parity.demo.md

Every call is graded `identical`, `accepted difference with reason` (only the
fields listed in ACCEPTED, each with its reason) or `failed`. Exit code 1 if
anything failed.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from collections import OrderedDict
from pathlib import Path

# (step-id predicate, JSON path, reason). A path is a tuple of keys; the value
# at that path is compared only for the expected before/after pair.
ACCEPTED = [
    (lambda sid: sid == "health", ("body", "backend"), ("oracle", "ow_billing_pg"),
     "health names the backend that answers; it is meant to change at cutover"),
    (lambda sid: ("month-end" in sid or "reconciliation" in sid) and "forbidden" not in sid,
     ("body", "source"), None,
     "report source metadata names the engine (oracle -> postgresql); figures unchanged"),
    (lambda sid: sid.endswith("reconciliation") and "forbidden" not in sid,
     ("body", "status"), ("baseline", "pass"),
     "on Oracle the estate is the baseline; after takeout the endpoint reconciles against it"),
    (lambda sid: sid.endswith("reconciliation") and "unknown-ns" not in sid,
     ("body", "checks"), None,
     "post-migration checks recomputed from Postgres vs the Oracle figures in migration_baseline"),
    (lambda sid: sid == "reconciliation:unknown-ns", ("body", "status"), ("baseline", "fail"),
     "no migration baseline exists for an unseeded namespace, so it fails closed"),
    (lambda sid: sid == "reconciliation:unknown-ns", ("body", "checks"), None,
     "single migration-baseline: missing check instead of an empty baseline"),
    (lambda sid: True, ("body", "detail"),
     ("the Oracle billing estate is not reachable", "the PostgreSQL billing estate is not reachable"),
     "503 detail names the engine; status code and error key unchanged"),
]

GROUPS = [
    ("health", "Health"),
    ("before:month-end", "Month-end report (before writes)"),
    ("after:month-end", "Month-end report (after writes)"),
    ("admin-month-end", "Month-end admin alias"),
    ("reconciliation", "Reconciliation report"),
    ("month-end:unknown-ns", "Month-end, unseeded namespace"),
    ("plans", "Plans"),
    ("legacy:", "Legacy HTML/JSON routes (/plans, /api/rating, /api/invoices, /api/dunning)"),
    (":me:", "/me"),
    (":entitlement", "Entitlement"),
    (":usage:", "Usage"),
    (":invoices:", "Invoices and invoice lines"),
    (":customer:", "Customer"),
    ("admin-", "Admin overdue / dunning"),
    ("ingest", "Internal usage ingest"),
    ("plan-change", "Plan change"),
    ("finalize", "Rating finalize"),
    ("issue", "Invoice issue"),
    ("dunning:", "Dunning schedule / suspend"),
    ("", "Validation and auth errors"),
]


def _get(obj, path):
    for key in path:
        if not isinstance(obj, dict) or key not in obj:
            return None, False
        obj = obj[key]
    return obj, True


def _drop(obj, path):
    for key in path[:-1]:
        obj = obj.get(key) if isinstance(obj, dict) else None
        if obj is None:
            return
    if isinstance(obj, dict):
        obj.pop(path[-1], None)


def grade(step_id, before, after):
    if before == after:
        return "identical", []
    if after is None:
        return "failed", ["missing on Postgres"]
    b, a = copy.deepcopy(before), copy.deepcopy(after)
    b.pop("attempts", None)
    a.pop("attempts", None)
    if a == b:
        return "identical", []
    reasons = []
    for match, path, pair, reason in ACCEPTED:
        if not match(step_id):
            continue
        bv, bfound = _get(b, path)
        av, afound = _get(a, path)
        if not (bfound or afound) or bv == av:
            continue
        if pair is not None and (bv, av) != pair:
            continue
        _drop(b, path)
        _drop(a, path)
        reasons.append(reason)
    if a == b:
        return "accepted difference with reason", reasons
    return "failed", [_first_diff(b, a)]


def _first_diff(b, a, path="$"):
    if type(b) is not type(a):
        return f"{path}: {json.dumps(b)[:120]} != {json.dumps(a)[:120]}"
    if isinstance(b, dict):
        for key in sorted(set(b) | set(a)):
            if b.get(key) != a.get(key):
                return _first_diff(b.get(key), a.get(key), f"{path}.{key}")
    if isinstance(b, list):
        if len(b) != len(a):
            return f"{path}: {len(b)} items != {len(a)} items"
        for i, (x, y) in enumerate(zip(b, a)):
            if x != y:
                return _first_diff(x, y, f"{path}[{i}]")
    return f"{path}: {json.dumps(b)[:120]} != {json.dumps(a)[:120]}"


def group_of(step_id):
    for prefix, title in GROUPS:
        if prefix in step_id and (prefix != "plans" or step_id.startswith("plans")):
            return title
    return GROUPS[-1][1]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--before", type=Path, required=True)
    ap.add_argument("--after", type=Path, required=True)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    before = json.loads(args.before.read_text())
    after = json.loads(args.after.read_text())

    groups: OrderedDict[str, dict] = OrderedDict((title, {"calls": 0, "grades": {}, "notes": set()})
                                                 for _, title in GROUPS)
    failures = []
    for step_id in list(before) + [k for k in after if k not in before]:
        result, notes = grade(step_id, before.get(step_id), after.get(step_id))
        if step_id not in before:
            result, notes = "failed", ["not in Oracle golden"]
        g = groups[group_of(step_id)]
        g["calls"] += 1
        g["grades"][result] = g["grades"].get(result, 0) + 1
        g["notes"].update(notes)
        if result == "failed":
            failures.append((step_id, notes[0]))

    lines = [
        "| Area | Calls | Result | Reason |",
        "| --- | ---: | --- | --- |",
    ]
    for title, g in groups.items():
        if not g["calls"]:
            continue
        if "failed" in g["grades"]:
            result = "failed"
        elif "accepted difference with reason" in g["grades"]:
            result = "accepted difference with reason"
        else:
            result = "identical"
        detail = ", ".join(f"{n} {k}" for k, n in sorted(g["grades"].items()))
        reason = "; ".join(sorted(g["notes"])) if result != "identical" else detail
        lines.append(f"| {title} | {g['calls']} | {result} | {reason} |")
    total = len(set(before) | set(after))
    lines.append("")
    lines.append(f"{total} calls compared; {len(failures)} failed.")
    for step_id, note in failures:
        lines.append(f"- `{step_id}`: {note}")
    text = "\n".join(lines) + "\n"
    print(text)
    if args.out:
        args.out.write_text(text)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
