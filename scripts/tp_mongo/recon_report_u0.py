"""Emit the repo-schema recon report (`*.recon.json`) for U0.

Wraps the harness `result.json` (the verdict authority; never re-graded here) and the
loader reports, recomputing target-side counts live from Atlas so the report never
carries copied numbers. Checks are pass/fail by comparison only.
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
from load_u0 import NS_VALUE, TARGET_DB, UNIT_COLLECTIONS

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / ".migration/recon/U0"
MANIFEST = ROOT / "testdata/legacy/manifests/demo.json"
EXPECTED_ROWS = {"codes": 32, "tenants": 69, "plans": 3}
U0_SOURCE_TABLES = {"CODES", "TENANTS", "PLANS"}
CODES_INDEXES = {"_id_", "code_type_1_code_val_1"}


def _check(cid: str, expected: Any, actual: Any, truth: str) -> dict[str, Any]:
    return {"id": cid, "expected": expected, "actual": actual, "source_of_truth": truth,
            "result": "pass" if expected == actual else "fail"}


def build(result: dict, load: dict, run1: dict, target: dict[str, Any],
          manifest: dict) -> dict[str, Any]:
    tiers = {t["tier"]: t for t in result["tiers"]}
    checks = [
        _check("harness.verdict", "PASS", result["verdict"], ".migration/recon/U0/result.json"),
        _check("harness.mapping_version", "v1.0.1", result["mapping_version"], "result.json"),
        _check("harness.tolerance_version", "v1", result["tolerance_version"], "result.json"),
        _check("harness.warnings_ungraded", [], result.get("warnings", []), "result.json"),
    ]
    for n, t in sorted(tiers.items()):
        checks.append(_check(f"harness.tier{n}.{t['name']}", True, t["passed"], "result.json"))
    for coll, expected in EXPECTED_ROWS.items():
        checks.append(_check(f"target.{coll}.count", expected, target["counts"][coll],
                             "Atlas count_documents"))
        checks.append(_check(f"target.{coll}.ns_tagged", target["counts"][coll],
                             target["ns_counts"][coll],
                             f"Atlas count_documents({{ns: {NS_VALUE!r}}})"))
    checks.append(_check("target.codes.indexes", sorted(CODES_INDEXES),
                         sorted(target["codes_indexes"]), "Atlas list_indexes"))
    checks.append(_check("target.codes.key_shape_TYPE_COLON_VAL", target["counts"]["codes"],
                         target["codes_key_shape_ok"], "Atlas $regexMatch on _key"))
    checks.append(_check("load.target_db", TARGET_DB, load["target_db"], "load_report.json"))
    checks.append(_check("load.collections_owned", sorted(UNIT_COLLECTIONS),
                         sorted(load["collections"]), "load_report.json"))

    planted = sorted(
        f"{a['kind']}:{a['count']}" for a in manifest["planted_anomalies"]
        if a["target"].startswith("oracle.OW_BILLING.")
        and a["target"].split(".")[2] in U0_SOURCE_TABLES)
    same_output = all(
        all(load["collections"][c][field] == run1["collections"][c][field]
            for field in ("source_rows", "inserted", "docs_after", "ns_docs_after"))
        and sorted(load["collections"][c]["indexes"]) == sorted(run1["collections"][c]["indexes"])
        and all(load["collections"][c][field] and run1["collections"][c][field]
                for field in ("dropped", "recreated"))
        for c in UNIT_COLLECTIONS)
    return {
        "kind": "recon-report",
        "unit": "U0",
        "namespace": NS_VALUE,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_mode": "fixture",
        "harness": {"result": ".migration/recon/U0/result.json",
                    "verdict": result["verdict"], "seed": result["seed"],
                    "params": result["params"]},
        "checks": checks,
        "values_recomputed_from_target": True,
        "idempotency_rerun": {
            "performed": True,
            "result": "pass" if same_output else "fail",
            "evidence": (
                ".migration/recon/U0/load_report.run1.json vs load_report.json "
                "(source_rows/inserted/docs_after/ns_docs_after/indexes equal; "
                "both runs dropped+recreated); final-state content graded by harness result.json"
            ),
        },
        "planted_anomaly_detections": {
            "expected_set": planted,
            "actual_set": [],
            "missing": planted,
            "unexpected": [],
        },
        "unverified_paths": [
            "LIVE-mode recon gate against the parent's uncontended window (parent-run responsibility; this report is run_mode=fixture)",
            "Tier 4 app-level parity (no recorded ops for U0; PKG_OW_UTL.F_CODE_DESC / fn_list_plans read paths are not rewritten in this unit)",
            "Stratified sampling path of the harness (Tier 3 ran full_diff: all U0 populations are below the row threshold)",
            "Derived read-time `plans.tier` DECODE (unpersisted by design; graded by the consuming unit)",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--uri-secret", default="MONGODB_ATLAS_URI")
    p.add_argument("--out", default=str(OUT_DIR / "u0.recon.json"))
    args = p.parse_args(argv)
    uri = os.environ.get(args.uri_secret)
    if not uri:
        raise SystemExit(f"secret {args.uri_secret} not set")
    db = MongoClient(uri)[TARGET_DB]
    target = {
        "counts": {c: db[c].count_documents({}) for c in UNIT_COLLECTIONS},
        "ns_counts": {c: db[c].count_documents({"ns": NS_VALUE}) for c in UNIT_COLLECTIONS},
        "codes_indexes": [ix["name"] for ix in db["codes"].list_indexes()],
        "codes_key_shape_ok": db["codes"].count_documents(
            {"$expr": {"$regexMatch": {"input": "$_key", "regex": r"^[A-Z_]+:\d+$"}}}),
    }
    report = build(json.loads((OUT_DIR / "result.json").read_text()),
                   json.loads((OUT_DIR / "load_report.json").read_text()),
                   json.loads((OUT_DIR / "load_report.run1.json").read_text()),
                   target, json.loads(MANIFEST.read_text()))
    Path(args.out).write_text(json.dumps(report, indent=2) + "\n")
    failed = [c["id"] for c in report["checks"] if c["result"] != "pass"]
    idempotency_failed = report["idempotency_rerun"]["result"] != "pass"
    anomaly_failures = (
        report["planted_anomaly_detections"]["missing"]
        + report["planted_anomaly_detections"]["unexpected"]
    )
    print(f"wrote {args.out}; checks={len(report['checks'])} failed={failed} "
          f"idempotency_failed={idempotency_failed} anomaly_failures={anomaly_failures}")
    return 1 if failed or anomaly_failures or idempotency_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
