"""Emit the repo-schema recon report for U5."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bson import Int64
from pymongo import MongoClient
from pymongo.errors import WriteError

sys.path.insert(0, str(Path(__file__).resolve().parent))
from load_u5 import (
    NS_VALUE,
    TARGET_DB,
    TTL_SECONDS,
    UNIT_COLLECTIONS,
    USAGE_EVENTS_VALIDATOR,
)

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / ".migration/recon/U5"
MANIFEST = ROOT / "testdata/legacy/manifests/demo.json"
EXPECTED_ROWS = {
    "subscriptions": 69,
    "subscriptions_history": 0,
    "usage_events": 814,
    "rating_periods": 3,
    "billing_invoices": 3,
    "credit_notes": 5,
    "dunning_attempts": 1,
    "notifications": 1,
    "billing_audit_log": 0,
}
EXPECTED_EMBEDDED = {"rating_periods.results": 3, "billing_invoices.lines": 2}
U5_SOURCE_TABLES = {
    "SUBSCRIPTIONS",
    "SUBSCRIPTIONS_HIST",
    "USAGE_EVENTS",
    "RATING_PERIODS",
    "RATING_RESULTS",
    "INVOICES",
    "INVOICE_LINES",
    "CREDIT_NOTES",
    "DUNNING_ATTEMPTS",
    "NOTIFICATIONS",
    "BILLING_AUDIT_LOG",
}


def _check(cid: str, expected: Any, actual: Any, truth: str) -> dict[str, Any]:
    return {
        "id": cid,
        "expected": expected,
        "actual": actual,
        "source_of_truth": truth,
        "result": "pass" if expected == actual else "fail",
    }


def _same_load(load: dict, run1: dict, collection: str) -> bool:
    current = load["collections"][collection]
    prior = run1["collections"][collection]
    return (
        all(
            current[field] == prior[field]
            for field in ("source_rows", "inserted", "docs_after", "ns_docs_after")
        )
        and sorted(current["indexes"]) == sorted(prior["indexes"])
        and current["dropped"]
        and prior["dropped"]
        and current["recreated"]
        and prior["recreated"]
        and current.get("embedded") == prior.get("embedded")
    )


def build(
    result: dict,
    load: dict,
    run1: dict,
    target: dict[str, Any],
    manifest: dict,
) -> dict[str, Any]:
    tiers = {tier["tier"]: tier for tier in result["tiers"]}
    checks = [
        _check("harness.verdict", "PASS", result["verdict"], "result.json"),
        _check("harness.mapping_version", "v1.0.1", result["mapping_version"], "result.json"),
        _check("harness.tolerance_version", "v1", result["tolerance_version"], "result.json"),
        _check("harness.warnings_ungraded", [], result.get("warnings", []), "result.json"),
    ]
    for name, expected in EXPECTED_EMBEDDED.items():
        checks.append(
            _check(
                f"harness.tier3.embeds_graded.{name}",
                expected,
                tiers[3]["stats"].get("embeds_graded", {}).get(name),
                "result.json tier3 stats",
            )
        )
    for number, tier in sorted(tiers.items()):
        checks.append(_check(f"harness.tier{number}.{tier['name']}", True, tier["passed"], "result.json"))
    for collection, expected in EXPECTED_ROWS.items():
        checks.append(
            _check(
                f"target.{collection}.count",
                expected,
                target["counts"][collection],
                "Atlas count_documents",
            )
        )
        checks.append(
            _check(
                f"target.{collection}.ns_tagged",
                expected,
                target["ns_counts"][collection],
                f"Atlas count_documents({{ns: {NS_VALUE!r}}})",
            )
        )
    for name, expected in EXPECTED_EMBEDDED.items():
        checks.append(
            _check(
                f"target.{name}",
                expected,
                target["embedded"][name],
                "Atlas $sum($size(embed))",
            )
        )
    checks.extend(
        [
            _check(
                "load.target_db",
                TARGET_DB,
                load["target_db"],
                "load_report.json",
            ),
            _check(
                "load.collections_owned",
                sorted(UNIT_COLLECTIONS),
                sorted(load["collections"]),
                "load_report.json",
            ),
            _check(
                "target.usage_events.validator",
                USAGE_EVENTS_VALIDATOR,
                target["usage_events_validator"],
                "Atlas listCollections",
            ),
            _check(
                "target.billing_audit_log.ttl",
                TTL_SECONDS,
                target["billing_audit_log_ttl"],
                "Atlas list_indexes",
            ),
            _check(
                "target.dunning_attempts.unique_index",
                True,
                target["unique_indexes"]["dunning_attempts"],
                "Atlas list_indexes",
            ),
            _check(
                "target.notifications.unique_index",
                True,
                target["unique_indexes"]["notifications"],
                "Atlas list_indexes",
            ),
            _check(
                "target.rating_periods.unique_index",
                True,
                target["unique_indexes"]["rating_periods"],
                "Atlas list_indexes",
            ),
            _check(
                "target.usage_events.rejects_zero_units",
                True,
                target["usage_events_rejects_zero_units"],
                "Atlas validator probe",
            ),
        ]
    )

    planted = sorted(
        f"{anomaly['kind']}:{anomaly['count']}"
        for anomaly in manifest["planted_anomalies"]
        if anomaly["target"].startswith("oracle.OW_BILLING.")
        and anomaly["target"].split(".")[2] in U5_SOURCE_TABLES
    )
    same_output = all(_same_load(load, run1, collection) for collection in UNIT_COLLECTIONS)
    return {
        "kind": "recon-report",
        "unit": "U5",
        "namespace": NS_VALUE,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_mode": "fixture",
        "harness": {
            "result": ".migration/recon/U5/result.json",
            "verdict": result["verdict"],
            "seed": result["seed"],
            "params": result["params"],
        },
        "checks": checks,
        "values_recomputed_from_target": True,
        "idempotency_rerun": {
            "performed": True,
            "result": "pass" if same_output else "fail",
            "evidence": (
                ".migration/recon/U5/load_report.run1.json vs load_report.json "
                "(source_rows/inserted/docs_after/ns_docs_after/indexes and embedded counts equal; "
                "both runs dropped+recreated only U5 collections)"
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
            "Tier 4 app-level parity — PL/SQL packages not rewritten in this unit (D10, U6–U9)",
            "TRG_USAGE_EVENTS_CHECK kind_cd-must-exist-in-CODES branch: cross-collection, not expressible in $jsonSchema; deferred to the app write path (U7)",
            "counters seeding for SEQ_SUBSCRIPTIONS_HIST / SEQ_BILLING_AUDIT_LOG: `counters` is U1's registered target, not written by U5",
            "TTL expiry on billing_audit_log not observed (0 rows; index options verified only)",
            "harness stratified sampling path (populations below threshold → full diff)",
        ],
    }


def _embedded_count(database: Any, collection: str, field: str) -> int:
    row = next(
        database[collection].aggregate(
            [
                {"$project": {"n": {"$size": f"${field}"}}},
                {"$group": {"_id": None, "total": {"$sum": "$n"}}},
            ]
        ),
        {"total": 0},
    )
    return row["total"]


def _usage_validator(database: Any) -> dict[str, Any] | None:
    response = database.command("listCollections", filter={"name": "usage_events"})
    batch = response.get("cursor", {}).get("firstBatch", [])
    return batch[0].get("options", {}).get("validator") if batch else None


def _ttl(database: Any) -> int | None:
    for index in database["billing_audit_log"].list_indexes():
        if index["key"] == {"logged_at": 1}:
            return index.get("expireAfterSeconds")
    return None


def _has_unique_index(database: Any, collection: str, name: str) -> bool:
    return any(
        index["name"] == name and index.get("unique") is True
        for index in database[collection].list_indexes()
    )


def _probe_zero_units(database: Any) -> bool:
    collection = database["usage_events"]
    before = collection.count_documents({})
    document = {
        "_id": "U5-PROBE-NEG-UNITS",
        "id": "U5-PROBE-NEG-UNITS",
        "tenant_id": "U5-PROBE",
        "occurred_at": datetime.now(timezone.utc),
        "units": Int64(0),
        "kind_cd": 1,
        "ns": NS_VALUE,
    }
    try:
        collection.insert_one(document)
    except WriteError as exc:
        accepted = exc.code == 121
    else:
        collection.delete_one({"_id": document["_id"]})
        accepted = False
    if collection.count_documents({}) != before:
        raise RuntimeError("usage_events validator probe changed collection count")
    return accepted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri-secret", default="MONGODB_ATLAS_URI")
    parser.add_argument("--out", default=str(OUT_DIR / "u5.recon.json"))
    args = parser.parse_args(argv)
    uri = os.environ.get(args.uri_secret)
    if not uri:
        raise SystemExit(f"secret {args.uri_secret} not set")
    database = MongoClient(uri)[TARGET_DB]
    target = {
        "counts": {collection: database[collection].count_documents({}) for collection in UNIT_COLLECTIONS},
        "ns_counts": {
            collection: database[collection].count_documents({"ns": NS_VALUE})
            for collection in UNIT_COLLECTIONS
        },
        "embedded": {
            "rating_periods.results": _embedded_count(database, "rating_periods", "results"),
            "billing_invoices.lines": _embedded_count(database, "billing_invoices", "lines"),
        },
        "usage_events_validator": _usage_validator(database),
        "billing_audit_log_ttl": _ttl(database),
        "unique_indexes": {
            "dunning_attempts": _has_unique_index(
                database, "dunning_attempts", "invoice_id_1_attempt_no_1"
            ),
            "notifications": _has_unique_index(
                database, "notifications", "tenant_id_1_kind_cd_1_sent_at_1"
            ),
            "rating_periods": _has_unique_index(
                database, "rating_periods", "tenant_id_1_period_start_1"
            ),
        },
        "usage_events_rejects_zero_units": _probe_zero_units(database),
    }
    report = build(
        json.loads((OUT_DIR / "result.json").read_text()),
        json.loads((OUT_DIR / "load_report.json").read_text()),
        json.loads((OUT_DIR / "load_report.run1.json").read_text()),
        target,
        json.loads(MANIFEST.read_text()),
    )
    Path(args.out).write_text(json.dumps(report, indent=2) + "\n")
    failed = [check["id"] for check in report["checks"] if check["result"] != "pass"]
    idempotency_failed = report["idempotency_rerun"]["result"] != "pass"
    anomaly_failures = (
        report["planted_anomaly_detections"]["missing"]
        + report["planted_anomaly_detections"]["unexpected"]
    )
    print(
        f"wrote {args.out}; checks={len(report['checks'])} failed={failed} "
        f"idempotency_failed={idempotency_failed} anomaly_failures={anomaly_failures}"
    )
    return 1 if failed or anomaly_failures or idempotency_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
