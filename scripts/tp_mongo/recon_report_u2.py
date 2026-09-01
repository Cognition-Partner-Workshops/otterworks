"""Emit the repo-schema recon report for U2."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from load_u2 import NS_VALUE, QUARANTINE_DB, TARGET_DB
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / ".migration/recon/U2"
EXPECTED_INDEXES = [
    "_id_",
    "batch_no_1_status_cd_1",
    "cust_id_1",
    "lines.line_id_1",
]


def _check(cid: str, expected: Any, actual: Any, truth: str) -> dict[str, Any]:
    return {
        "id": cid,
        "expected": expected,
        "actual": actual,
        "source_of_truth": truth,
        "result": "pass" if expected == actual else "fail",
    }


def build(
    result: dict[str, Any],
    load: dict[str, Any],
    run1: dict[str, Any],
    target: dict[str, Any],
    mapping_version: str,
) -> dict[str, Any]:
    tiers = {item["tier"]: item for item in result["tiers"]}
    tier3_stats = tiers.get(3, {}).get("stats", {})
    checks = [
        _check("harness.verdict", "PASS", result.get("verdict"), "result.json"),
        _check(
            "harness.mapping_version",
            mapping_version,
            result.get("mapping_version"),
            "result.json",
        ),
        _check(
            "harness.tolerance_version",
            "v1",
            result.get("tolerance_version"),
            "result.json",
        ),
    ]
    for number, tier in sorted(tiers.items()):
        checks.append(
            _check(
                f"harness.tier{number}.{tier['name']}",
                True,
                tier.get("passed"),
                "result.json",
            )
        )
    checks.extend(
        [
            _check("harness.tier3.no_embeds_ungraded", False, "embeds_ungraded" in tier3_stats, "result.json"),
            _check("target.invoices.count", 18750, target["invoices"], "Atlas count_documents"),
            _check("target.invoices.embedded_lines", 149963, target["embedded_lines"], "Atlas $unwind count"),
            _check(
                "target.quarantine.invoice_feed_orphan_lines.count",
                37,
                target["quarantine"],
                "Atlas count_documents",
            ),
            _check(
                "target.invoices.ns_mismatch",
                0,
                target["invoices_ns_mismatch"],
                "Atlas count_documents({ns: {$ne: ...}})",
            ),
            _check(
                "target.quarantine.ns_mismatch",
                0,
                target["quarantine_ns_mismatch"],
                "Atlas count_documents({ns: {$ne: ...}})",
            ),
            _check(
                "target.indexes",
                EXPECTED_INDEXES,
                sorted(target["indexes"]),
                "Atlas list_indexes",
            ),
            _check(
                "target.embedded_plus_quarantined",
                150000,
                target["embedded_lines"] + target["quarantine"],
                "Atlas counts",
            ),
            _check(
                "target.quarantine_rate",
                37 / 18750,
                target["quarantine"] / target["invoices"],
                "Atlas counts",
            ),
            _check(
                "load.source_counts.invoice_header",
                18750,
                load["source_counts"]["invoice_header"],
                "load_report.json",
            ),
            _check(
                "load.source_counts.invoice_line",
                150000,
                load["source_counts"]["invoice_line"],
                "load_report.json",
            ),
            _check(
                "load.embedded_lines",
                149963,
                load["embedded_lines"],
                "load_report.json",
            ),
            _check(
                "load.quarantined_lines",
                37,
                load["quarantined_lines"],
                "load_report.json",
            ),
        ]
    )
    same_output = (
        load["collections"] == run1["collections"]
        and load["source_counts"] == run1["source_counts"]
        and load["embedded_lines"] == run1["embedded_lines"]
        and load["quarantined_lines"] == run1["quarantined_lines"]
        and load["quarantined_line_ids"] == run1["quarantined_line_ids"]
        and load["indexes"] == run1["indexes"]
    )
    report = {
        "kind": "recon-report",
        "unit": "U2",
        "namespace": NS_VALUE,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_mode": "fixture",
        "harness": {
            "result": ".migration/recon/U2/result.json",
            "verdict": result.get("verdict"),
            "seed": result.get("seed"),
            "params": result.get("params"),
        },
        "checks": checks,
        "values_recomputed_from_target": True,
        "idempotency_rerun": {
            "performed": True,
            "result": "pass" if same_output else "fail",
            "evidence": ".migration/recon/U2/load_report_run1.json vs load_report.json",
        },
        "unverified_paths": [
            "LIVE-mode recon gate against the parent's uncontended window (parent-run responsibility; this report is run_mode=fixture)",
            "Tier 4 app-level parity beyond rpt114_parity_u2.py (report-path evidence is separate)",
            "Atlas source adapter key-strata sampling path (harness-owned)",
        ],
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri-secret", default="MONGODB_ATLAS_URI")
    parser.add_argument("--out", default=str(OUT_DIR / "u2.recon.json"))
    args = parser.parse_args(argv)
    uri = os.environ.get(args.uri_secret)
    if not uri:
        raise SystemExit(f"secret {args.uri_secret} not set")

    mapping = json.loads((ROOT / ".migration/03_mapping_spec.json").read_text())
    client = MongoClient(uri)
    try:
        db, quarantine_db = client[TARGET_DB], client[QUARANTINE_DB]
        embedded = next(
            db["invoices"].aggregate(
                [{"$unwind": "$lines"}, {"$count": "n"}]
            ),
            {"n": 0},
        )["n"]
        target = {
            "invoices": db["invoices"].count_documents({}),
            "embedded_lines": embedded,
            "quarantine": quarantine_db[
                "invoice_feed_orphan_lines"
            ].count_documents({}),
            "invoices_ns_mismatch": db["invoices"].count_documents(
                {"ns": {"$ne": NS_VALUE}}
            ),
            "quarantine_ns_mismatch": quarantine_db[
                "invoice_feed_orphan_lines"
            ].count_documents({"ns": {"$ne": NS_VALUE}}),
            "indexes": [
                item["name"] for item in db["invoices"].list_indexes()
            ],
        }
    finally:
        client.close()

    report = build(
        json.loads((OUT_DIR / "result.json").read_text()),
        json.loads((OUT_DIR / "load_report.json").read_text()),
        json.loads((OUT_DIR / "load_report_run1.json").read_text()),
        target,
        mapping["version"],
    )
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")

    lines = ["# Recon summary: `U2` - **PASS**", ""]
    failed = [item["id"] for item in report["checks"] if item["result"] != "pass"]
    if report["idempotency_rerun"]["result"] != "pass":
        failed.append("idempotency_rerun")
    verdict = "PASS" if not failed else "FAIL"
    lines[0] = f"# Recon summary: `U2` - **{verdict}**"
    lines.extend(
        [
            "",
            "- Mode: fixture",
            f"- Mapping `{mapping['version']}` / tolerances `v1` / seed `{report['harness']['seed']}` / params `{report['harness']['params']}`",
            f"- Generated: {report['generated_at']}",
            "",
            "| Check | Result |",
            "|---|---|",
        ]
    )
    lines.extend(
        f"| {item['id']} | {item['result'].upper()} |"
        for item in report["checks"]
    )
    lines.extend(["", "Full evidence: result.json, load_report.json."])
    (OUT_DIR / "recon.summary.md").write_text("\n".join(lines) + "\n")
    print(f"wrote {args.out}; checks={len(report['checks'])} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
