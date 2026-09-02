"""Emit the repo-schema recon report for U8 (PKG_INVOICING → ow_billing.invoicing)."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from load_u5 import NS_VALUE, TARGET_DB
from load_u8 import PREFIX, SOURCE_COLLECTIONS, UNIT_COLLECTIONS
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / ".migration/recon/U8"
MANIFEST = ROOT / "testdata/legacy/manifests/demo.json"
SCENARIOS = [f"INVOICE-{number:03d}" for number in range(1, 7)]
SHARED_EXPECTED = {
    "subscriptions": 69,
    "usage_events": 814,
    "rating_periods": 3,
    "billing_invoices": 3,
    "credit_notes": 5,
    "billing_audit_log": 1,
    "plans": 3,
    "tenants": 69,
}
CLONE_AFTER_REPLAY = {
    "billing_invoices": 6,
    "billing_invoices.lines": 17,
    "credit_notes.tenant_9.remaining": ["0.00", "6.96"],
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
    current, prior = load["collections"][collection], run1["collections"][collection]
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


def _embedded_count(database: Any, collection: str, field: str) -> int:
    row = next(
        database[collection].aggregate(
            [
                {"$project": {"n": {"$size": {"$ifNull": [f"${field}", []]}}}},
                {"$group": {"_id": None, "total": {"$sum": "$n"}}},
            ]
        ),
        {"total": 0},
    )
    return row["total"]


def build(
    result: dict,
    load: dict,
    run1: dict,
    provenance: dict,
    target: dict[str, Any],
    manifest: dict,
) -> dict[str, Any]:
    tiers = {tier["tier"]: tier for tier in result["tiers"]}
    checks = [
        _check("harness.verdict", "PASS", result["verdict"], "result.json"),
        _check("harness.mapping_version", "v1.0.1", result["mapping_version"], "result.json"),
        _check("harness.tolerance_version", "v1", result["tolerance_version"], "result.json"),
        _check("harness.warnings_ungraded", [], result.get("warnings", []), "result.json"),
        _check(
            "harness.tier3.embeds_graded.replay_u8_billing_invoices.lines",
            2,
            tiers[3]["stats"].get("embeds_graded", {}).get(
                "replay_u8_billing_invoices.lines"
            ),
            "result.json tier3 stats",
        ),
        _check(
            "harness.tier4.ops_replayed",
            len(SCENARIOS),
            tiers[4]["checks_run"],
            "result.json tier4 checks_run",
        ),
    ]
    for number, tier in sorted(tiers.items()):
        checks.append(
            _check(
                f"harness.tier{number}.{tier['name']}",
                True,
                tier["passed"],
                "result.json",
            )
        )
    checks.extend(
        [
            _check(
                "tier4.transcripts.oracle_source_sha_matches_repo",
                True,
                provenance["transcripts_match"],
                "tier4_provenance.json vs oracle_record.oracle_source_sha",
            ),
            _check(
                "tier4.transcripts.scenarios",
                SCENARIOS,
                provenance["scenarios"],
                "tier4_provenance.json",
            ),
        ]
    )
    for collection, expected in SHARED_EXPECTED.items():
        checks.append(
            _check(
                f"shared.{collection}.count_unchanged",
                expected,
                target["shared_counts"][collection],
                "Atlas count_documents (U5/U0 golden, must not be mutated by U8)",
            )
        )
    checks.extend(
        [
            _check(
                "shared.billing_audit_log.no_invoicing_rows",
                0,
                target["shared_audit_invoicing_rows"],
                "Atlas count_documents({module: 'INVOICING'}) on the shared audit log",
            ),
            _check(
                "clone.replay_u8_billing_invoices.count_after_replay",
                CLONE_AFTER_REPLAY["billing_invoices"],
                target["clone_billing_invoices"],
                "Atlas count_documents",
            ),
            _check(
                "clone.replay_u8_billing_invoices.lines_after_replay",
                CLONE_AFTER_REPLAY["billing_invoices.lines"],
                target["clone_invoice_lines"],
                "Atlas $sum($size(lines))",
            ),
            _check(
                "clone.replay_u8_billing_invoices.ns_tagged",
                target["clone_billing_invoices"],
                target["clone_billing_invoices_ns"],
                f"Atlas count_documents({{ns: {NS_VALUE!r}}})",
            ),
            _check(
                "clone.replay_u8_credit_notes.invoice_003_remaining",
                CLONE_AFTER_REPLAY["credit_notes.tenant_9.remaining"],
                target["clone_credit_remaining"],
                "Atlas credit_notes remaining_amount ordered by issued_on, _id",
            ),
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
                "load.clone_sources",
                sorted(SOURCE_COLLECTIONS),
                sorted(
                    value["cloned_from"]
                    for value in load["collections"].values()
                    if "cloned_from" in value
                ),
                "load_report.json",
            ),
        ]
    )

    planted = sorted(
        f"{anomaly['kind']}:{anomaly['count']}"
        for anomaly in manifest["planted_anomalies"]
        if anomaly["target"].startswith("oracle.OW_BILLING.")
        and anomaly["target"].split(".")[2]
        in {"INVOICES", "INVOICE_LINES", "CREDIT_NOTES"}
    )
    same_output = all(_same_load(load, run1, collection) for collection in UNIT_COLLECTIONS)
    return {
        "kind": "recon-report",
        "unit": "U8",
        "namespace": NS_VALUE,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_mode": "fixture",
        "harness": {
            "result": ".migration/recon/U8/result.json",
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
                ".migration/recon/U8/load_report.run1.json vs load_report.json "
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
            "Sibling U9 collection `replay_u9_subscriptions_history` (empty) appeared in the target DB during this run — different prefix, not a U8 write target, untouched",
            "Tier 4 source side is the recorded Oracle transcript, not a live PL/SQL call",
            (
                "No multi-document transaction spans finalize_rating, replaceOne, and credit updates; "
                "all NOT-NULL validation occurs before the first invoice write, while partial failure "
                "between writes is unexercised"
            ),
            "NULL plan, exempt tenant, and no-credit-note branches are unit-tested only unless covered by a scenario",
            "HTTP route exposure of fn_invoice_preview, sp_issue_invoice, and fn_invoice_lines is not wired",
            "billing_audit_log is not graded T1-T3; shared-log INVOICING isolation is checked separately",
            "Credit-note ordering ties are covered by the fixture scenario; concurrent credit updates are unexercised",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri-secret", default="MONGODB_ATLAS_URI")
    parser.add_argument("--out", default=str(OUT_DIR / "u8.recon.json"))
    args = parser.parse_args(argv)
    uri = os.environ.get(args.uri_secret)
    if not uri:
        raise SystemExit(f"secret {args.uri_secret} not set")
    database = MongoClient(uri)[TARGET_DB]
    clone_invoices = database[f"{PREFIX}billing_invoices"]
    clone_credits = database[f"{PREFIX}credit_notes"]
    tenant_9_credits = list(
        clone_credits.find({"tenant_id": "00000000-0000-0000-0000-000000000009"}).sort(
            [("issued_on", 1), ("_id", 1)]
        )
    )
    target = {
        "shared_counts": {
            collection: database[collection].count_documents({})
            for collection in SHARED_EXPECTED
        },
        "shared_audit_invoicing_rows": database["billing_audit_log"].count_documents(
            {"module": "INVOICING"}
        ),
        "clone_billing_invoices": clone_invoices.count_documents({}),
        "clone_billing_invoices_ns": clone_invoices.count_documents({"ns": NS_VALUE}),
        "clone_invoice_lines": _embedded_count(
            database, f"{PREFIX}billing_invoices", "lines"
        ),
        "clone_credit_remaining": [
            format(row["remaining_amount"].to_decimal(), "f")
            if hasattr(row.get("remaining_amount"), "to_decimal")
            else str(row.get("remaining_amount"))
            for row in tenant_9_credits
        ],
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
    failed = [check["id"] for check in report["checks"] if check["result"] != "pass"]
    idempotency_failed = report["idempotency_rerun"]["result"] != "pass"
    anomalies = (
        report["planted_anomaly_detections"]["missing"]
        + report["planted_anomaly_detections"]["unexpected"]
    )
    print(
        f"wrote {args.out}; checks={len(report['checks'])} failed={failed} "
        f"idempotency_failed={idempotency_failed} anomaly_failures={anomalies}"
    )
    return 1 if failed or anomalies or idempotency_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
