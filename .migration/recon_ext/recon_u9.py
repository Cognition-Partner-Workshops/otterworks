"""Run U9 Oracle-to-Mongo reconciliation and dunning replay."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "legacy-billing" / "app"))
sys.path.insert(0, str(ROOT / "scripts" / "tp_mongo"))
sys.path.insert(0, str(ROOT / "procs" / "harness"))

from load_replay_u9 import PREFIX, SOURCE_COLLECTIONS, TARGET_DB, reset_collections
from oracle_record import oracle_source_sha
from ow_billing import Store, dunning
from recon.adapters import MongoTargetAdapter, OracleSourceAdapter
from recon.config import load_canon_rules, load_mapping_spec, load_tolerances
from recon.engine import MODES, run_recon

GRADED_SOURCES = (
    "billing_invoices",
    "tenants",
    "subscriptions",
    "dunning_attempts",
    "notifications",
)
SCENARIOS = ROOT / "procs" / "scenarios" / "dunning"
TRANSCRIPTS = ROOT / "procs" / "oracle" / "transcripts" / "dunning"
MUTABLE = ("tenants", "subscriptions", "dunning_attempts", "notifications", "billing_audit_log", "counters")
TIER4_ROWS: list[dict[str, Any]] = []


def unit_mapping(mapping: Path, out: Path) -> Path:
    data = json.loads(mapping.read_text())
    kept = [
        {**collection, "collection": f"{PREFIX}{collection['collection']}", "unit": "U9"}
        for collection in data.get("collections", [])
        if collection.get("collection") in GRADED_SOURCES
    ]
    if len(kept) != len(GRADED_SOURCES):
        raise SystemExit(f"mapping {mapping} lacks one of {GRADED_SOURCES}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({**data, "collections": kept}, indent=2) + "\n")
    return out


def _date(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.date().isoformat()
    return value.isoformat() if hasattr(value, "isoformat") else value


def _status(value: int | None) -> str:
    return dunning.DUNNING_STATUS.get(value, "UNKNOWN")


def _subscription_status(value: int | None) -> str:
    return dunning.TENANT_STATUS.get(value, {30: "cancelled"}.get(value, "UNKNOWN"))


def _operations() -> list[dict[str, Any]]:
    operations = []
    for path in sorted(SCENARIOS.glob("*.yaml")):
        scenario = yaml.safe_load(path.read_text())
        transcript = json.loads((TRANSCRIPTS / f"{scenario['id']}.json").read_text())
        operations.append(
            {
                "name": scenario["id"],
                "collection": f"{PREFIX}{scenario['entrypoint'].split('.')[-1]}",
                "scenario": scenario,
                "transcript": transcript,
                "rules": [],
            }
        )
    return operations


def check_transcript_provenance(ops: list[dict[str, Any]]) -> dict[str, Any]:
    current = oracle_source_sha()
    recorded = {op["transcript"]["oracle_source_sha"] for op in ops}
    return {
        "oracle_source_sha": current,
        "transcripts_match": recorded == {current},
        "scenarios": [op["name"] for op in ops],
    }


def run_source(op: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [dict(op["transcript"]["business_fields"])]
    for probe_id, probe_rows in op["transcript"].get("probes", {}).items():
        rows.extend({"probe": probe_id, **row} for row in probe_rows)
    return rows


def _schedule_rows(store: Store) -> list[dict[str, Any]]:
    return [
        {
            "probe": "schedule_rows",
            "invoice_id": row["invoice_id"],
            "attempt_no": int(row["attempt_no"]),
            "scheduled_for": _date(row["scheduled_for"]),
            "status": _status(row.get("status_cd")),
        }
        for row in store.coll("dunning_attempts").find().sort(
            [("invoice_id", 1), ("attempt_no", 1)]
        )
    ]


def _notification_rows(store: Store) -> list[dict[str, Any]]:
    return [
        {
            "probe": "suspension_notifications",
            "id": row.get("id", row["_id"]),
            "tenant_id": row["tenant_id"],
            "kind": "suspension" if row.get("kind_cd") == 3 else "UNKNOWN",
            "sent_at": f"{row['sent_at']:%Y-%m-%dT%H:%M:%SZ}",
        }
        for row in store.coll("notifications").find({"kind_cd": 3}).sort(
            [("tenant_id", 1), ("sent_at", 1)]
        )
    ]


def run_target(store: Store, op: dict[str, Any], database: Any) -> list[dict[str, Any]]:
    reset_collections(database, MUTABLE)
    scenario = op["scenario"]
    as_of = date.fromisoformat(str(next(i["value"] for i in scenario["inputs"] if i["name"] == "as_of")))
    entrypoint = scenario["entrypoint"]
    if entrypoint == "billing.fn_overdue_accounts":
        result = dunning.fn_overdue_accounts(store, as_of)
        target_rows = [
            {
                "tenant_ids": [row["tenant_id"] for row in result],
                "days_overdue": [int(row["days_overdue"]) for row in result],
            }
        ]
    elif entrypoint == "billing.sp_schedule_dunning":
        dunning.sp_schedule_dunning(store, as_of)
        invoice_id = (
            "60000000-0000-0000-0000-000000000001"
            if op["name"] == "DUNNING-002"
            else "60000000-0000-0000-0000-000000000002"
        )
        latest = store.coll("dunning_attempts").find_one(
            {"invoice_id": invoice_id}, sort=[("attempt_no", -1)]
        )
        target_rows = [
            {
                "scheduled_for": _date(latest["scheduled_for"]),
                **({"status": _status(latest.get("status_cd"))}
                   if op["name"] == "DUNNING-002" else
                   {"attempt_no": int(latest["attempt_no"])}),
            }
        ]
        target_rows.extend(_schedule_rows(store))
    else:
        dunning.sp_suspend_overdue(store, as_of)
        if op["name"] == "DUNNING-005":
            dunning.sp_suspend_overdue(store, as_of)
            target_rows = [
                {
                    "notification_kinds": [
                        "suspension"
                        for row in store.coll("notifications").find(
                            {"tenant_id": "00000000-0000-0000-0000-000000000005", "kind_cd": 3}
                        ).sort("sent_at", 1)
                    ]
                }
            ]
        else:
            subscription = store.coll("subscriptions").find_one(
                {"tenant_id": "00000000-0000-0000-0000-000000000005"}
            )
            target_rows = [
                {
                    "status": _subscription_status(subscription.get("status_cd")),
                    "suspended_on": _date(subscription.get("suspended_on")),
                }
            ]
        target_rows.extend(_notification_rows(store))
    return target_rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="recon_u9")
    parser.add_argument("--unit", default="U9")
    parser.add_argument("--family", default="oracle", choices=("oracle",))
    parser.add_argument("--mapping", required=True, type=Path)
    parser.add_argument("--tolerances", required=True, type=Path)
    parser.add_argument("--canonicalization", required=True, type=Path)
    parser.add_argument("--mode", required=True, choices=MODES)
    parser.add_argument("--source-dsn-secret", required=True)
    parser.add_argument("--target-uri-secret", required=True)
    parser.add_argument("--target-db", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--param", action="append", default=[])
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    params = {}
    for item in args.param:
        name, sep, value = item.partition("=")
        if not sep or not name:
            raise SystemExit(f"--param must be NAME=VALUE, got '{item}'")
        params[name] = value
    mapping = unit_mapping(args.mapping, args.out / "mapping" / "u9.json")
    spec = load_mapping_spec(mapping, params)
    tolerances = load_tolerances(args.tolerances)
    canonicalization = load_canon_rules(args.canonicalization)
    ops = _operations()
    provenance = check_transcript_provenance(ops)
    if not provenance["transcripts_match"]:
        raise SystemExit(f"dunning transcripts were recorded against another source: {provenance}")
    uri = os.environ.get(args.target_uri_secret)
    if not uri:
        raise SystemExit(f"secret {args.target_uri_secret} not set")
    client = MongoClient(uri)
    database = client[args.target_db]
    store = Store(client, args.target_db, PREFIX)

    def run_target_fn(op: dict[str, Any]) -> list[dict[str, Any]]:
        target_rows = run_target(store, op, database)
        TIER4_ROWS.append(
            {"name": op["name"], "source": run_source(op), "target": target_rows}
        )
        return target_rows

    try:
        source = OracleSourceAdapter(args.source_dsn_secret)
        target = MongoTargetAdapter(args.target_uri_secret, args.target_db)
        result = run_recon(
            args.unit,
            args.mode,
            spec,
            tolerances,
            canonicalization,
            source,
            target,
            ops=ops,
            run_source=run_source,
            run_target=run_target_fn,
            out_dir=args.out,
            seed=args.seed,
            params=params,
        )
    finally:
        reset_collections(database, MUTABLE)
        client.close()
    (args.out / "tier4_replay.json").write_text(json.dumps(TIER4_ROWS, indent=2) + "\n")
    (args.out / "tier4_provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(
        f"recon {result['verdict']}: unit={args.unit} mode={args.mode} family=oracle "
        f"mapping={spec.version} tolerances={tolerances.version} -> {args.out}/result.json"
    )
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
