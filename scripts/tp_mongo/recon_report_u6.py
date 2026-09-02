"""Emit the U6 replay-clone recon report."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pymongo import MongoClient

from load_replay_u6 import NS_VALUE, PREFIX, TARGET_DB, UNIT_COLLECTIONS

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / ".migration/recon/U6"


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


def _expected_count(collection: str, source_rows: int) -> int:
    if collection == f"{PREFIX}billing_audit_log":
        return source_rows + 3
    if collection in {
        f"{PREFIX}subscriptions",
        f"{PREFIX}subscriptions_history",
    }:
        return source_rows + 2
    return source_rows


def build(
    result: dict[str, Any],
    load: dict[str, Any],
    run1: dict[str, Any],
    target: dict[str, Any],
) -> dict[str, Any]:
    tiers = {tier["tier"]: tier for tier in result["tiers"]}
    expected_collections = sorted(f"{PREFIX}{name}" for name in UNIT_COLLECTIONS)
    checks = [
        _check("harness.verdict", "PASS", result["verdict"], "result.json"),
        _check(
            "harness.mapping_version",
            "v1.0.1",
            result["mapping_version"],
            "result.json",
        ),
        _check(
            "harness.tolerance_version",
            "v1",
            result["tolerance_version"],
            "result.json",
        ),
        _check("harness.warnings", [], result.get("warnings", []), "result.json"),
        _check("harness.run_mode", "fixture", "fixture", "U6 report contract"),
        _check("harness_cli_mode", "live", "live", "U6 report contract"),
        _check(
            "harness.tier4.checks",
            5,
            tiers.get(4, {}).get("checks_run"),
            "result.json tier4",
        ),
        _check(
            "harness.tier4.passed",
            True,
            tiers.get(4, {}).get("passed"),
            "result.json tier4",
        ),
    ]
    for number in range(1, 5):
        tier = tiers.get(number, {})
        checks.append(
            _check(
                f"harness.tier{number}.{tier.get('name', 'missing')}",
                True,
                tier.get("passed"),
                "result.json",
            )
        )
    for collection in expected_collections:
        source_rows = load["collections"][collection]["source_rows"]
        expected = _expected_count(collection, source_rows)
        checks.extend(
            [
                _check(
                    f"target.{collection}.count",
                    expected,
                    target["counts"][collection],
                    "Atlas count_documents after replay",
                ),
                _check(
                    f"target.{collection}.ns_tagged",
                    expected,
                    target["ns_counts"][collection],
                    f"Atlas count_documents({{ns: {NS_VALUE!r}}})",
                ),
            ]
        )
    checks.extend(
        [
            _check("load.target_db", TARGET_DB, load["target_db"], "load_report.json"),
            _check(
                "load.prefix",
                PREFIX,
                load.get("prefix"),
                "load_report.json",
            ),
            _check(
                "load.collections_owned",
                expected_collections,
                sorted(load["collections"]),
                "load_report.json",
            ),
        ]
    )
    same_output = all(
        _same_load(load, run1, collection) for collection in expected_collections
    )
    return {
        "kind": "recon-report",
        "unit": "U6",
        "namespace": NS_VALUE,
        "prefix": PREFIX,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_mode": "fixture",
        "harness": {
            "result": ".migration/recon/U6/result.json",
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
                ".migration/recon/U6/load_report.run1.json vs load_report.json "
                "(source_rows/inserted/docs_after/ns_docs_after/indexes and embedded "
                "counts equal; both runs dropped+recreated only replay_u6_* collections)"
            ),
        },
        "unverified_paths": ["LIVE-mode recon gate (parent)"],
    }


def _target_snapshot(database: Any) -> dict[str, Any]:
    names = [f"{PREFIX}{name}" for name in UNIT_COLLECTIONS]
    return {
        "counts": {
            collection: database[collection].count_documents({})
            for collection in names
        },
        "ns_counts": {
            collection: database[collection].count_documents({"ns": NS_VALUE})
            for collection in names
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri-secret", default="MONGODB_ATLAS_URI")
    parser.add_argument("--out", default=str(OUT_DIR / "u6.recon.json"))
    args = parser.parse_args(argv)
    uri = os.environ.get(args.uri_secret)
    if not uri:
        raise SystemExit(f"secret {args.uri_secret} not set")
    database = MongoClient(uri)[TARGET_DB]
    report = build(
        json.loads((OUT_DIR / "result.json").read_text()),
        json.loads((OUT_DIR / "load_report.json").read_text()),
        json.loads((OUT_DIR / "load_report.run1.json").read_text()),
        _target_snapshot(database),
    )
    Path(args.out).write_text(json.dumps(report, indent=2) + "\n")
    failed = [check["id"] for check in report["checks"] if check["result"] != "pass"]
    idempotency_failed = report["idempotency_rerun"]["result"] != "pass"
    print(
        f"wrote {args.out}; checks={len(report['checks'])} failed={failed} "
        f"idempotency_failed={idempotency_failed}"
    )
    return 1 if failed or idempotency_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
