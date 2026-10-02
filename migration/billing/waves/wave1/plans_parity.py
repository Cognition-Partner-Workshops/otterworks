#!/usr/bin/env python3
"""U1 route parity: plans module on BILLING_BACKEND=oracle vs BILLING_BACKEND=mongo.

Replays procs/scenarios/plans/001-005.yaml (fn_list_plans, fn_entitlement, sp_change_plan)
through the legacy-billing Flask app in-process, once per backend, and grades both against
the immutable transcripts procs/transcripts/plans/PLANS-00N.json (business fields + state
probes). Before every scenario the Oracle fixture's static tenants are reset to the checked-in
seed (procs/harness/oracle_record.reset_baseline) and the Mongo fixture is reloaded from it
with migration/billing/loaders/oracle_to_mongo.py, so both backends start from the same rows.
A second section records the /api/v1/billing facade responses on both backends and requires
them to be identical (GET /me's `customer` key excluded until U2).

Fixture only: requires `make oracle-billing-up` and `make mongo-billing-up`; never Atlas.

    make tp-u1-parity        # -> migration/billing/waves/wave1/U1.plans_parity.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from urllib.parse import urlparse

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "procs" / "harness"))
sys.path.insert(0, str(ROOT / "migration" / "billing" / "loaders"))
sys.path.insert(0, str(ROOT / "services" / "legacy-billing" / "app"))

SCENARIOS = ROOT / "procs" / "scenarios" / "plans"
TRANSCRIPTS = ROOT / "procs" / "transcripts" / "plans"
U1 = ["codes", "tenants", "plans", "subscriptions", "subscriptions_hist"]
STATUS = {10: "active", 20: "suspended", 30: "cancelled"}
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0", ""}
TENANT = "00000000-0000-0000-0000-000000000001"


def normalize(value, kind=None):
    if value is None:
        return None
    if kind == "decimal":
        return str(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    if kind == "integer":
        return int(value)
    if kind == "date":
        return dt.date.fromisoformat(str(value)[:10]).isoformat()
    return value


def capture(rows, specs):
    out = {}
    for spec in specs:
        if spec.get("collect_rows"):
            out[spec["name"]] = [
                {c: normalize(r.get(c), k) for c, k in spec["columns"].items()} for r in rows
            ]
        elif spec.get("collect"):
            out[spec["name"]] = [normalize(r.get(spec["from"]), spec.get("type")) for r in rows]
        else:
            out[spec["name"]] = normalize(rows[0].get(spec["from"]), spec.get("type")) if rows else None
    return out


class Fixture:
    def __init__(self, oracle_dsn_env, mongo_uri_env):
        import oracle_record  # procs/harness: STATIC_TENANTS + 03_seed_static.sql statements
        import oracle_to_mongo
        import recon
        from pymongo import MongoClient

        self.oracle_record = oracle_record
        self.loader = oracle_to_mongo
        self.oracle_dsn_env, self.mongo_uri_env = oracle_dsn_env, mongo_uri_env
        kw = recon._oracle_kwargs(os.environ[oracle_dsn_env])
        self.oracle_host = recon._dsn_host(kw["dsn"])
        mongo_uri = os.environ[mongo_uri_env]
        if urlparse(mongo_uri).hostname not in LOCAL_HOSTS or self.oracle_host not in LOCAL_HOSTS:
            raise SystemExit("plans parity runs against the local fixtures only, never the live host or Atlas")
        from backends import mongo as mongo_backend

        self.database = mongo_backend.database_name()
        self.mongo = MongoClient(mongo_uri, tz_aware=True, serverSelectionTimeoutMS=10000)
        self.mongo.admin.command("ping")
        self.dsn_kw = kw

    def reset(self):
        """Plans-module baseline: static tenants' subscriptions(+hist) back to 03_seed_static.sql.

        Narrower than oracle_record.reset_baseline (which rebuilds every table of the static
        tenants and trips on the planted cross-tenant invoice rows of 04_upgrade_static.sql);
        the plans module only writes subscriptions, subscriptions_hist and the audit log, and
        the seeded subscription rows are referenced by rating_results, so they are restored in
        place (MERGE) while rows change_plan created are deleted.
        """
        import oracledb

        ids = ", ".join(f"'{t}'" for t in self.oracle_record.STATIC_TENANTS)
        merges, seed_ids = [], []
        for statement in self.oracle_record.seed_statements():
            m = re.match(r"INSERT INTO subscriptions \(([^)]*)\) VALUES \((.*)\)$", statement, re.I | re.S)
            if not m:
                continue
            cols = [c.strip() for c in m.group(1).split(",")]
            vals = [v.strip() for v in m.group(2).split(",")]
            if vals[cols.index("tenant_id")].strip("'") not in self.oracle_record.STATIC_TENANTS:
                continue
            seed_ids.append(vals[cols.index("id")])
            using = ", ".join(f"{v} AS {c}" for c, v in zip(cols, vals))
            sets = ", ".join(f"s.{c} = x.{c}" for c in cols if c != "id")
            changed = " + ".join(f"DECODE(s.{c}, x.{c}, 0, 1)" for c in cols if c != "id")
            merges.append(
                f"MERGE INTO subscriptions s USING (SELECT {using} FROM dual) x ON (s.id = x.id) "
                f"WHEN MATCHED THEN UPDATE SET {sets} WHERE {changed} > 0 "
                f"WHEN NOT MATCHED THEN INSERT ({', '.join(cols)}) VALUES ({', '.join('x.' + c for c in cols)})"
            )
        with oracledb.connect(**self.dsn_kw) as conn, conn.cursor() as cur:
            cur.execute(f"DELETE FROM subscriptions WHERE tenant_id IN ({ids}) AND id NOT IN ({', '.join(seed_ids)})")
            for merge in merges:
                cur.execute(merge)
            cur.execute(f"DELETE FROM subscriptions_hist WHERE tenant_id IN ({ids})")
            conn.commit()
        for name in U1:
            self.mongo[self.database].drop_collection(name)
        rc = self.loader.main([
            "--mode", "fixture", "--collections", ",".join(U1),
            "--oracle-dsn-env", self.oracle_dsn_env, "--mongo-uri-env", self.mongo_uri_env,
            "--mongo-db", self.database,
        ])
        if rc != 0:
            raise SystemExit("fixture reload failed")

    def probe_oracle(self, tenant_id):
        import oracledb

        oracledb.defaults.fetch_decimals = True
        with oracledb.connect(**self.dsn_kw) as conn, conn.cursor() as cur:
            cur.execute(
                """SELECT plan_id, starts_on, ends_on,
                          DECODE(status_cd, 10, 'active', 20, 'suspended', 30, 'cancelled', 'UNKNOWN') AS status
                     FROM subscriptions WHERE tenant_id = :1 ORDER BY starts_on""",
                (tenant_id,),
            )
            return [
                {"plan_id": r[0], "starts_on": r[1].date().isoformat() if r[1] else None,
                 "ends_on": r[2].date().isoformat() if r[2] else None, "status": r[3]}
                for r in cur.fetchall()
            ]

    def probe_mongo(self, tenant_id):
        return [
            {"plan_id": d.get("planId"), "starts_on": d["startsOn"].date().isoformat(),
             "ends_on": d["endsOn"].date().isoformat() if d.get("endsOn") else None,
             "status": STATUS.get(d.get("statusCd"), "UNKNOWN")}
            for d in self.mongo[self.database].subscriptions.find({"tenantId": tenant_id}).sort("startsOn", 1)
        ]

    def probe(self, backend, tenant_id):
        return self.probe_oracle(tenant_id) if backend == "oracle" else self.probe_mongo(tenant_id)

    def hist_count(self):
        return self.mongo[self.database].subscriptions_hist.count_documents({})


def run_scenario(client, fixture, backend, scenario):
    inputs = {i["name"]: i["value"] for i in scenario.get("inputs", [])}
    entry = scenario["entrypoint"]
    if entry == "billing.fn_list_plans":
        rows = client.get("/plans").get_json()
    elif entry == "billing.fn_entitlement":
        rows = client.get(f"/plans/{inputs['tenant_id']}/entitlement", query_string={"on": inputs["as_of"]}).get_json()
    elif entry == "billing.sp_change_plan":
        resp = client.post(f"/plans/{inputs['tenant_id']}/change",
                           data={"plan_id": inputs["plan_id"], "effective_on": inputs["effective_on"]})
        if resp.status_code != 302:
            raise RuntimeError(f"{scenario['id']} on {backend}: HTTP {resp.status_code}")
        rows = fixture.probe(backend, inputs["tenant_id"])
    else:
        raise RuntimeError(f"unknown entrypoint {entry}")
    fields = capture(rows, scenario["fields"])
    probes = {p["id"]: fixture.probe(backend, inputs["tenant_id"]) for p in scenario.get("probes", [])}
    return fields, probes


def facade_snapshot(client):
    headers = {"X-User-ID": TENANT, "X-User-Email": "tenant-one@example.com"}
    me = client.get("/api/v1/billing/me", query_string={"on": "2026-02-28"}, headers=headers).get_json()
    me.pop("customer", None)
    future = (dt.date.today() + dt.timedelta(days=30)).isoformat()
    change = client.post("/api/v1/billing/plan-change", headers=headers,
                         json={"plan_id": "10000000-0000-0000-0000-000000000003", "effective_on": future})
    return {
        "GET /api/v1/billing/plans": client.get("/api/v1/billing/plans", headers=headers).get_json(),
        "GET /api/v1/billing/entitlement?on=2026-02-28":
            client.get("/api/v1/billing/entitlement", query_string={"on": "2026-02-28"}, headers=headers).get_json(),
        "GET /api/v1/billing/me (customer excluded until U2)": me,
        f"POST /api/v1/billing/plan-change (plan 3, effective {future})": {"status": change.status_code, "body": change.get_json()},
    }


def non_u1_status(client):
    headers = {"X-User-ID": TENANT}
    return {path: client.get(f"/api/v1/billing/{path}", headers=headers).status_code
            for path in ("usage", "invoices", "customer")}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--oracle-dsn-env", default="OW_TP_ORACLE_FIXTURE_DSN")
    p.add_argument("--mongo-uri-env", default="OW_TP_MONGO_FIXTURE_URI")
    p.add_argument("--out", default=str(HERE / "U1.plans_parity.json"))
    args = p.parse_args(argv)

    os.environ["MONGODB_ATLAS_URI"] = os.environ[args.mongo_uri_env]  # process-local: the fixture mongod
    os.environ.setdefault("ORACLE_PORT", "52521")
    fixture = Fixture(args.oracle_dsn_env, args.mongo_uri_env)
    from app import app

    scenarios = [yaml.safe_load(path.read_text()) for path in sorted(SCENARIOS.glob("*.yaml"))]
    report = {
        "kind": "plans-parity", "unit": "U1", "run_mode": "fixture", "merge_evidence": False,
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": {"oracle": f"local fixture {fixture.oracle_host}", "mongo": f"local fixture, database {fixture.database}"},
        "transcripts": "procs/transcripts/plans/PLANS-001..005.json (immutable)",
        "scenarios": [], "facade": {}, "verdict": "pass",
    }
    for scenario in scenarios:
        transcript = json.loads((TRANSCRIPTS / f"{scenario['id']}.json").read_text())
        entry = {"id": scenario["id"], "entrypoint": scenario["entrypoint"], "description": scenario["description"],
                 "expected": {"business_fields": transcript["business_fields"], "probes": transcript["probes"]}, "backends": {}}
        for backend in ("oracle", "mongo"):
            fixture.reset()
            os.environ["BILLING_BACKEND"] = backend
            hist_before = fixture.hist_count()
            fields, probes = run_scenario(app.test_client(), fixture, backend, scenario)
            result = {"business_fields": fields, "probes": probes,
                      "fields_match": fields == transcript["business_fields"], "probes_match": probes == transcript["probes"]}
            if backend == "mongo" and scenario["entrypoint"] == "billing.sp_change_plan":
                result["subscriptions_hist_pre_images"] = fixture.hist_count() - hist_before
            entry["backends"][backend] = result
        entry["pass"] = all(b["fields_match"] and b["probes_match"] for b in entry["backends"].values()) and (
            entry["backends"]["oracle"]["business_fields"] == entry["backends"]["mongo"]["business_fields"])
        if not entry["pass"]:
            report["verdict"] = "fail"
        report["scenarios"].append(entry)
        print(f"{scenario['id']}: oracle={'ok' if entry['backends']['oracle']['fields_match'] else 'MISMATCH'} "
              f"mongo={'ok' if entry['backends']['mongo']['fields_match'] else 'MISMATCH'} -> {'pass' if entry['pass'] else 'FAIL'}")

    for backend in ("oracle", "mongo"):
        fixture.reset()
        os.environ["BILLING_BACKEND"] = backend
        report["facade"][backend] = facade_snapshot(app.test_client())
        report["facade"][f"{backend}_non_u1_routes"] = non_u1_status(app.test_client())
    report["facade"]["identical"] = report["facade"]["oracle"] == report["facade"]["mongo"]
    report["facade"]["non_u1_routes_501_on_mongo"] = all(
        code == 501 for code in report["facade"]["mongo_non_u1_routes"].values())
    if not (report["facade"]["identical"] and report["facade"]["non_u1_routes_501_on_mongo"]):
        report["verdict"] = "fail"
    print(f"facade U1 routes identical on both backends: {report['facade']['identical']}; "
          f"non-U1 routes 501 on mongo: {report['facade']['non_u1_routes_501_on_mongo']}")
    fixture.reset()

    out = Path(args.out)
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(f"plans parity {report['verdict']} -> {out}")
    return 0 if report["verdict"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
