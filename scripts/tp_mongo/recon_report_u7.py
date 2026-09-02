"""Emit the repo-schema recon report for U7 (PKG_RATING → ow_billing.rating)."""

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
from load_u5 import NS_VALUE, TARGET_DB
from load_u7 import PREFIX, SOURCE_COLLECTIONS, UNIT_COLLECTIONS

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / ".migration/recon/U7"
MANIFEST = ROOT / "testdata/legacy/manifests/demo.json"
SCENARIOS = [f"RATING-{n:03d}" for n in range(1, 9)]
# Shared (U5/U0) collections the replay must leave untouched: expected doc counts.
SHARED_EXPECTED = {
    "subscriptions": 69,
    "usage_events": 814,
    "rating_periods": 3,
    "plans": 3,
    "tenants": 69,
}
# Clone state after the Tier-4 replay: RATING-008 finalizes one new period for tenant 1.
CLONE_AFTER_REPLAY = {"rating_periods": 4, "rating_periods.results": 4}


def _check(cid: str, expected: Any, actual: Any, truth: str) -> dict[str, Any]:
    return {
        "id": cid,
        "expected": expected,
        "actual": actual,
        "source_of_truth": truth,
        "result": "pass" if expected == actual else "fail",
    }


def _same_load(load: dict, run1: dict, collection: str) -> bool:
    current, prior = load["collections"][collection], run1["collections"][collection]
    return (
        all(current[f] == prior[f] for f in ("source_rows", "inserted", "docs_after", "ns_docs_after"))
        and sorted(current["indexes"]) == sorted(prior["indexes"])
        and current["dropped"] and prior["dropped"] and current["recreated"] and prior["recreated"]
        and current.get("embedded") == prior.get("embedded")
    )


def _embedded_count(database: Any, collection: str, field: str) -> int:
    row = next(
        database[collection].aggregate([
            {"$project": {"n": {"$size": {"$ifNull": [f"${field}", []]}}}},
            {"$group": {"_id": None, "total": {"$sum": "$n"}}},
        ]),
        {"total": 0},
    )
    return row["total"]


def build(result: dict, load: dict, run1: dict, provenance: dict, target: dict[str, Any], manifest: dict) -> dict[str, Any]:
    tiers = {tier["tier"]: tier for tier in result["tiers"]}
    checks = [
        _check("harness.verdict", "PASS", result["verdict"], "result.json"),
        _check("harness.mapping_version", "v1.0.1", result["mapping_version"], "result.json"),
        _check("harness.tolerance_version", "v1", result["tolerance_version"], "result.json"),
        _check("harness.warnings_ungraded", [], result.get("warnings", []), "result.json"),
        _check("harness.tier3.embeds_graded.replay_u7_rating_periods.results", 3,
               tiers[3]["stats"].get("embeds_graded", {}).get("replay_u7_rating_periods.results"),
               "result.json tier3 stats"),
        _check("harness.tier4.ops_replayed", len(SCENARIOS), tiers[4]["checks_run"], "result.json tier4 checks_run"),
    ]
    for number, tier in sorted(tiers.items()):
        checks.append(_check(f"harness.tier{number}.{tier['name']}", True, tier["passed"], "result.json"))
    checks.append(_check("tier4.transcripts.oracle_source_sha_matches_repo", True,
                         provenance["transcripts_match"], "tier4_provenance.json vs procs/harness/oracle_record.oracle_source_sha"))
    checks.append(_check("tier4.transcripts.scenarios", SCENARIOS, provenance["scenarios"], "tier4_provenance.json"))
    for collection, expected in SHARED_EXPECTED.items():
        checks.append(_check(f"shared.{collection}.count_unchanged", expected, target["shared_counts"][collection],
                             "Atlas count_documents (U5/U0 golden, must not be mutated by U7)"))
    checks.append(_check("shared.billing_audit_log.no_rating_rows", 0, target["shared_audit_rating_rows"],
                         "Atlas count_documents({module: 'RATING'}) on the shared audit log"))
    checks.append(_check("clone.replay_u7_rating_periods.count_after_replay", CLONE_AFTER_REPLAY["rating_periods"],
                         target["clone_rating_periods"], "Atlas count_documents"))
    checks.append(_check("clone.replay_u7_rating_periods.results_after_replay", CLONE_AFTER_REPLAY["rating_periods.results"],
                         target["clone_results"], "Atlas $sum($size(results))"))
    checks.append(_check("clone.replay_u7_rating_periods.finalized_period_single_result", 1,
                         target["finalized_result_count"], "Atlas rating_periods.results length for RATING-008 period"))
    checks.append(_check("clone.replay_u7_rating_periods.ns_tagged", target["clone_rating_periods"],
                         target["clone_rating_periods_ns"], f"Atlas count_documents({{ns: {NS_VALUE!r}}})"))
    checks.append(_check("clone.replay_u7_rating_periods.unique_index", True, target["clone_unique_index"], "Atlas list_indexes"))
    checks.append(_check("load.target_db", TARGET_DB, load["target_db"], "load_report.json"))
    checks.append(_check("load.collections_owned", sorted(UNIT_COLLECTIONS), sorted(load["collections"]), "load_report.json"))
    checks.append(_check("load.clone_sources", sorted(SOURCE_COLLECTIONS),
                         sorted(v["cloned_from"] for k, v in load["collections"].items() if "cloned_from" in v), "load_report.json"))

    planted = sorted(
        f"{a['kind']}:{a['count']}" for a in manifest["planted_anomalies"]
        if a["target"].startswith("oracle.OW_BILLING.")
        and a["target"].split(".")[2] in {"SUBSCRIPTIONS", "USAGE_EVENTS", "RATING_PERIODS", "RATING_RESULTS", "PLANS"}
    )
    same_output = all(_same_load(load, run1, c) for c in UNIT_COLLECTIONS)
    return {
        "kind": "recon-report",
        "unit": "U7",
        "namespace": NS_VALUE,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_mode": "fixture",
        "harness": {
            "result": ".migration/recon/U7/result.json",
            "verdict": result["verdict"],
            "seed": result["seed"],
            "params": result["params"],
            "harness_cli_mode": "live",
        },
        "checks": checks,
        "values_recomputed_from_target": True,
        "idempotency_rerun": {
            "performed": True,
            "result": "pass" if same_output else "fail",
            "evidence": (
                ".migration/recon/U7/load_report.run1.json vs load_report.json "
                "(source_rows/inserted/docs_after/ns_docs_after/indexes and embedded counts equal; "
                f"both runs dropped+recreated only `{PREFIX}*` collections)"
            ),
        },
        "planted_anomaly_detections": {
            "expected_set": planted,
            "actual_set": [],
            "missing": planted,
            "unexpected": [],
        },
        "unverified_paths": [
            "LIVE-mode recon gate (parent)",
            (
                "billing_audit_log NOT graded T1-T3 for U7: write-only sink for rating; the U5 golden carries 1 "
                "observer-caused BILLING_AUDIT_LOG row absent from a fresh fixture (run 1 FAIL kept as result.run1.json)"
            ),
            "Tier 4 source side is the recorded Oracle transcript (procs/oracle/transcripts/rating), not a live PL/SQL call",
            "TRG_USAGE_EVENTS_CHECK kind_cd-in-CODES branch: rating never inserts usage_events; still no app write path (usage ingest is not a PKG_RATING member)",
            "sp_finalize_rating DUP_VAL_ON_INDEX on `id` (period id) vs (tenant_id, period_start): both keys derive from the same inputs, only the unique-index path exercised",
            "Suspension proration (status 20): no fixture subscription is suspended inside a graded period; covered by unit tests only",
            "NULL plan / no-subscription propagation: covered by unit tests only (fixture tenants all have a plan)",
            "HTTP route exposure of fn_usage_rating/fn_usage_summary/sp_finalize_rating: not wired (module + Tier-4 replay only)",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri-secret", default="MONGODB_ATLAS_URI")
    parser.add_argument("--out", default=str(OUT_DIR / "u7.recon.json"))
    args = parser.parse_args(argv)
    uri = os.environ.get(args.uri_secret)
    if not uri:
        raise SystemExit(f"secret {args.uri_secret} not set")
    database = MongoClient(uri)[TARGET_DB]
    clone = database[f"{PREFIX}rating_periods"]
    finalized = clone.find_one({"tenant_id": "00000000-0000-0000-0000-000000000001",
                                "period_start": datetime(2026, 2, 1)})  # noqa: DTZ001
    target = {
        "shared_counts": {c: database[c].count_documents({}) for c in SHARED_EXPECTED},
        "shared_audit_rating_rows": database["billing_audit_log"].count_documents({"module": "RATING"}),
        "clone_rating_periods": clone.count_documents({}),
        "clone_rating_periods_ns": clone.count_documents({"ns": NS_VALUE}),
        "clone_results": _embedded_count(database, f"{PREFIX}rating_periods", "results"),
        "finalized_result_count": len(finalized["results"]) if finalized else None,
        "clone_unique_index": any(i["name"] == "tenant_id_1_period_start_1" and i.get("unique") is True
                                  for i in clone.list_indexes()),
    }
    report = build(
        json.loads((OUT_DIR / "result.json").read_text()),
        json.loads((OUT_DIR / "load_report.json").read_text()),
        json.loads((OUT_DIR / "load_report.run1.json").read_text()),
        json.loads((OUT_DIR / "tier4_provenance.json").read_text()),
        target,
        json.loads(MANIFEST.read_text()),
    )
    Path(args.out).write_text(json.dumps(report, indent=2) + "\n")
    failed = [c["id"] for c in report["checks"] if c["result"] != "pass"]
    idem = report["idempotency_rerun"]["result"] != "pass"
    anomalies = report["planted_anomaly_detections"]["missing"] + report["planted_anomaly_detections"]["unexpected"]
    print(f"wrote {args.out}; checks={len(report['checks'])} failed={failed} idempotency_failed={idem} anomaly_failures={anomalies}")
    return 1 if failed or anomalies or idem else 0


if __name__ == "__main__":
    raise SystemExit(main())
