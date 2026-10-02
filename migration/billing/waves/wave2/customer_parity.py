#!/usr/bin/env python3
"""U2 route parity: GET /api/v1/billing/customer and the `customer` key of GET /api/v1/billing/me,
BILLING_BACKEND=oracle vs BILLING_BACKEND=mongo, field for field.

U2 has no PL/SQL entrypoint (facade-side SQL only), so there are no procs transcripts to grade against:
the Oracle backend's response is the reference and the Mongo backend must return the identical JSON
(status and body) for every probed tenant. The Mongo fixture is first reloaded from the Oracle fixture
with migration/billing/loaders/oracle_to_mongo.py (U1 collections for /me's bootstrap plus customers and
customers_hist, two passes so the rerun no-op is recorded), so both backends serve the same rows.

Probed tenants, picked from the Oracle fixture so each anomaly class the unit owns is covered: the static
OtterWorks Admin customer (four EAV rows, case-variant names), the first customer per class among the
demo-seeded tenants (dirty SIGNUP_DT, malformed RELATED_ACCT_IDS, attributes present, no attributes, all
clean) and a tenant without a customer_master row (404 on both). The route serves one customer per tenant,
so a second section renders every planted anomaly row (fixtures/demo.json `dirty_dates` and
`malformed_csv_lists` cust_ids) through both backends' row renderers and requires the same JSON: the
verbatim text is what the API returns, the typed siblings never surface.

Fixture only: requires `make oracle-billing-up` (seeded, `make oracle-billing-seed NS=demo`) and
`make mongo-billing-up`; never the live host or Atlas.

    make tp-u2-parity        # -> migration/billing/waves/wave2/U2.customer_parity.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "migration" / "billing" / "loaders"))
sys.path.insert(0, str(ROOT / "services" / "legacy-billing" / "app"))

U1 = ["codes", "tenants", "plans", "subscriptions", "subscriptions_hist"]
U2 = ["customers", "customers_hist"]
ADMIN_TENANT = "a0000000-0000-0000-0000-000000000001"
NO_CUSTOMER_TENANT = "00000000-0000-0000-0000-000000000001"
CLASSES = ("dirty_signup_dt", "malformed_related_acct_ids", "with_attributes", "without_attributes", "clean")


class Fixture:
    def __init__(self, oracle_dsn_env, mongo_uri_env):
        import oracle_to_mongo
        import recon
        from pymongo import MongoClient

        self.loader, self.recon = oracle_to_mongo, recon
        self.oracle_dsn_env, self.mongo_uri_env = oracle_dsn_env, mongo_uri_env
        self.dsn_kw = recon._oracle_kwargs(os.environ[oracle_dsn_env])
        self.oracle_host = recon._dsn_host(self.dsn_kw["dsn"])
        mongo_uri = os.environ[mongo_uri_env]
        if urlparse(mongo_uri).hostname not in recon.LOCAL_HOSTS or self.oracle_host not in recon.LOCAL_HOSTS:
            raise SystemExit("customer parity runs against the local fixtures only, never the live host or Atlas")
        from backends import mongo as mongo_backend

        self.database = mongo_backend.database_name()
        self.mongo = MongoClient(mongo_uri, tz_aware=True, serverSelectionTimeoutMS=10000)
        self.mongo.admin.command("ping")

    def reload(self, report_path: Path) -> dict:
        for name in U1 + U2:
            self.mongo[self.database].drop_collection(name)
        rc = self.loader.main([
            "--mode", "fixture", "--collections", ",".join(U1 + U2), "--passes", "2",
            "--oracle-dsn-env", self.oracle_dsn_env, "--mongo-uri-env", self.mongo_uri_env,
            "--mongo-db", self.database, "--report", str(report_path),
        ])
        if rc != 0:
            raise SystemExit("fixture reload failed")
        return json.loads(report_path.read_text())

    def probe_tenants(self) -> list[dict]:
        """One tenant per anomaly class: the tenant whose first customer (lowest CUST_SEQ_NO) is in the class."""
        import oracledb

        oracledb.defaults.fetch_decimals = True
        with oracledb.connect(**self.dsn_kw) as conn, conn.cursor() as cur:
            cur.execute(
                """SELECT c.tenant_id, c.cust_id, c.signup_dt, c.related_acct_ids,
                          (SELECT COUNT(*) FROM entity_attr_value e
                            WHERE e.entity_type = 'CUSTOMER' AND e.entity_id = c.cust_id) AS attrs
                     FROM customer_master c
                    WHERE c.cust_seq_no = (SELECT MIN(cust_seq_no) FROM customer_master x WHERE x.tenant_id = c.tenant_id)
                      AND c.tenant_id <> :1
                    ORDER BY c.tenant_id""",
                (ADMIN_TENANT,),
            )
            rows = cur.fetchall()
        picked: dict[str, dict] = {}
        for tenant_id, cust_id, signup_dt, related, attrs in rows:
            dirty = signup_dt is not None and self.recon.parse_ddmonyy(signup_dt) is None
            malformed = related not in (None, "") and not self.recon.csv_is_clean(related)
            if dirty:
                cls = "dirty_signup_dt"
            elif malformed:
                cls = "malformed_related_acct_ids"
            elif attrs:
                cls = "with_attributes"
            elif not attrs:
                cls = "without_attributes"
            else:
                cls = "clean"
            picked.setdefault(cls, {"tenant_id": tenant_id, "cust_id": cust_id, "class": cls,
                                    "signup_dt": signup_dt, "related_acct_ids": related, "attributes": int(attrs)})
        tenants = [{"tenant_id": ADMIN_TENANT, "class": "static_admin_customer"}]
        tenants += [picked[c] for c in CLASSES if c in picked]
        tenants.append({"tenant_id": NO_CUSTOMER_TENANT, "class": "no_customer_row"})
        return tenants


def anomaly_rows(fixture, app) -> dict:
    """SELECT * + EAV rows of each planted anomaly customer, rendered by both backends through the app's JSON provider."""
    import oracledb
    from backends import mongo as mongo_backend
    from backends import oracle as oracle_backend

    demo = json.loads((ROOT / "migration" / "billing" / "fixtures" / "demo.json").read_text())
    classes = {a["kind"]: sorted(a["cust_ids"]) for a in demo["anomalies"] if a["kind"] in ("dirty_dates", "malformed_csv_lists")}
    render = lambda body: json.loads(app.json.dumps(body))  # noqa: E731
    out = {"source": "migration/billing/fixtures/demo.json#anomalies cust_ids", "classes": {}, "mismatches": []}
    oracledb.defaults.fetch_decimals = True
    coll = fixture.mongo[fixture.database].customers
    with oracledb.connect(**fixture.dsn_kw) as conn, conn.cursor() as cur:
        for kind, cust_ids in classes.items():
            compared = 0
            for cust_id in cust_ids:
                cur.execute("SELECT * FROM customer_master WHERE cust_id = :1", (cust_id,))
                rows = oracle_backend.rows(cur)
                cur.execute("SELECT * FROM entity_attr_value WHERE entity_type = 'CUSTOMER' AND entity_id = :1 ORDER BY eav_id", (cust_id,))
                expected = render({**rows[0], "attributes": oracle_backend.rows(cur)}) if rows else None
                doc = coll.find_one({"_id": cust_id})
                actual = render({**mongo_backend._customer_row(doc, mongo_backend.CUSTOMER_COLUMNS),
                                 "attributes": mongo_backend._attribute_rows(doc)}) if doc else None
                if expected is None or expected != actual:
                    out["mismatches"].append({"kind": kind, "cust_id": cust_id, "oracle": expected, "mongo": actual})
                compared += 1
            out["classes"][kind] = {"cust_ids": len(cust_ids), "compared": compared}
    out["identical"] = not out["mismatches"]
    return out


def snapshot(client, tenant_id):
    headers = {"X-User-ID": tenant_id, "X-User-Email": f"parity-{tenant_id}@example.invalid"}
    customer = client.get("/api/v1/billing/customer", headers=headers)
    me = client.get("/api/v1/billing/me", query_string={"on": "2026-02-28"}, headers=headers)
    me_body = me.get_json() or {}
    return {
        "GET /api/v1/billing/customer": {"status": customer.status_code, "body": customer.get_json()},
        "GET /api/v1/billing/me .customer": {"status": me.status_code, "customer": me_body.get("customer")},
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--oracle-dsn-env", default="OW_TP_ORACLE_FIXTURE_DSN")
    p.add_argument("--mongo-uri-env", default="OW_TP_MONGO_FIXTURE_URI")
    p.add_argument("--out", default=str(HERE / "U2.customer_parity.json"))
    args = p.parse_args(argv)

    os.environ["MONGODB_ATLAS_URI"] = os.environ[args.mongo_uri_env]  # process-local: the fixture mongod
    os.environ.setdefault("ORACLE_PORT", "52521")
    fixture = Fixture(args.oracle_dsn_env, args.mongo_uri_env)
    from app import app

    out = Path(args.out)
    load = fixture.reload(out.with_suffix(".load.json"))
    tenants = fixture.probe_tenants()
    report = {
        "kind": "customer-parity", "unit": "U2", "run_mode": "fixture", "merge_evidence": False,
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": {"oracle": f"local fixture {fixture.oracle_host}", "mongo": f"local fixture, database {fixture.database}"},
        "reference": "BILLING_BACKEND=oracle response (facade-side SQL; U2 has no PL/SQL entrypoint or procs transcript)",
        "fixture_load": {"collections": load["collections"], "rerun_noop": load["rerun_noop"],
                         "customers": load["passes"][0]["collections"]["customers"],
                         "customers_hist": load["passes"][0]["collections"]["customers_hist"]},
        "tenants": [], "verdict": "pass",
    }
    for tenant in tenants:
        entry = dict(tenant)
        for backend in ("oracle", "mongo"):
            os.environ["BILLING_BACKEND"] = backend
            entry[backend] = snapshot(app.test_client(), tenant["tenant_id"])
        oracle, mongo = entry["oracle"], entry["mongo"]
        entry["customer_identical"] = oracle["GET /api/v1/billing/customer"] == mongo["GET /api/v1/billing/customer"]
        entry["me_customer_identical"] = oracle["GET /api/v1/billing/me .customer"] == mongo["GET /api/v1/billing/me .customer"]
        body = oracle["GET /api/v1/billing/customer"]["body"] or {}
        entry["fields_compared"] = len(body) + sum(len(a) for a in body.get("attributes", []) or [])
        entry["pass"] = entry["customer_identical"] and entry["me_customer_identical"]
        if not entry["pass"]:
            report["verdict"] = "fail"
        report["tenants"].append(entry)
        print(f"{tenant['class']:28s} {tenant['tenant_id']}: /customer {oracle['GET /api/v1/billing/customer']['status']} "
              f"{'identical' if entry['customer_identical'] else 'MISMATCH'}, /me.customer "
              f"{'identical' if entry['me_customer_identical'] else 'MISMATCH'} ({entry['fields_compared']} fields)")
    report["classes_covered"] = sorted({t["class"] for t in tenants})
    report["anomaly_rows"] = anomaly_rows(fixture, app)
    if not report["anomaly_rows"]["identical"]:
        report["verdict"] = "fail"
    print("anomaly rows rendered identically on both backends: "
          + ", ".join(f"{k} {v['compared']}/{v['cust_ids']}" for k, v in report["anomaly_rows"]["classes"].items())
          + f" -> {report['anomaly_rows']['identical']}")
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(f"customer parity {report['verdict']} ({len(tenants)} tenants, both backends) -> {out}")
    return 0 if report["verdict"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
