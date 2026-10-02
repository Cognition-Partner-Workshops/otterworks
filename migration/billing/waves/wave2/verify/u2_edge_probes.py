#!/usr/bin/env python3
"""UNT-22 edge-case probes for U2 (customers: CUSTOMER_MASTER + embedded ENTITY_ATTR_VALUE, CUSTOMER_MASTER_HIST)
on the local fixtures only. Drives the Oracle backend (facade-side SQL + TRG_CUSTOMER_MASTER_* on the Oracle Free
fixture) and the Mongo backend (its port on a loopback mongod, reloaded from the Oracle fixture by the batch's own
loader) through the same inputs past customer_parity.py: empty / unknown tenants, planted dirty-date and malformed-CSV
rows served through the facade (not just the row renderer), trigger-written customer_master_hist pre-images carried
by the loader and recon'd locally, the Mongo update_customer pre-image shape against the trigger's, atomicity of the
pre-image + update transaction, NUMBER(14,2) money edges, non-CUSTOMER / orphan EAV rows at the loader, EAV ordering
and case-variant names, the BEFORE INSERT trigger's derivations, quarantine (n/a for U2) and the write scope.

    TZ=UTC LC_ALL=C OW_TP_ORACLE_FIXTURE_DSN=... OW_TP_MONGO_FIXTURE_URI=... \
      uv run --no-project --with oracledb==2.5.1 --with pymongo==4.10.1 --with flask==3.1.1 \
        --with pyyaml==6.0.2 --with jsonschema==4.25.1 --with rfc3339-validator==0.1.4 \
        python3 migration/billing/waves/wave2/verify/u2_edge_probes.py --repo-root <PR checkout>

Refuses non-loopback hosts on either side (via customer_parity.Fixture). Fixture evidence only, never merge evidence.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
U2 = ["customers", "customers_hist"]
EMPTY_TENANT = "e0000000-0000-0000-0000-0000000000e1"
NEW_TENANT = "e0000000-0000-0000-0000-0000000000e2"
EDGE_CUST = "e0000000-0000-0000-0000-0000000000c1"
HIST_DT_RE = re.compile(r"^\d{2}-[A-Z]{3}-\d{2} \d{2}:\d{2}:\d{2}$")
MONEY = {"cur_bal_amt": "0.01", "past_due_amt": "-0.01", "credit_limit_amt": "999999999999.99",
         "ytd_billed_amt": "1234567890.1", "ltd_billed_amt": "0", "ytd_paid_amt": None}
HIST_META = {"_id", "histDt", "histOp", "custId", "histDate"}


def setup_paths(root: Path):
    for rel in (("migration", "billing", "loaders"), ("migration", "billing", "recon"),
                ("migration", "billing", "waves", "wave2"), ("services", "legacy-billing", "app")):
        sys.path.insert(0, str(root.joinpath(*rel)))


def jsonable(value):
    return json.loads(json.dumps(value, default=str))


class Probes:
    def __init__(self, root: Path, oracle_dsn_env: str, mongo_uri_env: str):
        import customer_parity
        import oracledb
        from backends import mongo as mongo_backend
        from backends import oracle as oracle_backend
        from app import app

        oracledb.defaults.fetch_decimals = True
        self.root, self.oracledb = root, oracledb
        self.fixture = customer_parity.Fixture(oracle_dsn_env, mongo_uri_env)
        self.parity = customer_parity
        self.oracle_dsn_env, self.mongo_uri_env = oracle_dsn_env, mongo_uri_env
        self.backends = {"oracle": oracle_backend, "mongo": mongo_backend}
        self.app = app
        self.mdb = self.fixture.mongo[self.fixture.database]
        self.demo = json.loads((root / "migration" / "billing" / "fixtures" / "demo.json").read_text())
        self.results = []

    # ---- fixture helpers -------------------------------------------------------------
    def oracle(self, statements, fetch=None, binds=()):
        with self.oracledb.connect(**self.fixture.dsn_kw) as conn, conn.cursor() as cur:
            for stmt in statements:
                cur.execute(stmt)
            out = None
            if fetch:
                cur.execute(fetch, binds)
                out = cur.fetchall()
            conn.commit()
            return out

    def reload(self, collections, mongo_db=None):
        """The batch's own loader, fixture mode, into the fixture database (or a scratch one). Returns the exit code."""
        db = mongo_db or self.fixture.database
        for name in collections:
            self.fixture.mongo[db].drop_collection(name)
        try:
            return self.fixture.loader.main([
                "--mode", "fixture", "--collections", ",".join(collections),
                "--oracle-dsn-env", self.oracle_dsn_env, "--mongo-uri-env", self.mongo_uri_env, "--mongo-db", db])
        except SystemExit as exc:
            return exc.code if isinstance(exc.code, int) else 1

    def use(self, backend):
        os.environ["BILLING_BACKEND"] = backend
        return self.backends[backend], self.app.test_client()

    def routes(self, tenant_id):
        out = {}
        for name in ("oracle", "mongo"):
            _backend, client = self.use(name)
            out[name] = self.parity.snapshot(client, tenant_id)
        return out

    def oracle_customer(self, cust_id):
        with self.oracledb.connect(**self.fixture.dsn_kw) as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM customer_master WHERE cust_id = :1", (cust_id,))
            rows = self.backends["oracle"].rows(cur)
        return rows[0] if rows else None

    def tenant_of(self, cust_id):
        return self.oracle([], fetch="SELECT tenant_id, cust_seq_no FROM customer_master WHERE cust_id = :1", binds=(cust_id,))[0]

    def hist_rows(self, since_hist_id):
        got = self.oracle([], fetch="SELECT hist_id, hist_op, cust_id, cust_seq_no, hist_dt FROM customer_master_hist "
                                    "WHERE hist_id > :1 ORDER BY hist_id", binds=(since_hist_id,))
        return [{"hist_id": int(r[0]), "hist_op": r[1], "cust_id": r[2], "cust_seq_no": str(r[3]), "hist_dt_format_ok": bool(HIST_DT_RE.match(r[4] or ""))} for r in got]

    def counts(self, db=None):
        d = self.fixture.mongo[db or self.fixture.database]
        return {name: d[name].count_documents({}) for name in sorted(d.list_collection_names())}

    def record(self, pid, description, per_backend, passed, notes=None, **extra):
        entry = {"id": pid, "description": description, "backends": jsonable(per_backend), "pass": bool(passed)}
        if notes:
            entry["notes"] = notes
        entry.update(extra)
        self.results.append(entry)
        print(f"{pid}: {'pass' if passed else 'FAIL'} - {description}")
        return entry

    # ---- probes --------------------------------------------------------------------------
    def probe_empty_and_unknown_tenant(self):
        self.oracle([f"INSERT INTO tenants (id, name, tax_exempt_yn, status_cd) VALUES ('{EMPTY_TENANT}', 'Edge Empty Tenant', 'N', 10)"])
        self.reload(["tenants"])
        out = {}
        try:
            for name in ("oracle", "mongo"):
                backend, client = self.use(name)
                out[name] = {
                    "existing tenant, no customer_master row": self.parity.snapshot(client, EMPTY_TENANT),
                    "customer_summary()": backend.customer_summary(EMPTY_TENANT),
                    "customer()": backend.customer(EMPTY_TENANT),
                    "unknown identity (bootstrapped by _ensure)": self.parity.snapshot(client, NEW_TENANT),
                }
                if name == "oracle":
                    out[name]["rows_after"] = {
                        "customer_master": int(self.oracle([], fetch=f"SELECT COUNT(*) FROM customer_master WHERE tenant_id IN ('{EMPTY_TENANT}', '{NEW_TENANT}')")[0][0]),
                        "subscriptions(new)": int(self.oracle([], fetch=f"SELECT COUNT(*) FROM subscriptions WHERE tenant_id = '{NEW_TENANT}'")[0][0]),
                        "subscriptions(empty)": int(self.oracle([], fetch=f"SELECT COUNT(*) FROM subscriptions WHERE tenant_id = '{EMPTY_TENANT}'")[0][0]),
                    }
                    self.oracle([f"DELETE FROM subscriptions WHERE tenant_id = '{NEW_TENANT}'",
                                 f"DELETE FROM subscriptions_hist WHERE tenant_id = '{NEW_TENANT}'",
                                 f"DELETE FROM tenants WHERE id = '{NEW_TENANT}'"])
                else:
                    out[name]["rows_after"] = {
                        "customer_master": self.mdb.customers.count_documents({"tenantId": {"$in": [EMPTY_TENANT, NEW_TENANT]}}),
                        "subscriptions(new)": self.mdb.subscriptions.count_documents({"tenantId": NEW_TENANT}),
                        "subscriptions(empty)": self.mdb.subscriptions.count_documents({"tenantId": EMPTY_TENANT}),
                    }
            m = out["mongo"]
            ok = (out["oracle"] == out["mongo"]
                  and m["existing tenant, no customer_master row"]["GET /api/v1/billing/customer"]["status"] == 404
                  and m["existing tenant, no customer_master row"]["GET /api/v1/billing/me .customer"] == {"status": 200, "customer": None}
                  and m["unknown identity (bootstrapped by _ensure)"]["GET /api/v1/billing/customer"]["status"] == 404
                  and m["customer()"] is None and m["customer_summary()"] is None
                  and m["rows_after"]["customer_master"] == 0)
            self.record("EDGE-U2-001", "tenant without a customer_master row and an unknown identity: /customer 404 and /me.customer null on both; "
                        "neither backend bootstraps a customer (U1's _ensure bootstrap of tenant+subscription is identical)", out, ok)
        finally:
            self.oracle([f"DELETE FROM subscriptions WHERE tenant_id IN ('{EMPTY_TENANT}', '{NEW_TENANT}')",
                         f"DELETE FROM subscriptions_hist WHERE tenant_id IN ('{EMPTY_TENANT}', '{NEW_TENANT}')",
                         f"DELETE FROM tenants WHERE id IN ('{EMPTY_TENANT}', '{NEW_TENANT}')"])
            for name in ("tenants", "subscriptions", "subscriptions_hist", "customers"):
                self.mdb[name].delete_many({"$or": [{"_id": {"$in": [EMPTY_TENANT, NEW_TENANT]}}, {"tenantId": {"$in": [EMPTY_TENANT, NEW_TENANT]}}]})

    def _planted(self, kind):
        return sorted(next(a for a in self.demo["anomalies"] if a["kind"] == kind)["cust_ids"])

    def probe_anomalies_through_facade(self):
        """Make one planted dirty-date and one planted malformed-CSV customer the tenant's first customer
        (cust_seq_no = -1, so the facade's ORDER BY cust_seq_no FETCH FIRST 1 serves it) and compare the routes."""
        recon = self.fixture.recon
        self.hist0 = int(self.oracle([], fetch="SELECT NVL(MAX(hist_id), 0) FROM customer_master_hist")[0][0] or 0)
        self.moved = {}
        for kind in ("dirty_dates", "malformed_csv_lists"):
            cust_id = self._planted(kind)[0]
            tenant_id, seq = self.tenant_of(cust_id)
            self.moved[kind] = {"cust_id": cust_id, "tenant_id": tenant_id, "cust_seq_no": seq}
            self.oracle(["UPDATE customer_master SET cust_seq_no = -1 WHERE cust_id = :1".replace(":1", f"'{cust_id}'")])
        self.reload(U2)
        out, ok = {}, True
        for kind, m in self.moved.items():
            routes = self.routes(m["tenant_id"])
            body = routes["oracle"]["GET /api/v1/billing/customer"]["body"] or {}
            doc = self.mdb.customers.find_one({"_id": m["cust_id"]}) or {}
            detail = {
                "routes_identical": routes["oracle"] == routes["mongo"],
                "served_cust_id": body.get("cust_id"),
                "signup_dt": body.get("signup_dt"), "signup_dt_parses": recon.parse_ddmonyy(body.get("signup_dt")) is not None,
                "related_acct_ids": body.get("related_acct_ids"),
                "related_acct_ids_clean": recon.csv_is_clean(body.get("related_acct_ids")) if body.get("related_acct_ids") else None,
                "typed_siblings_in_body": sorted({"signup_date", "signupDate", "related_acct_ids_list", "relatedAcctIdsList", "_id"} & set(body)),
                "mongo_doc_siblings": {"signupDate": doc.get("signupDate"), "relatedAcctIdsList": doc.get("relatedAcctIdsList")},
                "mongo": routes["mongo"],
            }
            if kind == "dirty_dates":
                expect = detail["served_cust_id"] == m["cust_id"] and not detail["signup_dt_parses"] and detail["mongo_doc_siblings"]["signupDate"] is None
            else:
                expect = detail["served_cust_id"] == m["cust_id"] and detail["related_acct_ids_clean"] is False and detail["mongo_doc_siblings"]["relatedAcctIdsList"] is None
            ok = ok and detail["routes_identical"] and expect and not detail["typed_siblings_in_body"]
            out[kind] = detail
        self.record("EDGE-U2-002", "planted dirty SIGNUP_DT and malformed RELATED_ACCT_IDS customers served through GET /customer and /me.customer: "
                    "verbatim text on both backends, no typed sibling surfaces, derived sibling is null in the document", out, ok,
                    moved=self.moved)

    def probe_trigger_hist_carried(self, out_path: Path):
        """The two cust_seq_no UPDATEs above fired TRG_CUSTOMER_MASTER_HIST; the loader carried the pre-images."""
        oracle_hist = self.hist_rows(self.hist0)
        mongo_hist = []
        for d in self.mdb.customers_hist.find({"_id": {"$gt": self.hist0}}).sort("_id", 1):
            mongo_hist.append({
                "hist_id": int(d["_id"]), "hist_op": d.get("histOp"), "cust_id": d.get("custId"), "cust_seq_no": str(d.get("custSeqNo")),
                "hist_dt_format_ok": bool(HIST_DT_RE.match(d.get("histDt") or "")),
                "hist_date_derived_from_hist_dt": d.get("histDate") is not None and self.backends["mongo"].f_str2dt(d["histDt"]) == d["histDate"].date(),
                "attributes_absent": "attributes" not in d,
                "pre_image_cust_seq_no_is_old_value": str(d.get("custSeqNo")) == str(next((m["cust_seq_no"] for m in self.moved.values() if m["cust_id"] == d.get("custId")), None)),
            })
        cmd = [sys.executable, str(self.root / "migration/billing/recon/recon.py"), "run", "--mode", "local",
               "--collections", ",".join(U2), "--oracle-dsn-env", self.oracle_dsn_env, "--mongo-uri-env", self.mongo_uri_env,
               "--mongo-db", self.fixture.database, "--out", str(out_path)]
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=self.root)
        report = json.loads(out_path.read_text()) if out_path.exists() else {}
        hist_checks = [c for c in report.get("checks", []) if "customers_hist" in c.get("id", "") or c.get("collection") == "customers_hist"]
        local = {"exit": proc.returncode, "stdout": proc.stdout.strip().splitlines()[-2:], "stderr": proc.stderr.strip().splitlines()[-2:],
                 "verdict": report.get("verdict"), "run_mode": report.get("run_mode"), "merge_evidence": report.get("merge_evidence"),
                 "failed": [c["id"] for c in report.get("checks", []) if c.get("result") not in ("pass", None)],
                 "customers_hist_checks": [c["id"] for c in hist_checks]}
        stripped = [{k: v for k, v in r.items()} for r in mongo_hist]
        for r in stripped:
            for k in ("hist_date_derived_from_hist_dt", "attributes_absent", "pre_image_cust_seq_no_is_old_value"):
                r.pop(k)
        ok = (len(oracle_hist) == 2 and oracle_hist == stripped and all(r["hist_op"] == "UPD" for r in oracle_hist)
              and all(r["hist_date_derived_from_hist_dt"] and r["attributes_absent"] and r["pre_image_cust_seq_no_is_old_value"] for r in mongo_hist)
              and proc.returncode == 0 and report.get("verdict") == "pass" and report.get("merge_evidence") is False and hist_checks)
        self.record("EDGE-U2-003", "TRG_CUSTOMER_MASTER_HIST pre-images (UPD) written by the Oracle fixture are carried by the loader with histDate "
                    "derived from the DD-MON-YY HH24:MI:SS histDt, no attributes; recon.py --mode local over customers,customers_hist passes with hist rows present "
                    "(live has 0)", {"oracle": oracle_hist, "mongo": mongo_hist, "local_recon": local}, ok, report_path=str(out_path))

    def probe_update_customer_pre_image_shape(self):
        mongo = self.backends["mongo"]
        cust_id = self.moved["dirty_dates"]["cust_id"]
        loaded = self.mdb.customers_hist.find_one({"custId": cust_id, "_id": {"$gt": self.hist0}})
        before = self.mdb.customers.find_one({"_id": cust_id})
        last_id = int(mongo._next_id(self.mdb.customers_hist)) - 1
        updated = mongo.update_customer(cust_id, {"contactNotes": "edge probe pre-image"})
        written = self.mdb.customers_hist.find_one({"_id": last_id + 1})
        out = {
            "trigger_pre_image_keys_minus_mongo": sorted(set(loaded) - set(written or {})),
            "mongo_pre_image_keys_minus_trigger": sorted(set(written or {}) - set(loaded)),
            "written": {"_id": written and written["_id"], "histOp": written and written.get("histOp"), "custId": written and written.get("custId"),
                        "histDt_format_ok": bool(written and HIST_DT_RE.match(written.get("histDt") or "")),
                        "histDate_derived": bool(written and written.get("histDate") == mongo._as_bson_date(mongo.f_str2dt(written["histDt"])))},
            "pre_image_equals_document_before_update": bool(written) and {k: v for k, v in written.items() if k not in HIST_META} == {k: v for k, v in before.items() if k not in ("_id", "attributes")},
            "document_after": {"contactNotes": updated and updated.get("contactNotes"), "attributes_kept": bool(updated) and updated.get("attributes") == before.get("attributes")},
            "id_continues_loaded_sequence": bool(written) and written["_id"] == last_id + 1,
        }
        ok = (not out["trigger_pre_image_keys_minus_mongo"] and not out["mongo_pre_image_keys_minus_trigger"]
              and out["written"]["histOp"] == "UPD" and out["written"]["histDt_format_ok"] and out["written"]["histDate_derived"]
              and out["pre_image_equals_document_before_update"] and out["document_after"]["contactNotes"] == "edge probe pre-image"
              and out["document_after"]["attributes_kept"] and out["id_continues_loaded_sequence"])
        self.record("EDGE-U2-004", "backends/mongo.update_customer writes the pre-image with the same key set as the loader-carried trigger pre-image "
                    "of the same customer, histDate derived, _id continuing the Oracle hist sequence; attributes are not versioned (as Oracle)", {"mongo": out}, ok,
                    notes="no app write path exists today (customer_master: 3 reads, 0 writes); this is the migrate-as-logic trigger replacement")

    def probe_update_atomicity(self):
        """Both halves of the pre-image + update transaction must fail together: a failing $set (second write) leaves
        no stray pre-image, and a failing pre-image insert (first write, forced with a temporary $jsonSchema validator on
        customers_hist, as Atlas would reject a document above the validator's shape) leaves the customer unchanged."""
        from pymongo.errors import PyMongoError

        mongo = self.backends["mongo"]
        cust_id = self.moved["dirty_dates"]["cust_id"]
        hist = self.mdb.customers_hist
        before = self.mdb.customers.find_one({"_id": cust_id})
        n0 = hist.count_documents({})
        out = {}
        try:
            mongo.update_customer(cust_id, {"$illegal": 1})
            out["bad_update_field"] = "no error"
        except PyMongoError as exc:
            out["bad_update_field"] = type(exc).__name__
        out["customer_unchanged_after_bad_update"] = self.mdb.customers.find_one({"_id": cust_id}) == before
        out["hist_rows_added_by_bad_update"] = hist.count_documents({}) - n0
        self.mdb.command("collMod", "customers_hist", validator={"$jsonSchema": {"required": ["edgeProbeRequiredField"]}}, validationLevel="strict")
        try:
            try:
                mongo.update_customer(cust_id, {"custName": "MUST NOT PERSIST"})
                out["pre_image_insert_rejected"] = "no error"
            except PyMongoError as exc:
                out["pre_image_insert_rejected"] = type(exc).__name__
        finally:
            self.mdb.command("collMod", "customers_hist", validator={}, validationLevel="off")
        out["customer_unchanged_after_pre_image_failure"] = self.mdb.customers.find_one({"_id": cust_id}) == before
        out["hist_rows_added_by_pre_image_failure"] = hist.count_documents({}) - n0
        try:
            mongo.update_customer(cust_id, {})
            out["empty_change_set"] = "no error"
        except ValueError as exc:
            out["empty_change_set"] = type(exc).__name__
        a = mongo.update_customer(cust_id, {"contactNotes": "edge probe a"})
        b = mongo.update_customer(cust_id, {"contactNotes": "edge probe b"})
        ids = [d["_id"] for d in hist.find({"custId": cust_id}).sort("_id", 1)]
        out["two_sequential_updates"] = {"hist_ids_for_customer": [int(i) for i in ids], "distinct_and_increasing": ids == sorted(set(ids)),
                                         "final_contact_notes": b and b.get("contactNotes"), "pre_image_of_second_is_first_result": hist.find_one({"_id": ids[-1]}).get("contactNotes") == (a or {}).get("contactNotes")}
        ok = (out["bad_update_field"] != "no error" and out["customer_unchanged_after_bad_update"] and out["hist_rows_added_by_bad_update"] == 0
              and out["pre_image_insert_rejected"] != "no error" and out["customer_unchanged_after_pre_image_failure"] and out["hist_rows_added_by_pre_image_failure"] == 0
              and out["empty_change_set"] == "ValueError" and out["two_sequential_updates"]["distinct_and_increasing"]
              and out["two_sequential_updates"]["pre_image_of_second_is_first_result"])
        self.record("EDGE-U2-005", "pre-image + update atomicity: a failing $set leaves no stray pre-image; a rejected pre-image insert (validator) leaves the "
                    "customer unchanged; an empty change set is refused; sequential updates chain pre-images with distinct increasing _ids", {"mongo": out}, ok,
                    notes="_next_id is max(_id)+1 read inside the transaction; two concurrent update_customer calls on one node would race to the same _id and "
                          "the loser gets DuplicateKeyError (nothing persists, no retry as log_msg has). Not reachable today: no app write path to customers")

    def restore_moved(self):
        for m in self.moved.values():
            self.oracle([f"UPDATE customer_master SET cust_seq_no = {m['cust_seq_no']} WHERE cust_id = '{m['cust_id']}'"])
        self.oracle([f"DELETE FROM customer_master_hist WHERE hist_id > {self.hist0}"])

    def probe_money_edges(self):
        tenant = next(t for t in self.fixture.probe_tenants() if t["class"] == "with_attributes")
        cust_id = tenant["cust_id"]
        original = self.oracle([], fetch=f"SELECT {', '.join(MONEY)} FROM customer_master WHERE cust_id = :1", binds=(cust_id,))[0]
        sets = ", ".join(f"{col} = {'NULL' if val is None else val}" for col, val in MONEY.items())
        hist0 = int(self.oracle([], fetch="SELECT NVL(MAX(hist_id), 0) FROM customer_master_hist")[0][0] or 0)
        self.oracle([f"UPDATE customer_master SET {sets} WHERE cust_id = '{cust_id}'"])
        try:
            self.reload(U2)
            routes = self.routes(tenant["tenant_id"])
            body = routes["oracle"]["GET /api/v1/billing/customer"]["body"] or {}
            doc = self.mdb.customers.find_one({"_id": cust_id}) or {}
            camel = self.backends["mongo"]._camel
            stored = {col: (type(doc.get(camel(col))).__name__, str(doc.get(camel(col)).to_decimal()) if doc.get(camel(col)) is not None else None) for col in MONEY}
            exact = all((stored[col][1] is None and val is None) or (stored[col][0] == "Decimal128" and Decimal(stored[col][1]) == Decimal(val)) for col, val in MONEY.items())
            out = {"routes_identical": routes["oracle"] == routes["mongo"], "served_cust_id": body.get("cust_id") == cust_id,
                   "rendered": {col: body.get(col) for col in MONEY}, "me_customer": routes["mongo"]["GET /api/v1/billing/me .customer"],
                   "mongo_stored": stored, "mongo_decimal128_exact": exact,
                   "rendered_as_expected": all(body.get(col) == val for col, val in MONEY.items())}
            ok = out["routes_identical"] and out["served_cust_id"] and exact and out["rendered_as_expected"] and out["me_customer"]["customer"]["cur_bal_amt"] == "0.01"
            self.record("EDGE-U2-006", "NUMBER(14,2) money edges (0.01, -0.01, 999999999999.99 max, 1234567890.1, 0, NULL) load as exact Decimal128 and "
                        "render identically on /customer and /me.customer", {"both": out}, ok)
        finally:
            restore = ", ".join(f"{col} = {'NULL' if v is None else v}" for col, v in zip(MONEY, original))
            self.oracle([f"UPDATE customer_master SET {restore} WHERE cust_id = '{cust_id}'",
                         f"DELETE FROM customer_master_hist WHERE hist_id > {hist0}"])

    def probe_eav_outside_contract(self):
        """ENTITY_ATTR_VALUE rows the facade never reads (non-CUSTOMER entity_type, entity_id without a customer): the
        loader must not drop them silently; mapping_spec says such a row fails the load. Oracle serves unchanged."""
        tenant = next(t for t in self.fixture.probe_tenants() if t["class"] == "with_attributes")
        before = self.counts()
        base_routes = self.routes(tenant["tenant_id"])
        out = {}
        for label, etype, eid in (("non_customer_entity_type", "INVOICE", tenant["cust_id"]), ("orphan_entity_id", "CUSTOMER", "e0000000-no-such-customer")):
            self.oracle([f"INSERT INTO entity_attr_value (eav_id, entity_type, entity_id, attr_name, attr_value, attr_type, created_dt) "
                         f"VALUES (seq_entity_attr_value.NEXTVAL, '{etype}', '{eid}', 'EDGE_PROBE', 'x', 'STR', '01-JAN-26')"])
            try:
                rc = self.reload(U2)
                after = self.counts()
                routes = self.routes(tenant["tenant_id"])
                out[label] = {"loader_exit": rc, "customers_after_load": after.get("customers", 0), "customers_before": before["customers"],
                              "oracle_route_unchanged": routes["oracle"] == base_routes["oracle"],
                              "attribute_names_served_by_oracle": [a["attr_name"] for a in (routes["oracle"]["GET /api/v1/billing/customer"]["body"] or {}).get("attributes", [])]}
            finally:
                self.oracle(["DELETE FROM entity_attr_value WHERE attr_name = 'EDGE_PROBE'"])
        rc = self.reload(U2)
        out["reload_after_cleanup"] = {"loader_exit": rc, "customers": self.counts()["customers"]}
        ok = (all(out[k]["loader_exit"] != 0 and out[k]["customers_after_load"] == 0 and out[k]["oracle_route_unchanged"] for k in ("non_customer_entity_type", "orphan_entity_id"))
              and "EDGE_PROBE" not in out["non_customer_entity_type"]["attribute_names_served_by_oracle"]
              and rc == 0 and out["reload_after_cleanup"]["customers"] == before["customers"])
        self.record("EDGE-U2-007", "EAV rows outside the embed contract (entity_type <> 'CUSTOMER', entity_id without a customer_master row) fail the whole load "
                    "(no silent drop, nothing partially written: the collection was dropped and stays empty); the Oracle facade never served them", {"loader": out}, ok,
                    notes="by design (mapping_spec.json#customers.embedded.identity, 0 live); operational consequence: one stray EAV row blocks the delta load "
                          "until it is triaged, since U2 defines no quarantine collection")

    def probe_eav_order_and_case(self):
        tenant = next(t for t in self.fixture.probe_tenants() if t["class"] == "without_attributes")
        cust_id = tenant["cust_id"]
        for name, value in (("zeta", "1"), ("ALPHA", "2"), ("alpha", "3"), ("Alpha", "")):
            self.oracle([f"INSERT INTO entity_attr_value (eav_id, entity_type, entity_id, attr_name, attr_value, attr_type, created_dt) "
                         f"VALUES (seq_entity_attr_value.NEXTVAL, 'CUSTOMER', '{cust_id}', '{name}', {'NULL' if value == '' else repr(value)}, 'STR', '31-FEB-26')"])
        try:
            self.reload(U2)
            routes = self.routes(tenant["tenant_id"])
            attrs = (routes["oracle"]["GET /api/v1/billing/customer"]["body"] or {}).get("attributes", [])
            doc = self.mdb.customers.find_one({"_id": cust_id}) or {}
            out = {"routes_identical": routes["oracle"] == routes["mongo"],
                   "attr_names_in_order": [a["attr_name"] for a in attrs], "attr_values": [a["attr_value"] for a in attrs],
                   "eav_ids_ascending": [a["eav_id"] for a in attrs] == sorted((a["eav_id"] for a in attrs), key=int),
                   "created_dt_verbatim": [a["created_dt"] for a in attrs],
                   "mongo_element_siblings": [{"createdDate": e.get("createdDate"), "typed": e.get("typed")} for e in sorted(doc.get("attributes", []), key=lambda e: int(e["eavId"]))]}
            ok = (out["routes_identical"] and out["attr_names_in_order"] == ["zeta", "ALPHA", "alpha", "Alpha"] and out["attr_values"] == ["1", "2", "3", None]
                  and out["eav_ids_ascending"] and out["created_dt_verbatim"] == ["31-FEB-26"] * 4
                  and all(s["createdDate"] is None for s in out["mongo_element_siblings"]))
            self.record("EDGE-U2-008", "EAV rows inserted out of name order with case-variant names, a NULL value and an unparsable CREATED_DT (31-FEB-26): "
                        "both backends serve them in eav_id order, verbatim, with null createdDate sibling in the document", {"both": out}, ok)
        finally:
            self.oracle([f"DELETE FROM entity_attr_value WHERE entity_id = '{cust_id}' AND attr_name IN ('zeta', 'ALPHA', 'alpha', 'Alpha')"])

    def probe_insert_trigger_derivations(self):
        """TRG_CUSTOMER_MASTER_SEQ fills cust_seq_no, cust_name_upper and row_version_no on INSERT; a row inserted with
        them NULL must load with the trigger's values and render identically (the port never recomputes them)."""
        hist0 = int(self.oracle([], fetch="SELECT NVL(MAX(hist_id), 0) FROM customer_master_hist")[0][0] or 0)
        self.oracle([f"INSERT INTO tenants (id, name, tax_exempt_yn, status_cd) VALUES ('{EMPTY_TENANT}', 'Edge Trigger Tenant', 'N', 10)",
                     f"INSERT INTO customer_master (cust_id, tenant_id, cust_no, cust_name, signup_dt, cur_bal_amt, created_by, created_dt) "
                     f"VALUES ('{EDGE_CUST}', '{EMPTY_TENANT}', 'EDGE-0001', 'Édge MiXed case ß', '29-FEB-25', 12.5, 'EDGE', DATE '2026-02-20')"])
        try:
            self.reload(["tenants"] + U2)
            routes = self.routes(EMPTY_TENANT)
            body = routes["oracle"]["GET /api/v1/billing/customer"]["body"] or {}
            row = self.oracle_customer(EDGE_CUST) or {}
            doc = self.mdb.customers.find_one({"_id": EDGE_CUST}) or {}
            out = {"routes_identical": routes["oracle"] == routes["mongo"], "status": routes["mongo"]["GET /api/v1/billing/customer"]["status"],
                   "oracle_row": {"cust_seq_no": str(row.get("cust_seq_no")), "cust_name_upper": row.get("cust_name_upper"), "row_version_no": str(row.get("row_version_no"))},
                   "mongo_doc": {"custSeqNo": str(doc.get("custSeqNo")), "custNameUpper": doc.get("custNameUpper"), "rowVersionNo": str(doc.get("rowVersionNo")),
                                 "signupDate(29-FEB-25 invalid day)": doc.get("signupDate"), "attributes": doc.get("attributes")},
                   "rendered": {k: body.get(k) for k in ("cust_seq_no", "cust_name_upper", "row_version_no", "signup_dt", "cur_bal_amt", "created_dt", "attributes")},
                   "hist_rows_from_insert": len(self.hist_rows(hist0))}
            ok = (out["routes_identical"] and out["status"] == 200 and row.get("cust_seq_no") is not None
                  and out["mongo_doc"]["custSeqNo"] == out["oracle_row"]["cust_seq_no"] and out["mongo_doc"]["custNameUpper"] == row.get("cust_name_upper")
                  and str(row.get("cust_name_upper")).startswith("ÉDGE MIXED CASE")
                  and out["mongo_doc"]["rowVersionNo"] == "1" and out["mongo_doc"]["signupDate(29-FEB-25 invalid day)"] is None
                  and out["rendered"]["signup_dt"] == "29-FEB-25" and out["rendered"]["cur_bal_amt"] == "12.5" and out["rendered"]["attributes"] == []
                  and out["hist_rows_from_insert"] == 0)
            self.record("EDGE-U2-009", "TRG_CUSTOMER_MASTER_SEQ derivations on INSERT (sequence cust_seq_no, Oracle UPPER(cust_name) incl. non-ASCII, carried as Oracle computed it, row_version_no 1) "
                        "are carried verbatim and rendered identically; an invalid calendar day (29-FEB-25) stays verbatim with a null signupDate; "
                        "INSERT writes no hist row on either side", {"both": out}, ok)
        finally:
            self.oracle([f"DELETE FROM customer_master WHERE cust_id = '{EDGE_CUST}'",
                         f"DELETE FROM customer_master_hist WHERE hist_id > {hist0}",
                         f"DELETE FROM subscriptions WHERE tenant_id = '{EMPTY_TENANT}'",
                         f"DELETE FROM subscriptions_hist WHERE tenant_id = '{EMPTY_TENANT}'",
                         f"DELETE FROM tenants WHERE id = '{EMPTY_TENANT}'"])
            for name in ("tenants", "subscriptions", "subscriptions_hist"):
                self.mdb[name].delete_many({"$or": [{"_id": EMPTY_TENANT}, {"tenantId": EMPTY_TENANT}]})

    def probe_quarantine_na(self, live_report: Path):
        spec = json.loads((self.root / "migration" / "billing" / "mapping_spec.json").read_text())
        u2 = [c for c in spec["collections"] if c["name"] in U2]
        live = json.loads(live_report.read_text()) if live_report.exists() else {}
        out = {"u2_quarantine_of": {c["name"]: c.get("quarantine_of") for c in u2},
               "u2_embedded_quarantine_collections": {c["name"]: [e.get("quarantine_collection") for e in c.get("embedded", [])] for c in u2},
               "quarantine_collections_in_spec": [c["name"] for c in spec["collections"] if c.get("quarantine_of")],
               "live_unverified_paths": live.get("unverified_paths")}
        ok = (all(v is None for v in out["u2_quarantine_of"].values()) and all(not any(q) for q in out["u2_embedded_quarantine_collections"].values())
              and any("INVOICE_LINE" in str(p) for p in out["live_unverified_paths"] or []))
        self.record("EDGE-U2-010", "quarantined rows: no U2 collection has a quarantine sibling (customers embeds EAV without one); the planted "
                    "orphaned INVOICE_LINE rows belong to U4's quarantine and are listed unverified in the U2 live report", {"spec": out}, ok)

    def probe_write_scope(self):
        scratch = "ow_tp_billing_u2_scope_probe"
        dbs_before = sorted(self.fixture.mongo.list_database_names())
        counts_before = self.counts()
        try:
            rc = self.reload(U2, mongo_db=scratch)
            scratch_colls = sorted(self.fixture.mongo[scratch].list_collection_names())
            indexes = {c: sorted(self.fixture.mongo[scratch][c].index_information()) for c in scratch_colls}
            dbs_after = sorted(self.fixture.mongo.list_database_names())
        finally:
            self.fixture.mongo.drop_database(scratch)
        for tenant in self.fixture.probe_tenants():
            self.routes(tenant["tenant_id"])
        counts_after = self.counts()
        out = {"loader_exit": rc, "scratch_collections": scratch_colls, "indexes": indexes,
               "other_databases_touched": sorted(set(dbs_after) - set(dbs_before) - {scratch}),
               "fixture_db_counts_changed_by_routes": {k: (counts_before.get(k), counts_after.get(k)) for k in set(counts_before) | set(counts_after) if counts_before.get(k) != counts_after.get(k)}}
        ok = rc == 0 and scratch_colls == U2 and not out["other_databases_touched"] and not out["fixture_db_counts_changed_by_routes"]
        self.record("EDGE-U2-011", "write scope: the U2 loader writes only customers and customers_hist (plus their spec indexes) in the target database and "
                    "touches no other database; GET /customer and /me on the Mongo backend write nothing for known tenants", {"mongo": out}, ok)

    # ---- driver ---------------------------------------------------------------------------------
    def run(self, out_dir: Path, live_report: Path):
        print("reloading U1 + U2 from the Oracle fixture (batch loader, 2 passes) ...")
        self.fixture.reload(out_dir / "U2.verify.edge_probes.load.json")
        self.probe_empty_and_unknown_tenant()
        self.probe_anomalies_through_facade()
        self.probe_trigger_hist_carried(out_dir / "U2.verify.edge_local.recon.json")
        self.probe_update_customer_pre_image_shape()
        self.probe_update_atomicity()
        self.restore_moved()
        self.probe_money_edges()
        self.probe_eav_outside_contract()
        self.probe_eav_order_and_case()
        self.probe_insert_trigger_derivations()
        self.probe_quarantine_na(live_report)
        self.probe_write_scope()
        self.reload(U2)
        leftovers = {"customer_master_hist": int(self.oracle([], fetch="SELECT COUNT(*) FROM customer_master_hist")[0][0]),
                     "edge_rows": int(self.oracle([], fetch=f"SELECT COUNT(*) FROM customer_master WHERE cust_id = '{EDGE_CUST}' OR tenant_id IN ('{EMPTY_TENANT}', '{NEW_TENANT}')")[0][0]),
                     "edge_eav": int(self.oracle([], fetch="SELECT COUNT(*) FROM entity_attr_value WHERE attr_name IN ('EDGE_PROBE', 'zeta', 'ALPHA', 'alpha', 'Alpha')")[0][0])}
        self.record("EDGE-U2-012", "fixture restored: no probe rows left in customer_master, customer_master_hist or entity_attr_value", {"oracle": leftovers},
                    all(v == 0 for v in leftovers.values()))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--repo-root", default=str(HERE.parents[4]), help="checkout whose loader/backends/recon to exercise (the PR head)")
    p.add_argument("--oracle-dsn-env", default="OW_TP_ORACLE_FIXTURE_DSN")
    p.add_argument("--mongo-uri-env", default="OW_TP_MONGO_FIXTURE_URI")
    p.add_argument("--live-report", default=str(HERE / "U2.verify.live.recon.json"))
    p.add_argument("--out", default=str(HERE / "U2.verify.edge_probes.json"))
    args = p.parse_args(argv)
    root = Path(args.repo_root).resolve()
    setup_paths(root)
    os.environ["MONGODB_ATLAS_URI"] = os.environ[args.mongo_uri_env]  # process-local: the fixture mongod
    os.environ.setdefault("ORACLE_PORT", "52521")

    probes = Probes(root, args.oracle_dsn_env, args.mongo_uri_env)
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=root).stdout.strip()
    probes.run(Path(args.out).parent, Path(args.live_report))
    report = {
        "kind": "u2-edge-probes", "unit": "U2", "run_mode": "fixture", "merge_evidence": False,
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "code_under_test": {"repo_root": str(root), "head": head},
        "source": {"oracle": f"local fixture {probes.fixture.oracle_host}", "mongo": f"local fixture, database {probes.fixture.database}"},
        "probes": probes.results,
        "verdict": "pass" if all(r["pass"] for r in probes.results) else "fail",
    }
    Path(args.out).write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(f"edge probes {report['verdict']} ({sum(r['pass'] for r in probes.results)}/{len(probes.results)}) -> {args.out}")
    return 0 if report["verdict"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
