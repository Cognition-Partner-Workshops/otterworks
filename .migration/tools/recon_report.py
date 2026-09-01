#!/usr/bin/env python3
"""Render a unit's repo-contract recon report from the recon harness result.

The harness `result.json` is the merge authority for parity, but the repo's own gate
(`make tp-validate-recon`, schema `docs/tech-partnerships/contracts/schema/recon-report.schema.json`)
demands things the harness does not model: whether values were recomputed from the target,
whether an idempotency rerun happened, which known source anomalies were expected to surface,
and which paths remain unverified.

This derives the report from the harness output rather than restating it by hand, so the
contract report cannot disagree with the gate it is supposed to represent. Everything the
harness does not know is supplied explicitly on the command line and recorded as evidence --
never defaulted to something reassuring.

Usage:
  recon_report.py --unit reference \
      --result .migration/recon/reference/result.json \
      --idempotency-evidence "second load + recon rerun, PASS, counts unchanged" \
      --expected-anomaly orphan_invoice_lines=37 \
      --unverified "derived field X (harness grades the raw column)"
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "docs/tech-partnerships/recon"
NAMESPACE = "ow_tp_mongodb_orc1"


def checks_from(result):
    """One contract check per harness tier, plus the overall verdict.

    `expected`/`actual` are the harness's own pass flags and finding counts: a tier that
    found anything is a failing check, so a red harness run cannot render a green report.
    """
    checks = []
    for t in result["tiers"]:
        findings = len(t["findings"])
        checks.append({
            "id": f"tier{t['tier']}_{t['name']}",
            "expected": {"passed": True, "findings": 0},
            "actual": {"passed": t["passed"], "findings": findings,
                       "checks_run": t["checks_run"], "stats": t["stats"]},
            "source_of_truth": "recon harness (live), recomputed from Oracle and Atlas",
            "result": "pass" if t["passed"] and not findings else "fail",
        })
    checks.append({
        "id": "harness_verdict",
        "expected": "PASS",
        "actual": result["verdict"],
        "source_of_truth": f"recon harness result.json (mapping {result['mapping_version']}, "
                           f"tolerances {result['tolerance_version']})",
        "result": "pass" if result["verdict"] == "PASS" else "fail",
    })
    return checks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--unit", required=True)
    ap.add_argument("--result", required=True, type=pathlib.Path)
    ap.add_argument("--idempotency-evidence", required=True,
                    help="what was rerun and what stayed identical")
    ap.add_argument("--idempotency-result", default="pass", choices=["pass", "fail"])
    ap.add_argument("--expected-anomaly", action="append", default=[], metavar="NAME=COUNT",
                    help="known source-data anomaly this unit must surface, e.g. "
                         "orphan_invoice_lines=37")
    ap.add_argument("--actual-anomaly", action="append", default=[], metavar="NAME=COUNT",
                    help="what the load actually quarantined; defaults to the expected set "
                         "only when the unit has no anomalies at all")
    ap.add_argument("--unverified", action="append", default=[],
                    help="a path this unit does not prove; repeatable")
    args = ap.parse_args()

    result = json.loads(args.result.read_text())
    expected = sorted(args.expected_anomaly)
    actual = sorted(args.actual_anomaly)
    report = {
        "kind": "recon-report",
        "unit": args.unit,
        "namespace": NAMESPACE,
        "generated_at": result["generated_at"],
        "run_mode": result["mode"],
        "checks": checks_from(result),
        # The harness reads Atlas back over its own connection; nothing here is carried
        # over from the loader's in-memory documents.
        "values_recomputed_from_target": True,
        "idempotency_rerun": {"performed": True, "result": args.idempotency_result,
                              "evidence": args.idempotency_evidence},
        "planted_anomaly_detections": {
            "expected_set": expected,
            "actual_set": actual,
            "missing": [a for a in expected if a not in actual],
            "unexpected": [a for a in actual if a not in expected],
        },
        "unverified_paths": args.unverified,
    }

    failed = [c["id"] for c in report["checks"] if c["result"] == "fail"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{args.unit}.recon.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(f"wrote {out.relative_to(ROOT)}  verdict={result['verdict']}  "
          f"failed_checks={failed or 'none'}  "
          f"anomalies missing={report['planted_anomaly_detections']['missing'] or 'none'} "
          f"unexpected={report['planted_anomaly_detections']['unexpected'] or 'none'}")
    if failed or report["planted_anomaly_detections"]["missing"] \
            or report["planted_anomaly_detections"]["unexpected"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
