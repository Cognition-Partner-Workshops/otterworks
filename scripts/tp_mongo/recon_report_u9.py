"""Emit the U9 recon report and target-state evidence."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pymongo import MongoClient

from load_replay_u9 import NS_VALUE, PREFIX, SOURCE_COLLECTIONS, TARGET_DB, UNIT_COLLECTIONS

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / ".migration/recon/U9"
SCENARIOS = [f"DUNNING-{number:03d}" for number in range(1, 6)]


def _check(identifier: str, expected: Any, actual: Any, truth: str) -> dict[str, Any]:
    return {
        "id": identifier,
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
    provenance: dict,
    target: dict[str, Any],
) -> dict[str, Any]:
    tiers = {tier["tier"]: tier for tier in result["tiers"]}
    checks = [
        _check("harness.verdict", "PASS", result["verdict"], "result.json"),
        _check("harness.mapping_version", "v1.0.1", result["mapping_version"], "result.json"),
        _check("harness.tolerance_version", "v1", result["tolerance_version"], "result.json"),
        _check("harness.tier4.ops_replayed", 5, tiers[4]["checks_run"], "result.json"),
        _check(
            "tier4.transcripts.oracle_source_sha_matches_repo",
            True,
            provenance["transcripts_match"],
            "tier4_provenance.json",
        ),
        _check("tier4.transcripts.scenarios", SCENARIOS, provenance["scenarios"], "tier4_provenance.json"),
    ]
    for number, tier in sorted(tiers.items()):
        checks.append(
            _check(f"harness.tier{number}.{tier['name']}", True, tier["passed"], "result.json")
        )
    for collection in UNIT_COLLECTIONS:
        checks.extend(
            [
                _check(
                    f"clone.{collection}.count",
                    load["collections"][collection]["docs_after"],
                    target["counts"][collection],
                    "Atlas count_documents",
                ),
                _check(
                    f"clone.{collection}.ns_tagged",
                    load["collections"][collection]["ns_docs_after"],
                    target["ns_counts"][collection],
                    "Atlas count_documents({ns})",
                ),
                _check(
                    f"clone.{collection}.indexes",
                    sorted(load["collections"][collection]["indexes"]),
                    sorted(target["indexes"][collection]),
                    "Atlas list_indexes vs load report",
                ),
            ]
        )
    for source in SOURCE_COLLECTIONS:
        checks.append(
            _check(
                f"golden.{source}.untouched",
                load["collections"][f"{PREFIX}{source}"]["source_rows"],
                target["golden_counts"][source],
                "Atlas unprefixed count_documents",
            )
        )
    same_output = all(
        _same_load(load, run1, collection) for collection in UNIT_COLLECTIONS
    )
    return {
        "kind": "recon-report",
        "unit": "U9",
        "namespace": NS_VALUE,
        "prefix": PREFIX,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_mode": "fixture",
        "harness": {
            "result": ".migration/recon/U9/result.json",
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
                ".migration/recon/U9/load_report.run1.json vs load_report.json "
                "(populations, indexes, embedded counts, dropped and recreated equal)"
            ),
        },
        "planted_anomaly_detections": {
            "expected_set": [],
            "actual_set": [],
            "missing": [],
            "unexpected": [],
        },
        "unverified_paths": [
            "billing_audit_log excluded from T1-T3 as a write-only sink",
            "Tier-4 source is recorded transcripts, not live PL/SQL",
            "scheduler job never activated or scheduled; CLI gate only",
            "HTTP blueprint routes unit-tested with fakes only; Tier 4 uses direct calls",
            "concurrent notification insert race (DuplicateKeyError would surface like ORA-00001) unit-tested only",
            "non-duplicate error propagation unit-tested only",
            "counters seeded in U6 contract (F-X-1) for the clone only",
        ],
    }


def _target_snapshot(database: Any) -> dict[str, Any]:
    return {
        "counts": {
            collection: database[collection].count_documents({})
            for collection in UNIT_COLLECTIONS
        },
        "ns_counts": {
            collection: database[collection].count_documents({"ns": NS_VALUE})
            for collection in UNIT_COLLECTIONS
        },
        "indexes": {
            collection: sorted(
                index["name"]
                for index in database[collection].list_indexes()
                if index["name"] != "_id_"
            )
            for collection in UNIT_COLLECTIONS
        },
        "golden_counts": {
            source: database[source].count_documents({}) for source in SOURCE_COLLECTIONS
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri-secret", default="MONGODB_ATLAS_URI")
    parser.add_argument("--out", default=str(OUT_DIR / "u9.recon.json"))
    args = parser.parse_args(argv)
    uri = os.environ.get(args.uri_secret)
    if not uri:
        raise SystemExit(f"secret {args.uri_secret} not set")
    result = json.loads((OUT_DIR / "result.json").read_text())
    load = json.loads((OUT_DIR / "load_report.json").read_text())
    run1 = json.loads((OUT_DIR / "load_report.run1.json").read_text())
    provenance = json.loads((OUT_DIR / "tier4_provenance.json").read_text())
    with MongoClient(uri) as client:
        report = build(
            result,
            load,
            run1,
            provenance,
            _target_snapshot(client[TARGET_DB]),
        )
    output = Path(args.out)
    output.write_text(json.dumps(report, indent=2) + "\n")
    tier_summary = ", ".join(
        f"T{number} {tier['checks_run']}/{tier['checks_run'] if tier['passed'] else '?'}"
        for number, tier in sorted({tier["tier"]: tier for tier in result["tiers"]}.items())
    )
    summary = OUT_DIR / "recon.summary.md"
    summary.write_text(
        f"# U9 recon summary\n\n"
        f"- Verdict: **{result['verdict']}**\n"
        f"- Tiers: {tier_summary}\n"
        f"- Idempotency: **{report['idempotency_rerun']['result']}**\n"
        f"- Report: `{output}`\n"
    )
    failed = [check["id"] for check in report["checks"] if check["result"] != "pass"]
    failed += ["idempotency"] if report["idempotency_rerun"]["result"] != "pass" else []
    print(f"wrote {output}; checks={len(report['checks'])} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
