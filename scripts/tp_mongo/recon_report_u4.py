#!/usr/bin/env python3
"""Assemble the repo-schema U4 recon report (docs/tech-partnerships/recon/U4.recon.json)
from the harness result.json, the load reports and the fixture manifest.

Values are copied from those artifacts or recomputed against the target; nothing here is
hand-typed. The harness result.json stays the merge authority; this file is the
`recon-report.schema.json` view validated by `make tp-validate-recon`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RECON_DIR = REPO_ROOT / ".migration/recon/U4"
MANIFEST = REPO_ROOT / "testdata/legacy/manifests/demo.json"
OUT = REPO_ROOT / "docs/tech-partnerships/recon/U4.recon.json"

UNVERIFIED = [
    ("orphaned_metadata via S3 HeadObject: the estate stores file metadata only (files bucket "
     "holds no objects for the partition), so markers use the storage-key convention "
     "(`<ns>/missing/` prefix) - same rule as testdata/legacy/validate.py; HEAD path untested"),
    ("file-service (Rust) read/write path against `files` is not converted or exercised in "
     "this unit; data-layer parity only"),
    ("DynamoDB attributes absent on an item (null_missing_equiv) - fixture items always carry "
     "folder_id, so the missing branch is exercised by canonicalization rules only"),
    "multi-partition sources - only ns='demo' exists in the fixture table",
]


def _tier(result: dict, n: int) -> dict:
    return next(t for t in result["tiers"] if t["tier"] == n)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--uri-secret", default="MONGODB_ATLAS_URI")
    p.add_argument("--target-db", default="ow_tp_mongodb_205236")
    args = p.parse_args()

    from pymongo import MongoClient

    result = json.loads((RECON_DIR / "gate/result.json").read_text())
    load = json.loads((RECON_DIR / "load_report.json").read_text())
    rerun = json.loads((RECON_DIR / "load_report.rerun.json").read_text())
    manifest = json.loads(MANIFEST.read_text())
    ns_value = load["ns"]

    coll = MongoClient(os.environ[args.uri_secret])[args.target_db]["files"]
    total = coll.count_documents({})
    tagged = coll.count_documents({"ns": ns_value})
    orphans_target = coll.count_documents({"orphaned_metadata": True})
    orphan_ids_target = sorted(d["_id"] for d in coll.find({"orphaned_metadata": True}, {"_id": 1}))
    index_names = sorted(coll.index_information())

    want_items = manifest["targets"]["dynamodb.file-metadata"]["items"]
    want_orphans = next(a["count"] for a in manifest["planted_anomalies"]
                        if a["kind"] == "orphaned_metadata")
    t1, t2, t3 = (_tier(result, n) for n in (1, 2, 3))

    def check(cid, expected, actual, truth, ok):
        return {"id": cid, "expected": expected, "actual": actual,
                "source_of_truth": truth, "result": "pass" if ok else "fail"}

    checks = [
        check("u4.counts_through_mapping",
              f"{t1['checks_run']}/{t1['checks_run']} pass (files roots {want_items})",
              f"{t1['checks_run'] - len(t1['findings'])}/{t1['checks_run']} pass; target docs {total}",
              "harness .migration/recon/U4/gate/result.json (tier1 counts_through_mapping)",
              t1["passed"] and total == want_items),
        check("u4.per_field_aggregates",
              f"{t2['checks_run']}/{t2['checks_run']} pass",
              f"{t2['checks_run'] - len(t2['findings'])}/{t2['checks_run']} pass; deferred {t2['stats'].get('deferred_to_tier3', [])}",
              "harness .migration/recon/U4/gate/result.json (tier2 per_field_aggregates)",
              t2["passed"]),
        check("u4.keyed_diffs",
              f"{want_items}/{want_items} pass, full_diff",
              f"{t3['checks_run'] - len(t3['findings'])}/{t3['checks_run']} pass; {t3['stats'].get('files')}",
              "harness .migration/recon/U4/gate/result.json (tier3 keyed_diffs)",
              t3["passed"] and t3["stats"].get("files", {}).get("mode") == "full_diff"),
        check("u4.namespace_tagging",
              f"{want_items} files documents tagged {ns_value}",
              f"{tagged}/{total} tagged {ns_value}",
              "recomputed from target (count_documents ns)", tagged == total == want_items),
        check("u4.orphaned_metadata",
              f"{want_orphans} markers (manifest planted_anomalies orphaned_metadata); items retained",
              f"load {load['orphaned_metadata']['count']} ({load['orphaned_metadata']['detection']}); target {orphans_target}",
              ".migration/recon/U4/load_report.json and recomputed from target",
              load["orphaned_metadata"]["count"] == orphans_target == want_orphans),
        check("u4.indexes",
              "owner_id_1_is_trashed_1, folder_id_1 (+_id_) per mapping v1.0",
              ", ".join(index_names),
              "recomputed from target (index_information)",
              index_names == ["_id_", "folder_id_1", "owner_id_1_is_trashed_1"]),
        check("u4.idempotency_rerun",
              "second drop/recreate load has no doubling",
              f"docs_before_drop {rerun['idempotency']['docs_before_drop']}, docs after {rerun['docs_in_collection']}",
              ".migration/recon/U4/load_report.rerun.json",
              rerun["idempotency"]["collection_existed_before"]
              and rerun["docs_in_collection"] == load["docs_in_collection"] == want_items),
    ]
    all_pass = all(c["result"] == "pass" for c in checks) and result["verdict"] == "PASS"

    report = {
        "kind": "recon-report",
        "unit": "U4",
        "namespace": ns_value,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "run_mode": "fixture",
        "harness": {
            "verdict": result["verdict"],
            "mapping_version": result["mapping_version"],
            "mapping_spec_sha256": load["mapping_spec_sha256"],
            "tolerance_version": result["tolerance_version"],
            "seed": result["seed"],
            "params": result["params"],
            "result": ".migration/recon/U4/gate/result.json",
        },
        "checks": checks,
        "values_recomputed_from_target": True,
        "idempotency_rerun": {
            "performed": True,
            "result": "pass" if checks[-1]["result"] == "pass" else "fail",
            "evidence": ".migration/recon/U4/load_report.rerun.json",
        },
        "planted_anomaly_detections": {
            "expected_set": [f"orphaned_metadata:{want_orphans}"],
            "actual_set": [f"orphaned_metadata:{orphans_target}"],
            "missing": [] if orphans_target == want_orphans else [f"orphaned_metadata:{want_orphans}"],
            "unexpected": [] if orphans_target == want_orphans else [f"orphaned_metadata:{orphans_target}"],
            "orphaned_metadata_ids_sha256_prefix": hashlib.sha256(
                "\n".join(orphan_ids_target).encode()).hexdigest()[:16],
        },
        "unverified_paths": UNVERIFIED,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n")
    print(f"{OUT.relative_to(REPO_ROOT)}: {'PASS' if all_pass else 'FAIL'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
