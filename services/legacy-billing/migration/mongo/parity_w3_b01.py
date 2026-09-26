#!/usr/bin/env python3
"""Batch w3-b01 parity replay: migrated PKG_OW_UTIL/PKG_PLANS service vs the
recorded Oracle transcripts (procs/oracle/transcripts/plans/) plus live
read-only calls into the fixture for u-07 helper parity.

For each plans scenario the script resets the migrated baseline
(fixture_load.load_baseline), runs the equivalent ow_util/plans_service
operation against ow_billing_migration, shapes the result exactly like the
recorded transcript (business_fields + probes), and compares verbatim.

Write targets: spec collections used (codes, plans, tenants, subscriptions,
subscriptionsHist, billingAuditLog — dropped+recreated by the baseline
loader) plus the declared batch scratch `ow_billing_migration.parity_w3_b01`
(one transcript summary document per check/scenario).

Transcripts are written under
services/legacy-billing/migration/mongo/recon/<unit>/parity/.

    env -u MONGODB_ATLAS_URI OW_BILLING_FIXTURE_DSN='{...}' \
        MONGO_LOCAL_URI=mongodb://localhost:27017 \
        python3 services/legacy-billing/migration/mongo/parity_w3_b01.py \
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

import fixture_load
import ow_util
import plans_service

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[3]
ORACLE_TRANSCRIPTS = REPO_ROOT / "procs" / "oracle" / "transcripts" / "plans"
RECON_ROOT = HERE / "recon"
SCRATCH = "parity_w3_b01"
ALLOWED_TARGETS_FILE = REPO_ROOT / ".migration" / "allowed_targets.json"


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


def _sub_rows(db, tenant_id: str) -> list[dict]:
    """Probe equivalent of the recorded subscription_rows query."""
    rows = []
    for d in db["subscriptions"].find({"tenantId": tenant_id}).sort("startsOn", 1):
        rows.append(
            {
                "plan_id": d.get("planId"),
                "starts_on": _iso(d.get("startsOn")),
                "ends_on": _iso(d.get("endsOn")),
                "status": plans_service.status_text(d.get("statusCd")),
            }
        )
    return rows


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
    doc["batch"] = "w3-b01"
    db[SCRATCH].insert_one(doc)


def run_scenario(db, payload: dict) -> dict:
    """Replay one plans scenario on the migrated model; returns transcript-shaped dict."""
    scen = payload["scenario"]
    entry = payload["entrypoint"]
    inputs = payload.get("inputs", {})
    business_fields: dict = {}
    probes: dict = {}

    if entry == "billing.fn_list_plans":
        rows = plans_service.list_plans(db)
        business_fields["codes"] = [r["code"] for r in rows]
        business_fields["fees"] = [r["monthly_fee"] for r in rows]
    elif entry == "billing.fn_entitlement":
        rows = plans_service.entitlement(
            db, inputs["tenant_id"], _dt.date.fromisoformat(inputs["as_of"])
        )
        if rows:
            row = rows[0]
            business_fields["plan_code"] = row["plan_code"]
            business_fields["tier"] = row["tier"]
            business_fields["included_units"] = row["included_units"]
            business_fields["subscription_status"] = row["subscription_status"]
    elif entry == "billing.sp_change_plan":
        plans_service.change_plan(
            db,
            inputs["tenant_id"],
            inputs["plan_id"],
            _dt.date.fromisoformat(inputs["effective_on"]),
        )
        business_fields["subscriptions"] = _sub_rows(db, inputs["tenant_id"])
    else:
        raise RuntimeError(f"no replay mapping for {entry}")

    for probe_id in (payload.get("probes") or {}):
        if probe_id == "subscription_rows":
            probes["subscription_rows"] = _sub_rows(db, inputs["tenant_id"])
        else:
            probes[probe_id] = "<no mongo equivalent recorded>"

    return {
        "scenario": scen,
        "module": "plans",
        "entrypoint": entry,
        "mongo_entrypoint": "plans_service."
        + {
            "billing.fn_list_plans": "list_plans",
            "billing.fn_entitlement": "entitlement",
            "billing.sp_change_plan": "change_plan",
        }[entry],
        "inputs": inputs,
        "business_fields": business_fields,
        "probes": probes,
    }


def run_u07(conn, db) -> dict:
    """PKG_OW_UTIL helper parity vs live fixture calls (read-only funcs)."""
    import oracledb  # lazy, same as main()

    cur = conn.cursor()
    report: dict = {"checks": {}, "mismatches": []}

    def note(name, oracle, mongo):
        if oracle != mongo:
            report["mismatches"].append(
                {"check": name, "oracle": oracle, "mongo": mongo}
            )

    # f_code_desc for every CODES row + one miss
    cur.execute("SELECT CODE_TYPE, CODE_VAL FROM CODES ORDER BY CODE_TYPE, CODE_VAL")
    pairs = cur.fetchall() + [("NO_SUCH_TYPE", 99)]
    n = 0
    for code_type, code_val in pairs:
        oracle = cur.callfunc(
            "pkg_ow_util.f_code_desc", oracledb.DB_TYPE_VARCHAR, [code_type, code_val]
        )
        mongo = ow_util.code_desc(db, code_type, code_val)
        note(f"f_code_desc({code_type},{code_val})", oracle, mongo)
        n += 1
    report["checks"]["f_code_desc"] = n

    # f_md5_uuid on the inputs sp_change_plan actually feeds it
    for s in ["tenant|plan|2026-03-01",
              ("a0000000-0000-0000-0000-000000000001"
               "10000000-0000-0000-0000-0000000000022026-01-01")]:
        oracle = cur.callfunc("pkg_ow_util.f_md5_uuid", oracledb.DB_TYPE_VARCHAR, [s])
        note(f"f_md5_uuid({s[:24]}...)", oracle, ow_util.md5_uuid(s))
    report["checks"]["f_md5_uuid"] = 2

    # f_dt2str / f_str2dt round trip
    d = _dt.date(2026, 2, 20)
    oracle = cur.callfunc("pkg_ow_util.f_dt2str", oracledb.DB_TYPE_VARCHAR, [d])
    note("f_dt2str(2026-02-20)", oracle, ow_util.dt2str(d))
    oracle = cur.callfunc("pkg_ow_util.f_str2dt", oracledb.DB_TYPE_DATE, ["20-FEB-26"])
    mongo = ow_util.str2dt("20-FEB-26")
    note("f_str2dt('20-FEB-26')", _iso(oracle), _iso(mongo))
    for dirty in ["31-FEB-24", "N/A", "1/1/1900"]:
        oracle = cur.callfunc("pkg_ow_util.f_str2dt", oracledb.DB_TYPE_DATE, [dirty])
        mongo = ow_util.str2dt(dirty)
        note(f"f_str2dt({dirty!r})", _iso(oracle), _iso(mongo))
    report["checks"]["date_funcs"] = 4

    # log_msg -> billingAuditLog insert (autonomous-commit equivalent)
    before = db["billingAuditLog"].count_documents({})
    ok = ow_util.log_msg(db, "PLANS", "parity check message")
    doc = db["billingAuditLog"].find_one(sort=[("_id", -1)])
    verified = (
        ok
        and db["billingAuditLog"].count_documents({}) == before + 1
        and doc
        and doc.get("module") == "PLANS"
        and doc.get("message") == "parity check message"
    )
    report["checks"]["log_msg"] = 1
    if not verified:
        report["mismatches"].append(
            {"check": "log_msg", "oracle": "inserted+committed",
             "mongo": f"ok={ok} last={doc}"}
        )
    cur.close()
    return report


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
    conn = oracledb.connect(
        user=raw["user"], password=raw["password"], dsn=raw["dsn"]
    )
    client = MongoClient(_secret_env(args.target_uri_secret),
                         serverSelectionTimeoutMS=5000)
    db = client[args.target_db]
    summary = {"batch": "w3-b01", "target_class": "local",
               "not_merge_evidence": True, "units": {}, "scenarios": []}

    try:
        loaded = fixture_load.load_baseline(conn, db)
        summary["fixture_loaded"] = loaded

        # --- u-07-plsql-util ---
        u07 = run_u07(conn, db)
        u07_dir = RECON_ROOT / "u-07-plsql-util" / "parity"
        u07_dir.mkdir(parents=True, exist_ok=True)
        (u07_dir / "PKG_OW_UTIL.parity.json").write_text(
            json.dumps(u07, indent=1) + "\n"
        )
        u07_pass = not u07["mismatches"]
        summary["units"]["u-07-plsql-util"] = {
            "verdict": "PASS" if u07_pass else "FAIL",
            "mismatches": len(u07["mismatches"]),
        }
        _record(
            db,
            {"kind": "parity", "unit": "u-07-plsql-util",
             "verdict": "PASS" if u07_pass else "FAIL",
             "checks": u07["checks"], "mismatches": u07["mismatches"]},
        )

        # --- u-08-plsql-plans ---
        u08_dir = RECON_ROOT / "u-08-plsql-plans" / "parity"
        u08_dir.mkdir(parents=True, exist_ok=True)
        u08_fail = 0
        for path in sorted(ORACLE_TRANSCRIPTS.glob("PLANS-*.json")):
            expected = json.loads(path.read_text())
            # Each scenario replays from the deterministic baseline.
            fixture_load.load_baseline(conn, db)
            actual = run_scenario(db, expected)
            failures = _diff(expected, actual)
            passed = not failures
            actual["parity"] = "PASS" if passed else "FAIL"
            if failures:
                actual["diffs"] = failures
                u08_fail += 1
            (u08_dir / f"{expected['scenario']}.mongo.json").write_text(
                json.dumps(actual, indent=1) + "\n"
            )
            summary["scenarios"].append(
                {"scenario": expected["scenario"], "verdict": actual["parity"],
                 "diffs": failures or None}
            )
            _record(
                db,
                {"kind": "parity", "unit": "u-08-plsql-plans",
                 "scenario": expected["scenario"],
                 "verdict": actual["parity"], "diffs": failures or []},
            )
        summary["units"]["u-08-plsql-plans"] = {
            "verdict": "PASS" if u08_fail == 0 else "FAIL",
            "scenarios_pass": len(summary["scenarios"]) - u08_fail,
            "scenarios_total": len(summary["scenarios"]),
        }
    finally:
        # Leave the target quiescent: reload the deterministic baseline so a
        # recon re-run sees Tier-1 counts identical to the source.
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
