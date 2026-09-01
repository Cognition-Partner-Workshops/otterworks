"""Emit the repo-schema recon report (`*.recon.json`) for U3.

Wraps the harness `result.json` (the verdict authority; never re-graded here) and the
loader `load_report.json`, recomputing the target-side counts live from Atlas so the
report never carries copied numbers. Checks are pass/fail by comparison only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parent))
from load_u3 import NS_VALUE, QUARANTINE_DB, TARGET_DB  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / ".migration/recon/U3"
MANIFEST = ROOT / "testdata/legacy/manifests/demo.json"
EXPECTED_ANOMALIES = {"orphaned_snapshots": "postgres.otterworks_demo.document_snapshots",
                      "version_gaps": "postgres.otterworks_demo.document_versions"}


def _check(cid: str, expected: Any, actual: Any, truth: str) -> dict[str, Any]:
    return {"id": cid, "expected": expected, "actual": actual, "source_of_truth": truth,
            "result": "pass" if expected == actual else "fail"}


def build(result: dict, load: dict, run1: dict, target_counts: dict[str, int],
          manifest: dict) -> dict[str, Any]:
    tiers = {t["tier"]: t for t in result["tiers"]}
    checks = [
        _check("harness.verdict", "PASS", result["verdict"], ".migration/recon/U3/result.json"),
        _check("harness.mapping_version", "v1.0", result["mapping_version"], "result.json"),
        _check("harness.tolerance_version", "v1", result["tolerance_version"], "result.json"),
    ]
    for n, t in sorted(tiers.items()):
        checks.append(_check(f"harness.tier{n}.{t['name']}", True, t["passed"], "result.json"))
    checks += [
        _check("target.documents.count", 2000, target_counts["documents"], "Atlas count_documents"),
        _check("target.documents.versions_embedded", 13876,
               target_counts["versions"], "Atlas $unwind count"),
        _check("target.document_snapshots.count", 384,
               target_counts["document_snapshots"], "Atlas count_documents"),
        _check("target.quarantine.orphan_document_snapshots.count", 6,
               target_counts["orphan_document_snapshots"], "Atlas count_documents"),
        _check("target.ns_tagged_docs", target_counts["all_docs"],
               target_counts["ns_docs"], f"Atlas count_documents({{ns: {NS_VALUE!r}}})"),
        _check("load.version_gaps_reported_not_repaired", 10,
               load["version_gaps"]["total_missing_numbers"], "load_report.json (D7)"),
        _check("load.orphan_versions", 0, load["orphan_versions"], "load_report.json"),
    ]
    planted = {a["kind"]: a["count"] for a in manifest["planted_anomalies"]
               if a["kind"] in EXPECTED_ANOMALIES and a["target"] == EXPECTED_ANOMALIES[a["kind"]]}
    actual = {"orphaned_snapshots": target_counts["orphan_document_snapshots"],
              "version_gaps": load["version_gaps"]["documents_with_gaps"]}
    expected_set = sorted(f"{k}:{v}" for k, v in planted.items())
    actual_set = sorted(f"{k}:{v}" for k, v in actual.items())
    same_counts = all(load["collections"][c]["docs_after"] == run1["collections"][c]["docs_after"]
                      for c in load["collections"])
    return {
        "kind": "recon-report",
        "unit": "U3",
        "namespace": NS_VALUE,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_mode": "fixture",
        "harness": {"result": ".migration/recon/U3/result.json",
                    "verdict": result["verdict"], "seed": result["seed"],
                    "params": result["params"]},
        "checks": checks,
        "values_recomputed_from_target": True,
        "idempotency_rerun": {
            "performed": True,
            "result": "pass" if same_counts and all(
                load["collections"][c]["dropped"] for c in load["collections"]) else "fail",
            "evidence": ".migration/recon/U3/idempotency.md",
        },
        "planted_anomaly_detections": {
            "expected_set": expected_set,
            "actual_set": actual_set,
            "missing": sorted(set(expected_set) - set(actual_set)),
            "unexpected": sorted(set(actual_set) - set(expected_set)),
        },
        "unverified_paths": [
            "LIVE-mode recon gate (parent-run responsibility; this report is run_mode=fixture)",
            "Tier 4 app-level parity (no recorded ops for U3; not in the U3 contract)",
            "key_strata() of PostgresSourceAdapter (not exercised: Tier 3 ran full_diff below threshold)",
            "state_b64 payload decode (deliberately byte-transparent per mapping v1.0; never decoded)",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--uri-secret", default="MONGODB_ATLAS_URI")
    p.add_argument("--out", default=str(OUT_DIR / "u3.recon.json"))
    args = p.parse_args(argv)
    uri = os.environ.get(args.uri_secret)
    if not uri:
        raise SystemExit(f"secret {args.uri_secret} not set")
    client = MongoClient(uri)
    db, qdb = client[TARGET_DB], client[QUARANTINE_DB]
    versions = next(db["documents"].aggregate(
        [{"$unwind": "$versions"}, {"$count": "n"}]), {"n": 0})["n"]
    counts = {
        "documents": db["documents"].count_documents({}),
        "versions": versions,
        "document_snapshots": db["document_snapshots"].count_documents({}),
        "orphan_document_snapshots": qdb["orphan_document_snapshots"].count_documents({}),
    }
    counts["all_docs"] = counts["documents"] + counts["document_snapshots"] + counts["orphan_document_snapshots"]
    counts["ns_docs"] = sum(c.count_documents({"ns": NS_VALUE}) for c in (
        db["documents"], db["document_snapshots"], qdb["orphan_document_snapshots"]))
    report = build(json.loads((OUT_DIR / "result.json").read_text()),
                   json.loads((OUT_DIR / "load_report.json").read_text()),
                   json.loads((OUT_DIR / "load_report_run1.json").read_text()),
                   counts, json.loads(MANIFEST.read_text()))
    Path(args.out).write_text(json.dumps(report, indent=2) + "\n")
    failed = [c["id"] for c in report["checks"] if c["result"] != "pass"]
    anomaly_failures = (report["planted_anomaly_detections"]["missing"]
                        + report["planted_anomaly_detections"]["unexpected"])
    idempotency_failed = report["idempotency_rerun"]["result"] != "pass"
    print(f"wrote {args.out}; checks={len(report['checks'])} failed={failed} "
          f"anomaly_failures={anomaly_failures} "
          f"idempotency_failed={idempotency_failed}")
    return 1 if failed or anomaly_failures or idempotency_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
