#!/usr/bin/env python3
"""Batch w3-b02 parity replay: migrated PKG_RATING/PKG_INVOICING/PKG_DUNNING
service code vs the recorded Oracle transcripts
(procs/oracle/transcripts/{rating,invoicing,dunning}/).

For each scenario the script resets the migrated baseline
(fixture_load.load_baseline), runs the equivalent rating_service /
invoicing_service / dunning_service operation against
ow_billing_migration, shapes the result exactly like the recorded
transcript (business_fields + probes), and compares verbatim. DUNNING-005
runs sp_suspend_overdue twice, matching the recorded after_sql.

Write targets: spec collections used (dropped+recreated by the baseline
loader) plus declared scratch `ow_billing_migration.parity_w3_b02`.

    env -u MONGODB_ATLAS_URI OW_BILLING_FIXTURE_DSN='{...}' \
        MONGO_LOCAL_URI=mongodb://localhost:27017 \
        python3 services/legacy-billing/migration/mongo/parity_w3_b02.py \
            --source-dsn-secret OW_BILLING_FIXTURE_DSN \
            --target-uri-secret MONGO_LOCAL_URI \
            --target-db ow_billing_migration
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from pathlib import Path

import dunning_service
import fixture_load
import invoicing_service
import ow_util
import rating_service

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[3]
ORACLE_TRANSCRIPTS = REPO_ROOT / "procs" / "oracle" / "transcripts"
RECON_ROOT = HERE / "recon"
SCRATCH = "parity_w3_b02"
ALLOWED_TARGETS_FILE = REPO_ROOT / ".migration" / "allowed_targets.json"

ENTRY_TO_SERVICE = {
    "billing.fn_usage_rating": ("rating_service", "usage_rating"),
    "billing.fn_usage_summary": ("rating_service", "usage_summary"),
    "billing.sp_finalize_rating": ("rating_service", "finalize_rating"),
    "billing.fn_invoice_preview": ("invoicing_service", "invoice_preview"),
    "billing.fn_invoice_lines": ("invoicing_service", "invoice_lines"),
    "billing.sp_issue_invoice": ("invoicing_service", "issue_invoice"),
    "billing.fn_overdue_accounts": ("dunning_service", "overdue_accounts"),
    "billing.sp_schedule_dunning": ("dunning_service", "schedule_dunning"),
    "billing.sp_suspend_overdue": ("dunning_service", "suspend_overdue"),
}


def _fail(msg: str) -> int:
    print(f"error: {msg}", file=sys.stderr)
    return 2


def _secret_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(_fail(f"secret env var {name} is not set"))
    return value


def _iso(v) -> str | None:
    if v is None:
        return None
    d = v.date() if isinstance(v, _dt.datetime) else v
    return d.isoformat()


def _iso_dt(v) -> str | None:
    if v is None:
        return None
    return v.isoformat() + "Z" if isinstance(v, _dt.datetime) and v.tzinfo is None \
        else str(v)


def _rating_result_row(db, tenant_id: str, period_start: _dt.date):
    period_id = ow_util.md5_uuid(tenant_id + period_start.isoformat())
    row = db["ratingResults"].find_one({"periodId": period_id})
    if row is None:
        return []
    return [
        {
            "used_units": row.get("usedUnits"),
            "quota_units": row.get("quotaUnits"),
            "rollover_units": row.get("rolloverUnits"),
            "billable_units": row.get("billableUnits"),
            "overage_amount": ow_util.dec2(row.get("overageAmount")),
        }
    ]


def _invoice_state(db, tenant_id: str, period_start: _dt.date):
    period_id = ow_util.md5_uuid(tenant_id + period_start.isoformat())
    inv = db["invoices"].find_one({"periodId": period_id})
    if inv is None:
        return []
    return [
        {
            "status": ow_util.code_desc(db, "INV_STATUS", inv.get("statusCd")),
            "subtotal": ow_util.dec2(inv.get("subtotal")),
            "tax": ow_util.dec2(inv.get("tax")),
            "total": ow_util.dec2(inv.get("total")),
        }
    ]


def _schedule_rows(db):
    rows = []
    for a in db["dunningAttempts"].find().sort([("invoiceId", 1), ("attemptNo", 1)]):
        rows.append(
            {
                "invoice_id": a.get("invoiceId"),
                "attempt_no": a.get("attemptNo"),
                "scheduled_for": _iso(a.get("scheduledFor")),
                "status": ow_util.code_desc(db, "DUN_STATUS", a.get("statusCd")),
            }
        )
    return rows


def _suspension_notifications(db):
    rows = []
    for n in db["notifications"].find({"kindCd": 3}).sort(
        [("tenantId", 1), ("sentAt", 1)]
    ):
        rows.append(
            {
                "id": n["_id"],
                "tenant_id": n.get("tenantId"),
                "kind": ow_util.code_desc(db, "NOTIF_KIND", n.get("kindCd")),
                "sent_at": _iso_dt(n.get("sentAt")),
            }
        )
    return rows


def _credit_notes(db, tenant_id: str):
    rows = []
    for cn in db["creditNotes"].find({"tenantId": tenant_id}).sort(
        [("issuedOn", 1), ("_id", 1)]
    ):
        rows.append(
            {
                "id": cn["_id"],
                "issued_on": _iso(cn.get("issuedOn")),
                "remaining_amount": ow_util.dec2(cn.get("remainingAmount")),
            }
        )
    return rows


def _scenario_fields(scen: str) -> dict:
    """Parse procs/scenarios/<module>/<NNN>.yaml `fields` entries:
    {final_name: (from_name, collect_bool)}. The transcripts record only
    the final names; the `from` mapping lives in the scenario yaml."""
    import re

    prefix, num = scen.split("-")
    module = {"RATING": "rating", "INVOICE": "invoicing", "DUNNING": "dunning"}[prefix]
    path = REPO_ROOT / "procs" / "scenarios" / module / f"{num}.yaml"
    out = {}
    for m in re.finditer(
        r"-\s*\{name:\s*(\w+),\s*from:\s*(\w+),[^}]*?(collect:\s*true)?\}", path.read_text()
    ):
        out[m.group(1)] = (m.group(2), bool(m.group(3)))
    return out


def run_scenario(db, payload: dict) -> dict:
    scen = payload["scenario"]
    entry = payload["entrypoint"]
    inputs = payload.get("inputs", {})
    fields = _scenario_fields(scen)
    bf_keys = set(payload.get("business_fields", {}))
    probe_keys = set((payload.get("probes") or {}).keys())
    business_fields: dict = {}
    probes: dict = {}

    def d(name):
        return _dt.date.fromisoformat(inputs[name])

    rows = []
    if entry == "billing.fn_usage_rating":
        rows = rating_service.usage_rating(db, inputs["tenant_id"], d("period_start"), d("period_end"))
    elif entry == "billing.fn_usage_summary":
        rows = rating_service.usage_summary(db, inputs["tenant_id"], d("period_start"), d("period_end"))
    elif entry == "billing.fn_invoice_preview":
        rows = invoicing_service.invoice_preview(db, inputs["tenant_id"], d("period_start"), d("period_end"))
    elif entry == "billing.fn_invoice_lines":
        rows = invoicing_service.invoice_lines(db, inputs["invoice_id"])
    elif entry == "billing.fn_overdue_accounts":
        rows = dunning_service.overdue_accounts(db, d("as_of"))
    elif entry == "billing.sp_finalize_rating":
        rating_service.finalize_rating(db, inputs["tenant_id"], d("period_start"), d("period_end"))
        rows = _rating_result_row(db, inputs["tenant_id"], d("period_start"))
    elif entry == "billing.sp_issue_invoice":
        invoicing_service.issue_invoice(db, inputs["tenant_id"], d("period_start"), d("period_end"))
        if "credit_ids" in bf_keys:
            cn = _credit_notes(db, inputs["tenant_id"])
            business_fields["credit_ids"] = [r["id"] for r in cn]
            business_fields["issued_on"] = [r["issued_on"] for r in cn]
            business_fields["remaining"] = [r["remaining_amount"] for r in cn]
        else:
            rows = _invoice_state(db, inputs["tenant_id"], d("period_start"))
    elif entry == "billing.sp_schedule_dunning":
        dunning_service.schedule_dunning(db, d("as_of"))
        inv1 = "60000000-0000-0000-0000-000000000001"
        inv2 = "60000000-0000-0000-0000-000000000002"
        inv_id = inv2 if "attempt_no" in bf_keys else inv1
        top = db["dunningAttempts"].find_one(
            {"invoiceId": inv_id}, sort=[("attemptNo", -1)]
        )
        for k in bf_keys:
            if k == "scheduled_for":
                business_fields[k] = _iso(top.get("scheduledFor"))
            elif k == "status":
                business_fields[k] = ow_util.code_desc(db, "DUN_STATUS", top.get("statusCd"))
            elif k == "attempt_no":
                business_fields[k] = top.get("attemptNo")
    elif entry == "billing.sp_suspend_overdue":
        dunning_service.suspend_overdue(db, d("as_of"))
        if scen == "DUNNING-005":  # recorded after_sql: CALL it a second time
            dunning_service.suspend_overdue(db, d("as_of"))
        if "notification_kinds" in bf_keys:
            kinds = [
                ow_util.code_desc(db, "NOTIF_KIND", n.get("kindCd"))
                for n in db["notifications"]
                .find({"tenantId": "00000000-0000-0000-0000-000000000005",
                       "kindCd": 3})
                .sort("sentAt", 1)
            ]
            business_fields["notification_kinds"] = kinds
        else:
            sub = db["subscriptions"].find_one(
                {"tenantId": "00000000-0000-0000-0000-000000000005"}
            )
            business_fields["status"] = ow_util.code_desc(
                db, "SUB_STATUS", (sub or {}).get("statusCd")
            )
            business_fields["suspended_on"] = _iso((sub or {}).get("suspendedOn"))

    # Collect business_fields from rows where not already set; `from`
    # maps the transcript name to the row key.
    for k in sorted(bf_keys - set(business_fields)):
        src, collect = fields.get(k, (k, False))
        vals = [r.get(src) for r in rows]
        if collect or len(rows) != 1:
            business_fields[k] = vals
        else:
            business_fields[k] = vals[0]

    for pid in probe_keys:
        if pid == "rating_result":
            probes[pid] = _rating_result_row(db, inputs["tenant_id"], d("period_start"))
        elif pid == "invoice_state":
            probes[pid] = _invoice_state(db, inputs["tenant_id"], d("period_start"))
        elif pid == "schedule_rows":
            probes[pid] = _schedule_rows(db)
        elif pid == "suspension_notifications":
            probes[pid] = _suspension_notifications(db)
        else:
            probes[pid] = "<no mongo equivalent recorded>"

    return {
        "scenario": scen,
        "entrypoint": entry,
        "mongo_entrypoint": ".".join(ENTRY_TO_SERVICE[entry]),
        "inputs": inputs,
        "business_fields": business_fields,
        "probes": probes,
    }


def _diff(expected: dict, actual: dict) -> dict:
    out = {}
    for section in ("business_fields", "probes"):
        e, a = expected.get(section, {}), actual.get(section, {})
        for name in sorted(set(e) | set(a)):
            if e.get(name, "<missing>") != a.get(name, "<missing>"):
                out.setdefault(section, {})[name] = {
                    "oracle": e.get(name, "<missing>"),
                    "mongo": a.get(name, "<missing>"),
                }
    return out


def _record(db, doc: dict) -> None:
    doc = dict(doc)
    doc["batch"] = "w3-b02"
    db[SCRATCH].insert_one(doc)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source-dsn-secret", required=True)
    ap.add_argument("--target-uri-secret", required=True)
    ap.add_argument("--target-db", required=True)
    args = ap.parse_args()

    allowed = json.loads(ALLOWED_TARGETS_FILE.read_text())
    if args.target_db not in allowed.get("databases", []):
        return _fail(f"target-db {args.target_db!r} not in allowed_targets")

    import oracledb  # lazy
    from pymongo import MongoClient

    raw = json.loads(_secret_env(args.source_dsn_secret))
    oracledb.defaults.fetch_decimals = True
    conn = oracledb.connect(user=raw["user"], password=raw["password"], dsn=raw["dsn"])
    client = MongoClient(_secret_env(args.target_uri_secret), serverSelectionTimeoutMS=5000)
    db = client[args.target_db]
    summary = {"batch": "w3-b02", "target_class": "local",
               "not_merge_evidence": True, "units": {}, "scenarios": []}

    unit_by_module = {"rating": "u-09-plsql-rating",
                      "invoicing": "u-10-plsql-invoicing",
                      "dunning": "u-11-plsql-dunning"}
    totals = {u: [0, 0] for u in unit_by_module.values()}
    try:
        loaded = fixture_load.load_baseline(conn, db)
        summary["fixture_loaded"] = loaded
        for module, unit in unit_by_module.items():
            tdir = ORACLE_TRANSCRIPTS / module
            out_dir = RECON_ROOT / unit / "parity"
            out_dir.mkdir(parents=True, exist_ok=True)
            for path in sorted(tdir.glob("*.json")):
                expected = json.loads(path.read_text())
                fixture_load.load_baseline(conn, db)
                actual = run_scenario(db, expected)
                failures = _diff(expected, actual)
                actual["parity"] = "PASS" if not failures else "FAIL"
                if failures:
                    actual["diffs"] = failures
                (out_dir / f"{expected['scenario']}.mongo.json").write_text(
                    json.dumps(actual, indent=1) + "\n"
                )
                totals[unit][1] += 1
                totals[unit][0] += 0 if failures else 1
                summary["scenarios"].append(
                    {"unit": unit, "scenario": expected["scenario"],
                     "verdict": actual["parity"], "diffs": failures or None}
                )
                _record(
                    db,
                    {"kind": "parity", "unit": unit,
                     "scenario": expected["scenario"],
                     "verdict": actual["parity"], "diffs": failures or []},
                )
        for unit, (ok, total) in totals.items():
            summary["units"][unit] = {
                "verdict": "PASS" if ok == total else "FAIL",
                "scenarios_pass": ok,
                "scenarios_total": total,
            }
    finally:
        try:
            fixture_load.load_baseline(conn, db)
        finally:
            client.close()
            conn.close()

    verdict = (
        "PASS"
        if all(u["verdict"] == "PASS" for u in summary["units"].values())
        else "FAIL"
    )
    summary["verdict"] = verdict
    print(json.dumps(summary, indent=1))
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
