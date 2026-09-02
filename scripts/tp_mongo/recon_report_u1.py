"""Emit the repo-schema recon report (`*.recon.json`) for U1.

Wraps the harness `result.json` (the verdict authority; never re-graded here) and the two
loader reports, recomputing target-side counts live from Atlas so the report never carries
copied numbers. Checks are pass/fail by comparison only.
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
from load_u1 import (
    NS_VALUE,
    QUARANTINE_COLLECTIONS,
    QUARANTINE_DB,
    SEQUENCES,
    TARGET_DB,
    UNIT_COLLECTIONS,
)

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / ".migration/recon/U1"
MANIFEST = ROOT / "testdata/legacy/manifests/demo.json"
EXPECTED_ROWS = {"customers": 25000, "customers_history": 0, "counters": 3}
EXPECTED_EMBEDDED = 8333
EXPECTED_QUARANTINE = {"dirty_signup_dt": 50, "bad_csv_list": 31}
ANOMALY_CLASS = {"dirty_dates": "dirty_signup_dt", "malformed_csv_lists": "bad_csv_list"}
U1_SOURCE_TABLES = {"CUSTOMER_MASTER", "ENTITY_ATTR_VALUE", "CUSTOMER_MASTER_HIST"}
CUSTOMERS_INDEXES = {"_id_", "tenant_id_1_cust_no_1", "cust_name_upper_1", "conversion_batch_no_1"}
QUARANTINE_CEILING = 0.005


def _check(cid: str, expected: Any, actual: Any, truth: str) -> dict[str, Any]:
    return {"id": cid, "expected": expected, "actual": actual, "source_of_truth": truth,
            "result": "pass" if expected == actual else "fail"}


def _same_load(load: dict, run1: dict, coll: dict, coll1: dict) -> bool:
    return (
        all(coll[f] == coll1[f] for f in ("inserted", "docs_after", "ns_docs_after"))
        and sorted(coll["indexes"]) == sorted(coll1["indexes"])
        and coll["dropped"] and coll1["dropped"] and coll["recreated"] and coll1["recreated"]
        and load["source_rows"] == run1["source_rows"]
    )


def build(result: dict, load: dict, run1: dict, target: dict[str, Any],
          manifest: dict) -> dict[str, Any]:
    tiers = {t["tier"]: t for t in result["tiers"]}
    checks = [
        _check("harness.verdict", "PASS", result["verdict"], ".migration/recon/U1/result.json"),
        _check("harness.mapping_version", "v1.0.1", result["mapping_version"], "result.json"),
        _check("harness.tolerance_version", "v1", result["tolerance_version"], "result.json"),
        _check("harness.warnings_ungraded", [], result.get("warnings", []), "result.json"),
        _check("harness.tier3.embeds_graded.customers.attributes", EXPECTED_EMBEDDED,
               tiers[3]["stats"].get("embeds_graded", {}).get("customers.attributes"),
               "result.json tier3 stats"),
    ]
    for n, t in sorted(tiers.items()):
        checks.append(_check(f"harness.tier{n}.{t['name']}", True, t["passed"], "result.json"))
    for coll, expected in EXPECTED_ROWS.items():
        checks.append(_check(f"target.{coll}.count", expected, target["counts"][coll],
                             "Atlas count_documents"))
        checks.append(_check(f"target.{coll}.ns_tagged", target["counts"][coll],
                             target["ns_counts"][coll],
                             f"Atlas count_documents({{ns: {NS_VALUE!r}}})"))
    checks.append(_check("target.customers.embedded_attributes", EXPECTED_EMBEDDED,
                         target["embedded_attributes"], "Atlas $sum($size(attributes))"))
    checks.append(_check("target.customers.attributes_eav_id_unique", EXPECTED_EMBEDDED,
                         target["distinct_eav_ids"], "Atlas $unwind/$group distinct eav_id"))
    checks.append(_check("target.customers.batch_scoped", target["counts"]["customers"],
                         target["batch_scoped"], "Atlas count_documents({conversion_batch_no})"))
    checks.append(_check("target.customers.indexes", sorted(CUSTOMERS_INDEXES),
                         sorted(target["customers_indexes"]), "Atlas list_indexes"))
    checks.append(_check("target.counters.seeded_at_last_number",
                         load["collections"]["counters"]["seeded"], target["counters"],
                         "Atlas counters find() vs USER_SEQUENCES.LAST_NUMBER at load"))
    checks.append(_check("target.counters.sequence_set", sorted(s.lower() for s in SEQUENCES),
                         sorted(target["counters"]), "Atlas counters _id set"))
    for q, expected in EXPECTED_QUARANTINE.items():
        checks.append(_check(f"quarantine.{q}.count", expected, target["quarantine"][q],
                             f"Atlas {QUARANTINE_DB}.{q} count_documents"))
        checks.append(_check(f"quarantine.{q}.under_ceiling", True,
                             target["quarantine"][q] <= QUARANTINE_CEILING * EXPECTED_ROWS["customers"],
                             "tolerances v1 quarantine ceiling 0.5%"))
    checks.append(_check("quarantine.rows_still_migrated", EXPECTED_QUARANTINE["dirty_signup_dt"],
                         target["dirty_rows_present"],
                         "Atlas customers count where signup_date is null and signup_dt non-null"))
    checks.append(_check("load.target_db", TARGET_DB, load["target_db"], "load_report.json"))
    checks.append(_check("load.quarantine_db", QUARANTINE_DB, load["quarantine_db"], "load_report.json"))
    checks.append(_check("load.collections_owned", sorted(UNIT_COLLECTIONS),
                         sorted(c for c in load["collections"] if c != "quarantine"),
                         "load_report.json"))
    checks.append(_check("load.quarantine_owned", sorted(QUARANTINE_COLLECTIONS),
                         sorted(load["collections"]["quarantine"]), "load_report.json"))

    planted = sorted(
        f"{a['kind']}:{a['count']}" for a in manifest["planted_anomalies"]
        if a["target"].startswith("oracle.OW_BILLING.")
        and a["target"].split(".")[2] in U1_SOURCE_TABLES)
    actual = sorted(
        f"{kind}:{target['quarantine'][cls]}" for kind, cls in ANOMALY_CLASS.items())
    same_output = all(
        _same_load(load, run1, load["collections"][c], run1["collections"][c])
        for c in UNIT_COLLECTIONS
    ) and all(
        _same_load(load, run1, load["collections"]["quarantine"][q],
                   run1["collections"]["quarantine"][q])
        for q in QUARANTINE_COLLECTIONS
    )
    return {
        "kind": "recon-report",
        "unit": "U1",
        "namespace": NS_VALUE,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_mode": "fixture",
        "harness": {"result": ".migration/recon/U1/result.json",
                    "verdict": result["verdict"], "seed": result["seed"],
                    "params": result["params"]},
        "checks": checks,
        "values_recomputed_from_target": True,
        "idempotency_rerun": {
            "performed": True,
            "result": "pass" if same_output else "fail",
            "evidence": (
                ".migration/recon/U1/load_report.run1.json vs load_report.json "
                "(source_rows/inserted/docs_after/ns_docs_after/indexes equal for the 3 unit "
                "and 2 quarantine collections; both runs dropped+recreated only those); "
                "final-state content graded by harness result.json"
            ),
        },
        "planted_anomaly_detections": {
            "expected_set": planted,
            "actual_set": actual,
            "missing": sorted(set(planted) - set(actual)),
            "unexpected": sorted(set(actual) - set(planted)),
        },
        "unverified_paths": [
            "LIVE-mode recon gate against the parent's uncontended window (parent-run responsibility; this report is run_mode=fixture)",
            "Tier 4 app-level parity: customer write path (customer_writes.py: counters allocation, cust_name_upper, row_version_no, customers_history append) is unit-scoped code with no recorded ops; customers_history graded only as an empty collection",
            "Derived ungraded twins per mapping derived_ungraded (signup_date, last_activity_date, related_accounts, child_accounts, promo_codes, addresses, phones) — unit-tested, not recon-graded",
            "RPT-114 /api/reports/reconciliation balances aggregation: Oracle BALANCES_SQL vs aggregation compared once in .migration/recon/U1/rpt114_balances.json and via Flask test client (200 + 503 fail-closed); route not exercised under gunicorn",
            "Stratified sampling path of the harness (Tier 3 ran full_diff: 25,000 < 100,000 threshold)",
            "counters are not in the mapping spec's collections (D11 seeds); graded here by comparison to USER_SEQUENCES.LAST_NUMBER, not by the harness",
            "Load swap: per-collection staging+rename is atomic per collection only; a reader may observe a partially swapped unit during the five renames. Write path: a history insert failing after a committed mutation loses the image (no phantom history)",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--uri-secret", default="MONGODB_ATLAS_URI")
    p.add_argument("--out", default=str(OUT_DIR / "u1.recon.json"))
    args = p.parse_args(argv)
    uri = os.environ.get(args.uri_secret)
    if not uri:
        raise SystemExit(f"secret {args.uri_secret} not set")
    client = MongoClient(uri)
    db = client[TARGET_DB]
    qdb = client[QUARANTINE_DB]
    load = json.loads((OUT_DIR / "load_report.json").read_text())
    embedded = next(db["customers"].aggregate([
        {"$project": {"n": {"$size": "$attributes"}}},
        {"$group": {"_id": None, "total": {"$sum": "$n"}}}]), {"total": 0})["total"]
    distinct = next(db["customers"].aggregate([
        {"$unwind": "$attributes"},
        {"$group": {"_id": "$attributes.eav_id"}},
        {"$count": "n"}]), {"n": 0})["n"]
    target = {
        "counts": {c: db[c].count_documents({}) for c in UNIT_COLLECTIONS},
        "ns_counts": {c: db[c].count_documents({"ns": NS_VALUE}) for c in UNIT_COLLECTIONS},
        "embedded_attributes": embedded,
        "distinct_eav_ids": distinct,
        "batch_scoped": db["customers"].count_documents({"conversion_batch_no": load["batch_no"]}),
        "customers_indexes": [ix["name"] for ix in db["customers"].list_indexes()],
        "counters": {d["_id"]: int(d["seq"]) for d in db["counters"].find()},
        "quarantine": {q: qdb[q].count_documents({"ns": NS_VALUE}) for q in QUARANTINE_COLLECTIONS},
        "dirty_rows_present": db["customers"].count_documents(
            {"signup_date": None, "signup_dt": {"$ne": None}}),
    }
    report = build(json.loads((OUT_DIR / "result.json").read_text()), load,
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
