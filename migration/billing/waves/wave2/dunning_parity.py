#!/usr/bin/env python3
"""U5 route parity: dunning module on BILLING_BACKEND=oracle vs BILLING_BACKEND=mongo.

Replays procs/scenarios/dunning/001-005.yaml (fn_overdue_accounts, sp_schedule_dunning,
sp_suspend_overdue) through the legacy-billing Flask app in-process, once per backend, and
grades both against the immutable transcripts procs/transcripts/dunning/DUNNING-00N.json
(business fields + state probes). Oracle captures run the procs/oracle/oracle_map.yaml SQL the
recorder used; the Mongo captures read the same facts from the documents. Before every scenario
the Oracle fixture's static tenants are put back to 03_seed_static.sql (tenants, subscriptions,
dunning_attempts, notifications; invoices are read-only to this module) and the Mongo fixture is
reloaded from it: U1 + U5 collections through migration/billing/loaders/oracle_to_mongo.py, the
read-only `invoices` copy through recon.load_documents (U4 owns its loader). A second section
records GET /api/v1/billing/admin/overdue and /admin/dunning on both backends and requires them to
be identical. Extends wave1/plans_parity.py (fixture guard, capture, normalisation).

Fixture only: requires `make oracle-billing-up` and `make mongo-billing-up`; never Atlas.

    make tp-u5-parity        # -> migration/billing/waves/wave2/U5.dunning_parity.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from decimal import Decimal
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "migration" / "billing" / "waves" / "wave1"))
sys.path.insert(0, str(ROOT / "migration" / "billing" / "recon"))

import plans_parity  # noqa: E402  (wave 1: fixture guard, loader reload, capture, normalize)

SCENARIOS = ROOT / "procs" / "scenarios" / "dunning"
TRANSCRIPTS = ROOT / "procs" / "transcripts" / "dunning"
ORACLE_MAP = ROOT / "procs" / "oracle" / "oracle_map.yaml"
U5 = ["dunning_attempts", "notifications", "billing_audit_log"]
RESET_TABLES = ["tenants", "subscriptions", "dunning_attempts", "notifications"]
DUN_STATUS = {10: "scheduled", 20: "sent", 30: "skipped"}
NOTIF_KIND = {1: "invoice", 2: "dunning", 3: "suspension"}
ADMIN = {"X-User-ID": plans_parity.TENANT, "X-User-Roles": "ADMIN"}
AS_OF = "2026-02-28"


class Fixture(plans_parity.Fixture):
    def __init__(self, oracle_dsn_env, mongo_uri_env):
        super().__init__(oracle_dsn_env, mongo_uri_env)
        import recon

        self.recon = recon
        self.oracle_map = yaml.safe_load(ORACLE_MAP.read_text())["scenarios"]

    def _merges(self, table):
        """MERGE every 03_seed_static.sql row of `table` for the static tenants back in place."""
        merges, seed_ids = [], []
        for statement in self.oracle_record.seed_statements():
            m = re.match(rf"INSERT INTO {table} \(([^)]*)\) VALUES \((.*)\)$", statement, re.I | re.S)
            if not m:
                continue
            cols = [c.strip() for c in m.group(1).split(",")]
            vals = [v.strip() for v in m.group(2).split(",")]
            owner = vals[cols.index("tenant_id")] if "tenant_id" in cols else vals[cols.index("id")]
            if owner.strip("'") not in self.oracle_record.STATIC_TENANTS:
                continue
            seed_ids.append(vals[cols.index("id")])
            using = ", ".join(f"{v} AS {c}" for c, v in zip(cols, vals))
            sets = ", ".join(f"s.{c} = x.{c}" for c in cols if c != "id")
            changed = " + ".join(f"DECODE(s.{c}, x.{c}, 0, 1)" for c in cols if c != "id")
            merges.append(
                f"MERGE INTO {table} s USING (SELECT {using} FROM dual) x ON (s.id = x.id) "
                f"WHEN MATCHED THEN UPDATE SET {sets} WHERE {changed} > 0 "
                f"WHEN NOT MATCHED THEN INSERT ({', '.join(cols)}) VALUES ({', '.join('x.' + c for c in cols)})"
            )
        return merges, seed_ids

    def reset(self):
        """Dunning-module baseline on both fixtures.

        The module writes tenants.status_cd, subscriptions (status_cd, suspended_on, + hist
        pre-images), dunning_attempts, notifications and the audit log; invoices are only read.
        Seed rows are restored in place (MERGE), rows the module created are deleted.
        """
        import oracledb

        ids = ", ".join(f"'{t}'" for t in self.oracle_record.STATIC_TENANTS)
        with oracledb.connect(**self.dsn_kw) as conn, conn.cursor() as cur:
            for table in ("notifications", "dunning_attempts", "subscriptions"):
                merges, seed_ids = self._merges(table)
                cur.execute(f"DELETE FROM {table} WHERE tenant_id IN ({ids}) AND id NOT IN ({', '.join(seed_ids)})")
                for merge in merges:
                    cur.execute(merge)
            for merge in self._merges("tenants")[0]:
                cur.execute(merge)
            cur.execute(f"DELETE FROM subscriptions_hist WHERE tenant_id IN ({ids})")
            conn.commit()
        db = self.mongo[self.database]
        for name in plans_parity.U1 + U5 + ["invoices"]:
            db.drop_collection(name)
        rc = self.loader.main([
            "--mode", "fixture", "--collections", ",".join(plans_parity.U1 + U5),
            "--oracle-dsn-env", self.oracle_dsn_env, "--mongo-uri-env", self.mongo_uri_env,
            "--mongo-db", self.database,
        ])
        if rc != 0:
            raise SystemExit("fixture reload failed")
        inputs = self.recon.build_inputs(self.recon.SPEC_PATH, self.recon.TOLERANCES_PATH, None)
        source = self.recon.OracleSource(os.environ[self.oracle_dsn_env], self.oracle_dsn_env, "OW_BILLING", 1)
        tables = {t: source.rows(t) for t in ("INVOICES", "INVOICE_LINES")}
        docs = self.recon.load_documents(inputs, tables)["invoices"]
        if docs:
            db.invoices.insert_many(docs)

    # -- captures: Oracle runs the recorder's SQL (oracle_map.yaml); Mongo reads the documents --

    def oracle_rows(self, sql):
        import oracledb

        oracledb.defaults.fetch_decimals = True
        with oracledb.connect(**self.dsn_kw) as conn, conn.cursor() as cur:
            cur.execute(sql)
            names = [d[0].lower() for d in cur.description]
            return [dict(zip(names, r)) for r in cur.fetchall()]

    def mongo_rows(self, scenario_id, probe=None):
        db = self.mongo[self.database]
        if probe == "schedule_rows":
            return [{"invoice_id": d["invoiceId"], "attempt_no": d["attemptNo"], "scheduled_for": d["scheduledFor"].date().isoformat(),
                     "status": DUN_STATUS.get(d["statusCd"], "UNKNOWN")}
                    for d in db.dunning_attempts.find().sort([("invoiceId", 1), ("attemptNo", 1)])]
        if probe == "suspension_notifications":
            return [{"id": d["_id"], "tenant_id": d["tenantId"], "kind": NOTIF_KIND.get(d["kindCd"], "UNKNOWN"),
                     "sent_at": d["sentAt"].strftime("%Y-%m-%dT%H:%M:%SZ")}
                    for d in db.notifications.find({"kindCd": 3}).sort([("tenantId", 1), ("sentAt", 1)])]
        if scenario_id in ("DUNNING-002", "DUNNING-003"):
            invoice = "60000000-0000-0000-0000-00000000000" + ("1" if scenario_id == "DUNNING-002" else "2")
            d = db.dunning_attempts.find_one({"invoiceId": invoice}, sort=[("attemptNo", -1)])
            return [] if d is None else [{"attempt_no": d["attemptNo"], "scheduled_for": d["scheduledFor"].date().isoformat(),
                                          "status": DUN_STATUS.get(d["statusCd"], "UNKNOWN")}]
        if scenario_id == "DUNNING-004":
            return [{"status": plans_parity.STATUS.get(d.get("statusCd"), "UNKNOWN"),
                     "suspended_on": d["suspendedOn"].date().isoformat() if d.get("suspendedOn") else None}
                    for d in db.subscriptions.find({"tenantId": "00000000-0000-0000-0000-000000000005"})]
        if scenario_id == "DUNNING-005":
            return [{"kind": NOTIF_KIND.get(d["kindCd"], "UNKNOWN")}
                    for d in db.notifications.find({"tenantId": "00000000-0000-0000-0000-000000000005", "kindCd": 3}).sort("sentAt", 1)]
        raise RuntimeError(f"no mongo capture for {scenario_id}/{probe}")

    def rows(self, backend, scenario_id, probe=None):
        if backend == "oracle":
            entry = self.oracle_map[scenario_id]
            return self.oracle_rows(entry["probes"][probe] if probe else entry["capture_query"])
        return self.mongo_rows(scenario_id, probe)

    def audit_count(self):
        return self.mongo[self.database].billing_audit_log.count_documents({})


def plain(value):
    """Oracle NUMBER arrives as Decimal (fetch_decimals); the transcripts hold ints."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else str(value)
    return plans_parity.normalize(value)


def run_scenario(client, fixture, backend, scenario):
    inputs = {i["name"]: str(i["value"]) for i in scenario.get("inputs", [])}
    entry = scenario["entrypoint"]
    if entry == "billing.fn_overdue_accounts":
        rows = client.get("/api/dunning/overdue", query_string={"as_of": inputs["as_of"]}).get_json()
    else:
        route = {"billing.sp_schedule_dunning": "/api/dunning/schedule", "billing.sp_suspend_overdue": "/api/dunning/suspend"}[entry]
        runs = 2 if scenario.get("after_sql") else 1  # DUNNING-005: the recorder called the procedure twice
        for _ in range(runs):
            resp = client.post(route, data={"as_of": inputs["as_of"]})
            if resp.status_code != 200:
                raise RuntimeError(f"{scenario['id']} on {backend}: HTTP {resp.status_code}")
        rows = fixture.rows(backend, scenario["id"])
    fields = plans_parity.capture(rows, scenario["fields"])
    probes = {p["id"]: [{k: plain(v) for k, v in r.items()} for r in fixture.rows(backend, scenario["id"], p["id"])]
              for p in scenario.get("probes", [])}
    return fields, probes


def facade_snapshot(client):
    overdue = client.get("/api/v1/billing/admin/overdue", query_string={"as_of": AS_OF}, headers=ADMIN)
    client.post("/api/dunning/schedule", data={"as_of": "2026-02-14"})
    dunning = client.get("/api/v1/billing/admin/dunning", query_string={"as_of": AS_OF}, headers=ADMIN)
    return {
        f"GET /api/v1/billing/admin/overdue?as_of={AS_OF}": {"status": overdue.status_code, "body": overdue.get_json()},
        f"GET /api/v1/billing/admin/dunning?as_of={AS_OF} (after schedule 2026-02-14)": {"status": dunning.status_code, "body": dunning.get_json()},
        "GET /api/v1/billing/admin/overdue without ADMIN": client.get("/api/v1/billing/admin/overdue", headers={"X-User-ID": plans_parity.TENANT}).status_code,
        "GET /api/v1/billing/admin/dunning?as_of=bad": client.get("/api/v1/billing/admin/dunning", query_string={"as_of": "bad"}, headers=ADMIN).status_code,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--oracle-dsn-env", default="OW_TP_ORACLE_FIXTURE_DSN")
    p.add_argument("--mongo-uri-env", default="OW_TP_MONGO_FIXTURE_URI")
    p.add_argument("--out", default=str(HERE / "U5.dunning_parity.json"))
    args = p.parse_args(argv)

    os.environ["MONGODB_ATLAS_URI"] = os.environ[args.mongo_uri_env]  # process-local: the fixture mongod
    os.environ.setdefault("ORACLE_PORT", "52521")
    fixture = Fixture(args.oracle_dsn_env, args.mongo_uri_env)
    from app import app

    scenarios = [yaml.safe_load(path.read_text()) for path in sorted(SCENARIOS.glob("*.yaml"))]
    report = {
        "kind": "dunning-parity", "unit": "U5", "run_mode": "fixture", "merge_evidence": False,
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": {"oracle": f"local fixture {fixture.oracle_host}", "mongo": f"local fixture, database {fixture.database}"},
        "transcripts": "procs/transcripts/dunning/DUNNING-001..005.json (immutable)",
        "scenarios": [], "facade": {}, "verdict": "pass",
    }
    for scenario in scenarios:
        transcript = json.loads((TRANSCRIPTS / f"{scenario['id']}.json").read_text())
        entry = {"id": scenario["id"], "entrypoint": scenario["entrypoint"], "description": scenario["description"],
                 "expected": {"business_fields": transcript["business_fields"], "probes": transcript["probes"]}, "backends": {}}
        for backend in ("oracle", "mongo"):
            fixture.reset()
            os.environ["BILLING_BACKEND"] = backend
            audit_before = fixture.audit_count()
            fields, probes = run_scenario(app.test_client(), fixture, backend, scenario)
            result = {"business_fields": fields, "probes": probes,
                      "fields_match": fields == transcript["business_fields"], "probes_match": probes == transcript["probes"]}
            if backend == "mongo" and scenario["kind"] == "procedure":
                result["billing_audit_log_rows"] = fixture.audit_count() - audit_before
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
    report["facade"]["identical"] = report["facade"]["oracle"] == report["facade"]["mongo"]
    if not report["facade"]["identical"]:
        report["verdict"] = "fail"
    print(f"facade U5 routes identical on both backends: {report['facade']['identical']}")
    fixture.reset()

    out = Path(args.out)
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(f"dunning parity {report['verdict']} -> {out}")
    return 0 if report["verdict"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
