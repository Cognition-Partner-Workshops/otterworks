"""Grades the converted estate against the Oracle recordings.

The Oracle transcripts in `procs/oracle/transcripts/` are the golden baseline for this unit:
they were recorded from the running PL/SQL, they are immutable, and they were produced before
any conversion code existed. This compares them field for field and probe for probe with the
transcripts `mongo_record.py` records from the converted routines, and writes a machine-
readable verdict. Any difference fails the unit; there is no tolerance for a "close enough"
number here, because a rating result that is off by a cent is a billing defect.

Usage:
    mongo_parity.py [--out .migration/recon/stored_logic/parity.json]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys

import transcripts as tr

ROOT = pathlib.Path(__file__).resolve().parents[2]
ORACLE = ROOT / "procs" / "oracle" / "transcripts"
CONVERTED = pathlib.Path(__file__).resolve().parent / "transcripts"
DEFAULT_OUT = ROOT / ".migration" / "recon" / "stored_logic" / "parity.json"


def load(root):
    return {
        payload["scenario"]: payload
        for payload in (json.loads(p.read_text()) for p in sorted(root.glob("*/*.json")))
    }


def diff_section(kind, expected, actual):
    findings = []
    for name in sorted(set(expected) | set(actual)):
        oracle_value = expected.get(name, "<missing>")
        mongo_value = actual.get(name, "<missing>")
        if oracle_value != mongo_value:
            findings.append(
                {"kind": kind, "name": name, "oracle": oracle_value, "mongodb": mongo_value}
            )
    return findings


def grade(oracle, converted):
    scenarios = []
    for name, expected in sorted(oracle.items()):
        actual = converted.get(name)
        if actual is None:
            scenarios.append(
                {
                    "scenario": name,
                    "module": expected["module"],
                    "entrypoint": expected["oracle_entrypoint"],
                    "verdict": "FAIL",
                    "findings": [{"kind": "transcript", "name": name, "oracle": "recorded",
                                  "mongodb": "<missing>"}],
                }
            )
            continue
        findings = diff_section(
            "business_field", expected["business_fields"], actual["business_fields"]
        ) + diff_section("probe", expected["probes"], actual["probes"])
        scenarios.append(
            {
                "scenario": name,
                "module": expected["module"],
                "entrypoint": expected["oracle_entrypoint"],
                "verdict": "FAIL" if findings else "PASS",
                "findings": findings,
            }
        )
    unrecorded = sorted(set(converted) - set(oracle))
    return scenarios, unrecorded


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    oracle = load(ORACLE)
    if not oracle:
        sys.exit("no oracle transcripts to grade against")
    # Not just "the files that are there": the converted side is graded only as the run that
    # published it, so an interrupted or superseded recording cannot pass as current.
    manifest, converted = tr.published(CONVERTED)

    scenarios, unrecorded = grade(oracle, converted)
    failed = [s for s in scenarios if s["verdict"] == "FAIL"]
    by_entrypoint = {}
    for scenario in scenarios:
        rollup = by_entrypoint.setdefault(scenario["entrypoint"], {"pass": 0, "fail": 0})
        rollup["pass" if scenario["verdict"] == "PASS" else "fail"] += 1

    report = {
        "unit": "stored_logic",
        "generated_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "baseline": "procs/oracle/transcripts (recorded from the running PL/SQL estate)",
        "replay_run_id": manifest["run_id"],
        "replay_recorded_at": manifest["recorded_at"],
        "verdict": "FAIL" if failed or unrecorded else "PASS",
        "scenarios_graded": len(scenarios),
        "scenarios_failed": len(failed),
        "unrecorded_by_oracle": unrecorded,
        "by_entrypoint": dict(sorted(by_entrypoint.items())),
        "scenarios": scenarios,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        f"stored_logic parity {report['verdict']}: {len(scenarios) - len(failed)}/{len(scenarios)} "
        f"scenarios, {len(by_entrypoint)} entrypoints -> {args.out.relative_to(ROOT)}"
    )
    if report["verdict"] == "FAIL":
        for scenario in failed:
            for finding in scenario["findings"]:
                print(
                    f"  {scenario['scenario']} {finding['kind']} {finding['name']}: "
                    f"oracle={finding['oracle']!r} mongodb={finding['mongodb']!r}"
                )
        sys.exit(1)


if __name__ == "__main__":
    main()
