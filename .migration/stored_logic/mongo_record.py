"""Records transcripts of the converted estate, for comparison with the Oracle recordings.

Same declarative scenario set as `procs/harness/oracle_record.py` (`procs/scenarios/`), same
transcript shape, same normalization -- so `mongo_parity.py` can compare the two sets field
for field. What changes is the driver: the entrypoints are the converted routines in
`billing_logic.py` running against MongoDB, and the Postgres-dialect capture/probe SQL is
translated into the Mongo reads in SCENARIO_READS below, the way `procs/oracle/oracle_map.yaml`
translates it into the Oracle dialect.

The baseline is the migrated target itself. Before each scenario the static-tenant documents
are copied out of the migrated collections into replay collections (`sl_replay_*`, registered
in `.migration/04_progress.md`), and the scenario runs against those. The migrated
collections are never written to, and a scenario cannot see another scenario's writes.

Usage:
    mongo_record.py --target-db ow_tp_mongodb_orc1 [--module dunning] [--scenario PLANS-004]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import sys
from decimal import ROUND_HALF_UP, Decimal

import billing_logic as bl
import yaml
from mongo_store import MongoStore
from pymongo import MongoClient

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCENARIOS = ROOT / "procs" / "scenarios"
OUT = pathlib.Path(__file__).resolve().parent / "transcripts"
REPLAY_PREFIX = "sl_replay_"
STATIC_TENANTS = [f"00000000-0000-0000-0000-00000000000{n}" for n in range(1, 10)]
REPLAY_COLLECTIONS = (
    "tenants",
    "plans",
    "subscriptions",
    "usage_events",
    "rating_periods",
    "credit_notes",
    "subscription_invoices",
    "dunning_attempts",
    "notifications",
    "billing_audit_log",
)


def normalized(value, kind=None):
    """Byte-identical to the Oracle recorder's normalization; the two transcript sets are only
    comparable if the values are shaped the same way before they are written."""
    if value is None:
        return None
    if kind == "decimal":
        return str(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    if kind == "integer":
        current = Decimal(str(value))
        return str(current) if current != current.to_integral_value() else int(current)
    if kind == "date":
        return _date(value).isoformat()
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else str(value)
    if isinstance(value, dt.datetime):
        if value.tzinfo is not None:
            return value.astimezone(dt.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
        return value.isoformat(timespec="seconds")
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [normalized(item) for item in value]
    if isinstance(value, dict):
        return {str(k): normalized(v) for k, v in sorted(value.items())}
    return value


def _date(value):
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value)[:10])


def _ymd(value):
    return None if value is None else _date(value).isoformat()


def _dec(value):
    return None if value is None else Decimal(str(value))


def typed(value, kind):
    if kind == "date":
        return dt.date.fromisoformat(str(value))
    if kind == "integer":
        return int(value)
    if kind == "decimal":
        return Decimal(str(value))
    return value


# --- entrypoints ----------------------------------------------------------------------

ENTRYPOINTS = {
    "billing.fn_list_plans": ("pkg_plans.fn_list_plans", bl.list_plans),
    "billing.fn_entitlement": ("pkg_plans.fn_entitlement", bl.entitlement),
    "billing.sp_change_plan": ("pkg_plans.sp_change_plan", bl.change_plan),
    "billing.fn_usage_rating": ("pkg_rating.fn_usage_rating", bl.usage_rating),
    "billing.fn_usage_summary": ("pkg_rating.fn_usage_summary", bl.usage_summary),
    "billing.sp_finalize_rating": ("pkg_rating.sp_finalize_rating", bl.finalize_rating),
    "billing.fn_invoice_preview": ("pkg_invoicing.fn_invoice_preview", bl.invoice_preview),
    "billing.fn_invoice_lines": ("pkg_invoicing.fn_invoice_lines", bl.invoice_lines),
    "billing.sp_issue_invoice": ("pkg_invoicing.sp_issue_invoice", bl.issue_invoice),
    "billing.fn_overdue_accounts": ("pkg_dunning.fn_overdue_accounts", bl.overdue_accounts),
    "billing.sp_schedule_dunning": ("pkg_dunning.sp_schedule_dunning", bl.schedule_dunning),
    "billing.sp_suspend_overdue": ("pkg_dunning.sp_suspend_overdue", bl.suspend_overdue),
}


# --- capture and probe reads ----------------------------------------------------------


def subscription_rows(store, tenant_id):
    subs = sorted(store.subscriptions(tenant_id), key=lambda s: _date(s["starts_on"]))
    return [
        {
            "plan_id": s["plan_id"],
            "starts_on": _ymd(s["starts_on"]),
            "ends_on": _ymd(s.get("ends_on")),
            "status": store.code_desc("SUB_STATUS", s["status_cd"]),
        }
        for s in subs
    ]


def rating_result_rows(store, tenant_id, period_start):
    return [
        {
            "used_units": r["used_units"],
            "quota_units": r["quota_units"],
            "rollover_units": r["rollover_units"],
            "billable_units": r["billable_units"],
            "overage_amount": normalized(_dec(r["overage_amount"]), "decimal"),
        }
        for period in store.rating_periods(tenant_id)
        if _date(period["period_start"]) == period_start
        for r in period.get("results", [])
    ]


def credit_note_rows(store, tenant_id):
    notes = sorted(store.credit_notes(tenant_id), key=lambda c: (_date(c["issued_on"]), c["_id"]))
    return [
        {
            "id": c["_id"],
            "issued_on": _ymd(c["issued_on"]),
            "remaining_amount": normalized(_dec(c["remaining_amount"]), "decimal"),
        }
        for c in notes
    ]


def invoice_state_rows(store, tenant_id):
    period_id = bl.md5_uuid(f"{tenant_id}2026-02-01")
    return [
        {
            "status": store.code_desc("INV_STATUS", i["status_cd"]),
            "subtotal": normalized(_dec(i["subtotal"]), "decimal"),
            "tax": normalized(_dec(i["tax"]), "decimal"),
            "total": normalized(_dec(i["total"]), "decimal"),
        }
        for i in store.collection("subscription_invoices").find({"period_id": period_id})
    ]


def schedule_rows(store):
    attempts = sorted(
        store.collection("dunning_attempts").find(),
        key=lambda a: (a["invoice_id"], a["attempt_no"]),
    )
    return [
        {
            "invoice_id": a["invoice_id"],
            "attempt_no": int(a["attempt_no"]),
            "scheduled_for": _ymd(a["scheduled_for"]),
            "status": store.code_desc("DUN_STATUS", a["status_cd"]),
        }
        for a in attempts
    ]


def latest_attempt_rows(store, invoice_id):
    attempts = sorted(store.dunning_attempts(invoice_id), key=lambda a: a["attempt_no"])
    return [
        {
            "attempt_no": int(a["attempt_no"]),
            "scheduled_for": _ymd(a["scheduled_for"]),
            "status": store.code_desc("DUN_STATUS", a["status_cd"]),
        }
        for a in attempts[-1:]
    ]


def suspension_notification_rows(store):
    notifications = sorted(
        (n for n in store.notifications() if int(n["kind_cd"]) == bl.NOTIFY_SUSPENSION),
        key=lambda n: (n["tenant_id"], n["sent_at"]),
    )
    return [
        {
            "id": n["_id"],
            "tenant_id": n["tenant_id"],
            "kind": store.code_desc("NOTIF_KIND", n["kind_cd"]),
            "sent_at": f"{_ymd(n['sent_at'])}T00:00:00Z",
        }
        for n in notifications
    ]


def suspension_state_rows(store, tenant_id):
    return [
        {
            "status": store.code_desc("SUB_STATUS", s["status_cd"]),
            "suspended_on": _ymd(s.get("suspended_on")),
        }
        for s in store.subscriptions(tenant_id)
    ]


TENANT_5 = "00000000-0000-0000-0000-000000000005"
INVOICE_1 = "60000000-0000-0000-0000-000000000001"
INVOICE_2 = "60000000-0000-0000-0000-000000000002"

SCENARIO_READS = {
    "PLANS-004": {
        "capture": lambda s: subscription_rows(s, STATIC_TENANTS[0]),
        "probes": {"subscription_rows": lambda s: subscription_rows(s, STATIC_TENANTS[0])},
    },
    "PLANS-005": {
        "capture": lambda s: subscription_rows(s, STATIC_TENANTS[3]),
        "probes": {"subscription_rows": lambda s: subscription_rows(s, STATIC_TENANTS[3])},
    },
    "RATING-008": {
        "capture": lambda s: rating_result_rows(s, STATIC_TENANTS[0], dt.date(2026, 2, 1)),
        "probes": {
            "rating_result": lambda s: rating_result_rows(s, STATIC_TENANTS[0], dt.date(2026, 2, 1))
        },
    },
    "INVOICE-003": {
        "capture": lambda s: credit_note_rows(s, STATIC_TENANTS[8]),
        "probes": {"invoice_state": lambda s: invoice_state_rows(s, STATIC_TENANTS[8])},
    },
    "INVOICE-004": {
        "capture": lambda s: credit_note_rows(s, STATIC_TENANTS[3]),
        "probes": {"invoice_state": lambda s: invoice_state_rows(s, STATIC_TENANTS[3])},
    },
    "INVOICE-005": {
        "capture": lambda s: invoice_state_rows(s, STATIC_TENANTS[5]),
        "probes": {"invoice_state": lambda s: invoice_state_rows(s, STATIC_TENANTS[5])},
    },
    "DUNNING-002": {
        "capture": lambda s: latest_attempt_rows(s, INVOICE_1),
        "probes": {"schedule_rows": schedule_rows},
    },
    "DUNNING-003": {
        "capture": lambda s: latest_attempt_rows(s, INVOICE_2),
        "probes": {"schedule_rows": schedule_rows},
    },
    "DUNNING-004": {
        "capture": lambda s: suspension_state_rows(s, TENANT_5),
        "probes": {"suspension_notifications": suspension_notification_rows},
    },
    "DUNNING-005": {
        "capture": lambda s: [
            {"kind": s.code_desc("NOTIF_KIND", n["kind_cd"])}
            for n in sorted(
                (
                    n
                    for n in s.notifications(TENANT_5)
                    if int(n["kind_cd"]) == bl.NOTIFY_SUSPENSION
                ),
                key=lambda n: n["sent_at"],
            )
        ],
        "probes": {"suspension_notifications": suspension_notification_rows},
    },
}

AFTER_CALLS = {"DUNNING-005": lambda store: bl.suspend_overdue(store, dt.date(2026, 2, 28))}


# --- baseline -------------------------------------------------------------------------


def reset_baseline(db):
    """Rebuild the replay copies from the migrated collections. Only the static-seed tenants
    the scenario set exercises are copied, mirroring the Oracle recorder's reset scope."""
    for name in REPLAY_COLLECTIONS:
        target = db[f"{REPLAY_PREFIX}{name}"]
        target.drop()
        if name == "plans":
            query = {}
        elif name == "tenants":
            query = {"_id": {"$in": STATIC_TENANTS}}
        else:
            query = {"tenant_id": {"$in": STATIC_TENANTS}}
        docs = list(db[name].find(query))
        if docs:
            target.insert_many(docs)


def drop_replay(db):
    for name in REPLAY_COLLECTIONS:
        db[f"{REPLAY_PREFIX}{name}"].drop()


# --- recording ------------------------------------------------------------------------


def capture_fields(rows, specs):
    captured = {}
    for spec in specs:
        source = str(spec["from"]) if "from" in spec else None
        values = [row.get(source) for row in rows] if source else []
        if spec.get("collect"):
            captured[spec["name"]] = [normalized(v, spec.get("type")) for v in values]
        elif spec.get("collect_rows"):
            captured[spec["name"]] = [
                {key: normalized(row.get(key), kind) for key, kind in spec["columns"].items()}
                for row in rows
            ]
        else:
            captured[spec["name"]] = normalized(values[0] if values else None, spec.get("type"))
    return captured


def run_scenario(db, scenario):
    reset_baseline(db)
    store = MongoStore(db, prefix=REPLAY_PREFIX)
    store.ensure_indexes()

    inputs = scenario.get("inputs", [])
    args = [typed(item.get("value"), item["type"]) for item in inputs]
    oracle_entrypoint, routine = ENTRYPOINTS[scenario["entrypoint"]]
    result = routine(store, *args)
    rows = result if scenario["kind"] == "function" else []

    if scenario.get("after_sql"):
        after = AFTER_CALLS.get(scenario["id"])
        if after is None:
            sys.exit(f"{scenario['id']}: after_sql has no converted after_call")
        after(store)

    reads = SCENARIO_READS.get(scenario["id"], {})
    if scenario.get("capture_query"):
        if "capture" not in reads:
            sys.exit(f"{scenario['id']}: capture_query has no converted read")
        rows = reads["capture"](store)

    probes = {}
    for probe in scenario.get("probes", []):
        read = reads.get("probes", {}).get(probe["id"])
        if read is None:
            sys.exit(f"{scenario['id']}: probe {probe['id']} has no converted read")
        probe_rows = [{k: normalized(v) for k, v in row.items()} for row in read(store)]
        probes[probe["id"]] = (
            probe_rows
            if probe.get("collect_rows")
            else (probe_rows[0][next(iter(probe_rows[0]))] if probe_rows else None)
        )

    return {
        "scenario": scenario["id"],
        "module": scenario["module"],
        "entrypoint": scenario["entrypoint"],
        "oracle_entrypoint": oracle_entrypoint,
        "inputs": {
            str(item["name"]): normalized(item.get("value"), item.get("type")) for item in inputs
        },
        "business_fields": capture_fields(rows, scenario.get("fields", [])),
        "probes": probes,
    }


def load_scenarios(module, scenario_id):
    paths = sorted(SCENARIOS.glob(f"{module}/*.yaml" if module else "*/*.yaml"))
    scenarios = [yaml.safe_load(path.read_text()) for path in paths]
    if scenario_id:
        scenarios = [s for s in scenarios if s["id"] == scenario_id]
    if not scenarios:
        sys.exit("no scenario selected")
    return scenarios


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-db", required=True)
    ap.add_argument("--target-uri-secret", default="MONGODB_ATLAS_URI")
    ap.add_argument("--module")
    ap.add_argument("--scenario")
    ap.add_argument("--out", type=pathlib.Path, default=OUT)
    ap.add_argument("--report-out", type=pathlib.Path,
                    help="machine-readable record of this replay; two of them, compared, are "
                         "what proves the conversion is idempotent")
    args = ap.parse_args()

    conventions = (ROOT / ".migration" / "01_conventions.md").read_text()
    if f"`{args.target_db}`" not in conventions:
        sys.exit(f"{args.target_db} is not the designated migration database")
    uri = os.environ.get(args.target_uri_secret)
    if not uri:
        sys.exit(f"{args.target_uri_secret} is not set in the environment")

    db = MongoClient(uri)[args.target_db]
    records = [run_scenario(db, scenario) for scenario in load_scenarios(args.module, args.scenario)]
    drop_replay(db)

    args.out.mkdir(parents=True, exist_ok=True)
    for record in records:
        destination = args.out / record["module"] / f"{record['scenario']}.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(f"recorded {len(records)} converted transcript(s) -> {args.out.relative_to(ROOT)}")

    if args.report_out:
        # A per-scenario digest, not one over the whole set: a replay that drifts names the
        # scenario that drifted instead of just disagreeing.
        report = {
            "unit": "stored_logic",
            "target_db": args.target_db,
            "selection": {"module": args.module, "scenario": args.scenario},
            "completed_at": dt.datetime.now(dt.UTC).isoformat(),
            "scenarios": len(records),
            "digests": {
                record["scenario"]: hashlib.sha256(
                    json.dumps(record, sort_keys=True).encode()
                ).hexdigest()
                for record in records
            },
        }
        args.report_out.parent.mkdir(parents=True, exist_ok=True)
        args.report_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
