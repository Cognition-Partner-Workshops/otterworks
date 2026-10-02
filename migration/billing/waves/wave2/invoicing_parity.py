#!/usr/bin/env python3
"""U4 route parity: invoicing module on BILLING_BACKEND=oracle vs BILLING_BACKEND=mongo.

Replays procs/scenarios/invoicing/001-006.yaml (fn_invoice_preview, sp_issue_invoice,
fn_invoice_lines) through the legacy-billing Flask app in-process, once per backend, and grades
both against the immutable transcripts procs/transcripts/invoicing/INVOICE-00N.json (business
fields + state probes). Before every scenario the Oracle fixture's invoicing rows of the static
tenants are reset to the checked-in seed (03_seed_static.sql: invoices, invoice_lines,
rating_periods, rating_results, credit_notes restored in place, rows the scenarios issued
deleted) and the Mongo fixture's invoicing collections are reloaded from it with
migration/billing/loaders/oracle_to_mongo.py, so both backends start from the same rows.

Three more sections record, on both backends, the /api/v1/billing invoice routes (list, owned
lines, foreign invoice -> 404), the admin month-end / reconciliation reports (same rollups to
the cent; mongo source.engine=mongodb and status=pass), and the CUSTBILL month-end extract
(byte-identical CUSTBILL_<NS>_ORACLE.dat, sha256 on both sides).

Fixture only: requires `make oracle-billing-up` (seeded) and `make mongo-billing-up`; never Atlas.

    make tp-u4-parity        # -> migration/billing/waves/wave2/U4.invoicing_parity.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import tempfile
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from urllib.parse import urlparse

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "procs" / "harness"))
sys.path.insert(0, str(ROOT / "migration" / "billing" / "loaders"))
sys.path.insert(0, str(ROOT / "services" / "legacy-billing" / "app"))
sys.path.insert(0, str(ROOT / "etl" / "legacy-extra" / "tools"))

SCENARIOS = ROOT / "procs" / "scenarios" / "invoicing"
TRANSCRIPTS = ROOT / "procs" / "transcripts" / "invoicing"
U4 = ["credit_notes", "invoice_feed", "invoice_feed_quarantine", "invoices"]
READ_DEPENDENCIES = ["codes", "tenants", "plans", "subscriptions", "subscriptions_hist", "usage_events", "rating_periods", "customers"]
RESET_COLLECTIONS = ["rating_periods", "invoices", "credit_notes"]
SEED_TABLES = {"invoices": "tenant_id", "invoice_lines": None, "rating_periods": "tenant_id", "rating_results": None, "credit_notes": "tenant_id"}
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0", ""}
INVOICED_TENANT = "00000000-0000-0000-0000-000000000002"
FOREIGN_TENANT = "00000000-0000-0000-0000-000000000006"
SEEDED_INVOICE = "60000000-0000-0000-0000-000000000001"
NS = "demo"


def md5_uuid(text):
    h = hashlib.md5(text.encode()).hexdigest()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"


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
        if spec.get("collect"):
            out[spec["name"]] = [normalize(r.get(spec["from"]), spec.get("type")) for r in rows]
        else:
            out[spec["name"]] = normalize(rows[0].get(spec["from"]), spec.get("type")) if rows else None
    return out


def _iso(value):
    if value is None:
        return None
    return value.date().isoformat() if isinstance(value, dt.datetime) else str(value)[:10]


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
            raise SystemExit("invoicing parity runs against the local fixtures only, never the live host or Atlas")
        from backends import mongo as mongo_backend

        self.database = mongo_backend.database_name()
        self.mongo = MongoClient(mongo_uri, tz_aware=True, serverSelectionTimeoutMS=10000)
        self.mongo.admin.command("ping")
        self.dsn_kw = kw
        self.seed = self._seed_rows()

    def _seed_rows(self):
        """03_seed_static.sql rows of the invoicing tables, keyed by table -> [(cols, vals)]."""
        seed = {t: [] for t in SEED_TABLES}
        for statement in self.oracle_record.seed_statements():
            m = re.match(r"INSERT INTO (\w+) \(([^)]*)\) VALUES \((.*)\)$", statement, re.I | re.S)
            if not m or m.group(1).lower() not in seed:
                continue
            cols = [c.strip() for c in m.group(2).split(",")]
            vals = [v.strip() for v in re.split(r",(?=(?:[^']*'[^']*')*[^']*$)", m.group(3))]
            seed[m.group(1).lower()].append((cols, vals))
        return seed

    def load(self, names):
        for name in names:
            self.mongo[self.database].drop_collection(name)
        rc = self.loader.main([
            "--mode", "fixture", "--collections", ",".join(names),
            "--oracle-dsn-env", self.oracle_dsn_env, "--mongo-uri-env", self.mongo_uri_env,
            "--mongo-db", self.database,
        ])
        if rc != 0:
            raise SystemExit("fixture reload failed")

    def reset(self):
        """Invoicing baseline for the static tenants: rows the scenarios issued are deleted, the
        seeded invoices / lines / rating periods / results / credit notes are restored in place."""
        import oracledb

        ids = ", ".join(f"'{t}'" for t in self.oracle_record.STATIC_TENANTS)
        seed_ids = {t: [vals[cols.index("id")] for cols, vals in rows] for t, rows in self.seed.items()}

        def not_seeded(table):
            return f"id NOT IN ({', '.join(seed_ids[table])})" if seed_ids[table] else "1 = 1"

        deletes = [
            f"DELETE FROM invoice_lines WHERE invoice_id IN (SELECT id FROM invoices WHERE tenant_id IN ({ids}) AND {not_seeded('invoices')})",
            f"DELETE FROM invoice_lines WHERE invoice_id IN (SELECT id FROM invoices WHERE tenant_id IN ({ids})) AND {not_seeded('invoice_lines')}",
            f"DELETE FROM invoices WHERE tenant_id IN ({ids}) AND {not_seeded('invoices')}",
            f"DELETE FROM rating_results WHERE period_id IN (SELECT id FROM rating_periods WHERE tenant_id IN ({ids}) AND {not_seeded('rating_periods')})",
            f"DELETE FROM rating_results WHERE period_id IN (SELECT id FROM rating_periods WHERE tenant_id IN ({ids})) AND {not_seeded('rating_results')}",
            f"DELETE FROM rating_periods WHERE tenant_id IN ({ids}) AND {not_seeded('rating_periods')} AND id NOT IN (SELECT period_id FROM invoices)",
            f"DELETE FROM credit_notes WHERE tenant_id IN ({ids}) AND {not_seeded('credit_notes')}",
        ]
        merges = []
        for table in ("rating_periods", "rating_results", "invoices", "invoice_lines", "credit_notes"):
            for cols, vals in self.seed[table]:
                using = ", ".join(f"{v} AS {c}" for c, v in zip(cols, vals))
                sets = ", ".join(f"s.{c} = x.{c}" for c in cols if c != "id")
                changed = " + ".join(f"DECODE(s.{c}, x.{c}, 0, 1)" for c in cols if c != "id")
                merges.append(
                    f"MERGE INTO {table} s USING (SELECT {using} FROM dual) x ON (s.id = x.id) "
                    f"WHEN MATCHED THEN UPDATE SET {sets} WHERE {changed} > 0 "
                    f"WHEN NOT MATCHED THEN INSERT ({', '.join(cols)}) VALUES ({', '.join('x.' + c for c in cols)})"
                )
        with oracledb.connect(**self.dsn_kw) as conn, conn.cursor() as cur:
            for statement in deletes + merges:
                cur.execute(statement)
            conn.commit()
        self.load(RESET_COLLECTIONS)

    # ---- state probes (same shape on both estates)

    def credit_rows(self, backend, tenant_id):
        if backend == "oracle":
            rows = self.oracle_query(
                "SELECT id, issued_on, remaining_amount FROM credit_notes WHERE tenant_id = :1 ORDER BY issued_on, id",
                (tenant_id,))
            return [{"id": r[0], "issued_on": _iso(r[1]), "remaining_amount": r[2]} for r in rows]
        return [
            {"id": d["_id"], "issued_on": _iso(d.get("issuedOn")), "remaining_amount": d.get("remainingAmount")}
            for d in self.mongo[self.database].credit_notes.find({"tenantId": tenant_id}, sort=[("issuedOn", 1), ("_id", 1)])
        ]

    def invoice_rows(self, backend, tenant_id, period_start):
        period_id = md5_uuid(f"{tenant_id}{period_start}")
        if backend == "oracle":
            rows = self.oracle_query(
                """SELECT c.code_desc, i.subtotal, i.tax, i.total FROM invoices i
                     LEFT JOIN codes c ON c.code_type = 'INV_STATUS' AND c.code_val = i.status_cd
                    WHERE i.period_id = :1 ORDER BY i.id""", (period_id,))
            return [{"status": r[0], "subtotal": r[1], "tax": r[2], "total": r[3]} for r in rows]
        db = self.mongo[self.database]
        codes = {c["_id"]["codeVal"]: c.get("codeDesc") for c in db.codes.find({"_id.codeType": "INV_STATUS"})}
        return [
            {"status": codes.get(d.get("statusCd")), "subtotal": d.get("subtotal"), "tax": d.get("tax"), "total": d.get("total")}
            for d in db.invoices.find({"periodId": period_id}, sort=[("_id", 1)])
        ]

    def oracle_query(self, sql, params):
        with self.oracle_connection() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    def oracle_connection(self):
        """Probe connection: NUMBER columns as Decimal (the app's own connections are left alone)."""
        import oracledb

        def decimals(cursor, metadata):
            if metadata.type is oracledb.DB_TYPE_NUMBER:
                return cursor.var(oracledb.DB_TYPE_NUMBER, arraysize=cursor.arraysize,
                                  outconverter=lambda v: Decimal(v) if v is not None else None, convert_nulls=True)
            return None

        conn = oracledb.connect(**self.dsn_kw)
        conn.outputtypehandler = decimals
        return conn


def run_scenario(client, fixture, backend, scenario):
    inputs = {i["name"]: i["value"] for i in scenario.get("inputs", [])}
    entry = scenario["entrypoint"]
    if entry == "billing.fn_invoice_preview":
        rows = client.get(f"/api/invoices/{inputs['tenant_id']}/preview",
                          query_string={"period_start": inputs["period_start"], "period_end": inputs["period_end"]}).get_json()
    elif entry == "billing.fn_invoice_lines":
        rows = client.get(f"/api/invoices/{inputs['invoice_id']}/lines").get_json()
    elif entry == "billing.sp_issue_invoice":
        resp = client.post(f"/api/invoices/{inputs['tenant_id']}/issue",
                           data={"period_start": inputs["period_start"], "period_end": inputs["period_end"]})
        if resp.status_code != 200:
            raise RuntimeError(f"{scenario['id']} on {backend}: HTTP {resp.status_code}")
        if "credit_notes" in scenario["capture_query"]:
            rows = fixture.credit_rows(backend, inputs["tenant_id"])
        else:
            rows = fixture.invoice_rows(backend, inputs["tenant_id"], inputs["period_start"])
    else:
        raise RuntimeError(f"unknown entrypoint {entry}")
    fields = capture(rows, scenario["fields"])
    probes = {}
    for probe in scenario.get("probes", []):
        state = fixture.invoice_rows(backend, inputs["tenant_id"], inputs["period_start"])
        probes[probe["id"]] = [{k: normalize(v, None if k == "status" else "decimal") for k, v in row.items()} for row in state]
    return fields, probes


def facade_snapshot(client):
    headers = {"X-User-ID": INVOICED_TENANT, "X-User-Email": "tenant-two@example.com"}
    foreign = {"X-User-ID": FOREIGN_TENANT, "X-User-Email": "tenant-six@example.com"}
    listing = client.get("/api/v1/billing/invoices", headers=headers)
    owned = client.get(f"/api/v1/billing/invoices/{SEEDED_INVOICE}/lines", headers=headers)
    not_owned = client.get(f"/api/v1/billing/invoices/{SEEDED_INVOICE}/lines", headers=foreign)
    return {
        "GET /api/v1/billing/invoices (tenant 2)": {"status": listing.status_code, "body": listing.get_json()},
        f"GET /api/v1/billing/invoices/{SEEDED_INVOICE}/lines (owner)": {"status": owned.status_code, "body": owned.get_json()},
        f"GET /api/v1/billing/invoices/{SEEDED_INVOICE}/lines (tenant 6, not owner)": {"status": not_owned.status_code, "body": not_owned.get_json()},
    }


def reports_snapshot(client):
    headers = {"X-User-ID": "admin", "X-User-Roles": "ADMIN"}
    month_end = client.get("/api/v1/billing/admin/reports/month-end", query_string={"ns": NS}, headers=headers).get_json()
    recon = client.get("/api/v1/billing/admin/reports/reconciliation", query_string={"ns": NS}, headers=headers).get_json()
    return {"month_end": month_end, "reconciliation": recon}


COUNT_FIELDS = {"invoice_count", "line_count", "invoices_touched", "customer_count"}


def _counts_as_int(row):
    """The Oracle report serves its COUNT(*) columns through oracle_conn's fetch_decimals=True (so
    they render as "5504"); the contract and the Mongo report carry them as integers. Compare the
    numbers, not the rendering."""
    return {k: int(v) if k in COUNT_FIELDS and v is not None else v for k, v in row.items()}


def report_rollups(snapshot):
    """The parts of both reports that must be identical to the cent across backends."""
    me, rc = snapshot["month_end"], snapshot["reconciliation"]
    return {
        "namespace": me.get("namespace"), "batch_no": me.get("batch_no"), "report": me.get("report"),
        "by_status": [_counts_as_int(r) for r in me.get("by_status") or []],
        "by_status_line_type": [_counts_as_int(r) for r in me.get("by_status_line_type") or []],
        "balances": _counts_as_int(rc.get("balances") or {}),
    }


def custbill_extract(fixture, backend):
    import oracle_custbill_extract as extractor

    out_dir = Path(tempfile.mkdtemp(prefix=f"custbill-{backend}-"))
    if backend == "oracle":
        destination, count = extractor.extract(NS, out_dir, connection=fixture.oracle_connection())
    else:
        destination, count = extractor.extract(NS, out_dir, database=fixture.mongo[fixture.database])
    data = destination.read_bytes()
    return {"file": destination.name, "records": count, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "path": str(destination)}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--oracle-dsn-env", default="OW_TP_ORACLE_FIXTURE_DSN")
    p.add_argument("--mongo-uri-env", default="OW_TP_MONGO_FIXTURE_URI")
    p.add_argument("--out", default=str(HERE / "U4.invoicing_parity.json"))
    args = p.parse_args(argv)

    os.environ["MONGODB_ATLAS_URI"] = os.environ[args.mongo_uri_env]  # process-local: the fixture mongod
    os.environ.setdefault("ORACLE_PORT", "52521")
    fixture = Fixture(args.oracle_dsn_env, args.mongo_uri_env)
    from app import app

    fixture.load(READ_DEPENDENCIES + U4)
    scenarios = [yaml.safe_load(path.read_text()) for path in sorted(SCENARIOS.glob("*.yaml"))]
    report = {
        "kind": "invoicing-parity", "unit": "U4", "run_mode": "fixture", "merge_evidence": False,
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": {"oracle": f"local fixture {fixture.oracle_host}", "mongo": f"local fixture, database {fixture.database}"},
        "transcripts": "procs/transcripts/invoicing/INVOICE-001..006.json (immutable)",
        "scenarios": [], "facade": {}, "reports": {}, "custbill": {}, "verdict": "pass",
    }
    for scenario in scenarios:
        transcript = json.loads((TRANSCRIPTS / f"{scenario['id']}.json").read_text())
        entry = {"id": scenario["id"], "entrypoint": scenario["entrypoint"], "description": scenario["description"],
                 "expected": {"business_fields": transcript["business_fields"], "probes": transcript["probes"]}, "backends": {}}
        for backend in ("oracle", "mongo"):
            fixture.reset()
            os.environ["BILLING_BACKEND"] = backend
            fields, probes = run_scenario(app.test_client(), fixture, backend, scenario)
            entry["backends"][backend] = {
                "business_fields": fields, "probes": probes,
                "fields_match": fields == transcript["business_fields"], "probes_match": probes == transcript["probes"],
            }
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
        report["reports"][backend] = reports_snapshot(app.test_client())
        report["custbill"][backend] = custbill_extract(fixture, backend)
    report["facade"]["identical"] = report["facade"]["oracle"] == report["facade"]["mongo"]
    report["facade"]["foreign_invoice_404_on_both"] = all(
        snap[f"GET /api/v1/billing/invoices/{SEEDED_INVOICE}/lines (tenant 6, not owner)"]["status"] == 404
        for snap in (report["facade"]["oracle"], report["facade"]["mongo"]))
    rollups = {b: report_rollups(report["reports"][b]) for b in ("oracle", "mongo")}
    report["reports"]["rollups_identical"] = rollups["oracle"] == rollups["mongo"]
    report["reports"]["engines"] = {b: report["reports"][b]["month_end"].get("source", {}).get("engine") for b in ("oracle", "mongo")}
    report["reports"]["reconciliation_status"] = {b: report["reports"][b]["reconciliation"].get("status") for b in ("oracle", "mongo")}
    report["reports"]["contract"] = (
        report["reports"]["rollups_identical"]
        and report["reports"]["engines"] == {"oracle": "oracle", "mongo": "mongodb"}
        and report["reports"]["reconciliation_status"] == {"oracle": "baseline", "mongo": "pass"}
    )
    report["custbill"]["byte_identical"] = (
        report["custbill"]["oracle"]["sha256"] == report["custbill"]["mongo"]["sha256"]
        and report["custbill"]["oracle"]["bytes"] == report["custbill"]["mongo"]["bytes"] > 0
    )
    if not (report["facade"]["identical"] and report["facade"]["foreign_invoice_404_on_both"]
            and report["reports"]["contract"] and report["custbill"]["byte_identical"]):
        report["verdict"] = "fail"
    print(f"facade invoice routes identical on both backends: {report['facade']['identical']}; "
          f"foreign invoice 404 on both: {report['facade']['foreign_invoice_404_on_both']}")
    print(f"admin reports: rollups identical={report['reports']['rollups_identical']} engines={report['reports']['engines']} "
          f"reconciliation={report['reports']['reconciliation_status']}")
    print(f"CUSTBILL_{NS.upper()}: oracle sha256={report['custbill']['oracle']['sha256'][:16]}.. ({report['custbill']['oracle']['bytes']} bytes) "
          f"mongo sha256={report['custbill']['mongo']['sha256'][:16]}.. ({report['custbill']['mongo']['bytes']} bytes) "
          f"byte-identical={report['custbill']['byte_identical']}")
    fixture.reset()

    out = Path(args.out)
    out.write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(f"invoicing parity {report['verdict']} -> {out}")
    return 0 if report["verdict"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
