#!/usr/bin/env python3
"""UNT-16 edge-case probes for U1 (plans module) on the local fixtures only.

Drives the Oracle backend (PKG_PLANS + triggers on the Oracle Free fixture) and the Mongo
backend (its port, on a loopback mongod) through the same inputs past the parity scenarios
and records whether they agree: empty/unknown tenants, tenant bootstrap, the cancelled-stays-
cancelled trigger, same-day plan changes, duplicate plan changes through the facade, insert
conflicts inside the close+insert transaction, decimal edges on plans, and a `recon.py run
--mode local` with subscriptions_hist rows present (live hist has 0 rows, so the dirty-date
derived rule is otherwise unexercised). Quarantine is not part of U1 and is recorded as such.

    TZ=UTC LC_ALL=C OW_TP_ORACLE_FIXTURE_DSN=... OW_TP_MONGO_FIXTURE_URI=... \
      uv run --no-project --with oracledb==2.5.1 --with pymongo==4.10.1 --with flask==3.1.1 \
        --with pyyaml==6.0.2 --with jsonschema==4.25.1 --with rfc3339-validator==0.1.4 \
        python3 migration/billing/waves/wave1/verify/edge_probes.py [--repo-root <checkout>]

Refuses non-loopback hosts on either side (via plans_parity.Fixture). Never merge evidence.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

U1 = ["codes", "tenants", "plans", "subscriptions", "subscriptions_hist"]
T = {n: f"00000000-0000-0000-0000-00000000000{n}" for n in range(1, 10)}
P = {n: f"10000000-0000-0000-0000-00000000000{n}" for n in range(1, 4)}
S = {n: f"20000000-0000-0000-0000-00000000000{n}" for n in range(1, 10)}
EMPTY_TENANT = "e0000000-0000-0000-0000-0000000000e1"
NEW_TENANT = "e0000000-0000-0000-0000-0000000000e2"
EDGE_PLAN = "e0000000-0000-0000-0000-0000000000p1"
EDGE_PLAN_INACTIVE = "e0000000-0000-0000-0000-0000000000p2"
HIST_DT_RE = re.compile(r"^\d{2}-[A-Z]{3}-\d{2} \d{2}:\d{2}:\d{2}$")


def setup_paths(root: Path):
    for rel in (("procs", "harness"), ("migration", "billing", "loaders"), ("migration", "billing", "recon"),
                ("migration", "billing", "waves", "wave1"), ("services", "legacy-billing", "app")):
        sys.path.insert(0, str(root.joinpath(*rel)))


class Probes:
    def __init__(self, root: Path, oracle_dsn_env: str, mongo_uri_env: str):
        import oracledb
        import plans_parity
        from backends import mongo as mongo_backend
        from backends import oracle as oracle_backend
        from app import app

        self.root, self.oracledb = root, oracledb
        self.fixture = plans_parity.Fixture(oracle_dsn_env, mongo_uri_env)
        self.oracle_dsn_env, self.mongo_uri_env = oracle_dsn_env, mongo_uri_env
        self.backends = {"oracle": oracle_backend, "mongo": mongo_backend}
        self.app = app
        self.mdb = self.fixture.mongo[self.fixture.database]
        self.results = []

    # ---- fixture helpers -------------------------------------------------------------
    def oracle(self, statements, fetch=None):
        with self.oracledb.connect(**self.fixture.dsn_kw) as conn, conn.cursor() as cur:
            for stmt in statements:
                cur.execute(stmt)
            out = None
            if fetch:
                cur.execute(fetch)
                out = cur.fetchall()
            conn.commit()
            return out

    def reload_mongo(self):
        for name in U1:
            self.mdb.drop_collection(name)
        rc = self.fixture.loader.main([
            "--mode", "fixture", "--collections", ",".join(U1),
            "--oracle-dsn-env", self.oracle_dsn_env, "--mongo-uri-env", self.mongo_uri_env,
            "--mongo-db", self.fixture.database,
        ])
        if rc != 0:
            raise SystemExit("fixture reload failed")

    def use(self, backend):
        os.environ["BILLING_BACKEND"] = backend
        return self.backends[backend], self.app.test_client()

    def rows(self, backend, tenant_id):
        return self.fixture.probe(backend, tenant_id)

    def raw_rows(self, backend, tenant_id):
        """Independent of plans_parity.Fixture.probe/_ordered: unordered (plan_id, starts_on, ends_on, status) multiset."""
        from collections import Counter
        if backend == "oracle":
            got = self.oracle([], fetch=f"SELECT plan_id, TO_CHAR(starts_on, 'YYYY-MM-DD'), TO_CHAR(ends_on, 'YYYY-MM-DD'), status_cd "
                                        f"FROM subscriptions WHERE tenant_id = '{tenant_id}'")
            return Counter((r[0], r[1], r[2], {10: "active", 20: "suspended", 30: "cancelled"}.get(int(r[3]), "UNKNOWN")) for r in got)
        return Counter((d.get("planId"), d["startsOn"].date().isoformat(), d["endsOn"].date().isoformat() if d.get("endsOn") else None,
                        {10: "active", 20: "suspended", 30: "cancelled"}.get(d.get("statusCd"), "UNKNOWN"))
                       for d in self.mdb.subscriptions.find({"tenantId": tenant_id}))

    def hist(self, backend, tenant_id):
        if backend == "oracle":
            got = self.oracle([], fetch=f"SELECT hist_op, id, plan_id, status_cd, hist_dt FROM subscriptions_hist "
                                        f"WHERE tenant_id = '{tenant_id}' ORDER BY hist_id")
            return [{"op": r[0], "subscription_id": r[1], "plan_id": r[2], "status_cd": int(r[3]),
                     "hist_dt_format_ok": bool(HIST_DT_RE.match(r[4] or ""))} for r in got]
        out = []
        for d in self.mdb.subscriptions_hist.find({"tenantId": tenant_id}).sort("_id", 1):
            derived_ok = d.get("histDate") is not None and self.backends["mongo"].f_str2dt(d["histDt"]) == d["histDate"].date()
            out.append({"op": d["histOp"], "subscription_id": d["subscriptionId"], "plan_id": d.get("planId"),
                        "status_cd": d["statusCd"], "hist_dt_format_ok": bool(HIST_DT_RE.match(d.get("histDt") or "")),
                        "hist_date_derived_from_hist_dt": derived_ok})
        return out

    def record(self, pid, description, per_backend, passed, notes=None, **extra):
        entry = {"id": pid, "description": description, "backends": per_backend, "pass": bool(passed)}
        if notes:
            entry["notes"] = notes
        entry.update(extra)
        self.results.append(entry)
        print(f"{pid}: {'pass' if passed else 'FAIL'} - {description}")
        return entry

    # ---- probes --------------------------------------------------------------------------
    def probe_empty_tenant(self):
        self.fixture.reset()
        self.oracle([f"INSERT INTO tenants (id, name, tax_exempt_yn, status_cd) VALUES ('{EMPTY_TENANT}', 'Edge Empty Tenant', 'N', 10)"])
        self.reload_mongo()
        out = {}
        try:
            for name in ("oracle", "mongo"):
                backend, client = self.use(name)
                headers = {"X-User-ID": EMPTY_TENANT, "X-User-Email": "edge-empty@example.com"}
                me = client.get("/api/v1/billing/me", query_string={"on": "2026-02-28"}, headers=headers)
                body = me.get_json()
                body.pop("customer", None)
                out[name] = {
                    "entitlement()": backend.entitlement(EMPTY_TENANT, "2026-02-28"),
                    "tenant_profile()": backend.tenant_profile(EMPTY_TENANT),
                    "GET /api/v1/billing/entitlement": client.get("/api/v1/billing/entitlement", query_string={"on": "2026-02-28"}, headers=headers).get_json(),
                    "GET /api/v1/billing/me": {"status": me.status_code, "body": body},
                    "GET /plans/<t>/entitlement": client.get(f"/plans/{EMPTY_TENANT}/entitlement", query_string={"on": "2026-02-28"}).get_json(),
                    "subscriptions_after": self.rows(name, EMPTY_TENANT),
                }
            ok = out["oracle"] == out["mongo"] and out["mongo"]["entitlement()"] == [] and out["mongo"]["subscriptions_after"] == []
            self.record("EDGE-001", "tenant with no subscriptions: entitlement empty on both backends, /me does not bootstrap a subscription", out, ok)
        finally:
            self.oracle([f"DELETE FROM subscriptions WHERE tenant_id = '{EMPTY_TENANT}'",
                         f"DELETE FROM subscriptions_hist WHERE tenant_id = '{EMPTY_TENANT}'",  # after the DEL trigger rows
                         f"DELETE FROM tenants WHERE id = '{EMPTY_TENANT}'"])

    def probe_unknown_tenant(self):
        self.fixture.reset()
        out = {}
        for name in ("oracle", "mongo"):
            backend, client = self.use(name)
            out[name] = {
                "entitlement()": backend.entitlement("no-such-tenant", "2026-02-28"),
                "tenant_profile()": backend.tenant_profile("no-such-tenant"),
                "GET /plans/no-such-tenant/entitlement": client.get("/plans/no-such-tenant/entitlement", query_string={"on": "2026-02-28"}).get_json(),
                "entitlement() before first subscription": backend.entitlement(T[1], "2025-12-31"),
            }
        ok = out["oracle"] == out["mongo"] and all(v == [] for v in out["mongo"].values())
        self.record("EDGE-002", "unknown tenant and a date before the first subscription: empty results on both backends", out, ok)

    def probe_bootstrap(self):
        out = {}
        try:
            for name in ("oracle", "mongo"):
                self.fixture.reset()
                backend, client = self.use(name)
                headers = {"X-User-ID": NEW_TENANT, "X-User-Email": "edge-new@example.com"}
                first = client.get("/api/v1/billing/me", query_string={"on": dt.date.today().isoformat()}, headers=headers)
                second = client.get("/api/v1/billing/me", query_string={"on": dt.date.today().isoformat()}, headers=headers)
                body = first.get_json()
                body.pop("customer", None)
                out[name] = {"GET /api/v1/billing/me (first)": {"status": first.status_code, "body": body},
                             "second call identical": first.get_json() == second.get_json(),
                             "subscriptions_after": self.rows(name, NEW_TENANT),
                             "tenant_profile()": backend.tenant_profile(NEW_TENANT)}
                if name == "oracle":
                    self.oracle([f"DELETE FROM subscriptions WHERE tenant_id = '{NEW_TENANT}'",
                                 f"DELETE FROM subscriptions_hist WHERE tenant_id = '{NEW_TENANT}'",  # after the DEL trigger rows
                                 f"DELETE FROM tenants WHERE id = '{NEW_TENANT}'"])
            ent = out["mongo"]["GET /api/v1/billing/me (first)"]["body"].get("entitlement")
            ok = (out["oracle"] == out["mongo"] and out["mongo"]["second call identical"]
                  and len(out["mongo"]["subscriptions_after"]) == 1 and ent and ent[0]["plan_code"] == "STARTER")
            self.record("EDGE-003", "unknown identity on /me bootstraps the tenant + cheapest active plan once, identically on both backends", out, ok)
        finally:
            self.oracle([f"DELETE FROM subscriptions WHERE tenant_id = '{NEW_TENANT}'",
                         f"DELETE FROM subscriptions_hist WHERE tenant_id = '{NEW_TENANT}'",  # after the DEL trigger rows
                         f"DELETE FROM tenants WHERE id = '{NEW_TENANT}'"])

    def restore_s5(self):
        """Fixture.reset() restores rows with UPDATE, which TRG_SUB_NO_UNCANCEL blocks for a cancelled row;
        the local fixture's trigger is disabled for the restore only (fixture-only; never done live)."""
        self.oracle([f"DELETE FROM subscriptions WHERE tenant_id = '{T[5]}' AND id <> '{S[5]}'",
                     "ALTER TRIGGER trg_sub_no_uncancel DISABLE",
                     f"UPDATE subscriptions SET status_cd = 10, ends_on = NULL, suspended_on = NULL WHERE id = '{S[5]}'",
                     "ALTER TRIGGER trg_sub_no_uncancel ENABLE",
                     f"DELETE FROM subscriptions_hist WHERE tenant_id = '{T[5]}'"])

    def probe_cancelled_stays_cancelled(self):
        out = {}
        try:
            for name in ("oracle", "mongo"):
                self.restore_s5()
                self.fixture.reset()
                self.oracle([f"UPDATE subscriptions SET status_cd = 30 WHERE id = '{S[5]}'"])  # fires trg_subscriptions_hist
                self.reload_mongo()
                backend, _ = self.use(name)
                before = self.rows(name, T[5])
                backend.change_plan(T[5], P[1], "2026-04-01")
                out[name] = {"before": before, "after": self.rows(name, T[5]), "hist": self.hist(name, T[5]),
                             "entitlement(2026-03-31)": backend.entitlement(T[5], "2026-03-31"),
                             "entitlement(2026-04-01)": backend.entitlement(T[5], "2026-04-01")}
            after = out["mongo"]["after"]
            strip = lambda rows: [{k: v for k, v in h.items() if k != "hist_date_derived_from_hist_dt"} for h in rows]
            ok = (out["oracle"]["after"] == out["mongo"]["after"] and strip(out["oracle"]["hist"]) == strip(out["mongo"]["hist"])
                  and out["oracle"]["entitlement(2026-04-01)"] == out["mongo"]["entitlement(2026-04-01)"]
                  and out["oracle"]["entitlement(2026-03-31)"] == out["mongo"]["entitlement(2026-03-31)"]
                  and after[0]["status"] == "cancelled" and after[0]["ends_on"] == "2026-03-31" and after[1]["status"] == "active"
                  and len(out["mongo"]["hist"]) == 2 and all(h["hist_dt_format_ok"] for h in out["mongo"]["hist"]))
            self.loaded_hist_sample = [d for d in self.mdb.subscriptions_hist.find({"tenantId": T[5]}).sort("_id", 1)][:1]
            self.record("EDGE-004", "TRG_SUB_NO_UNCANCEL: change_plan over a cancelled subscription keeps it cancelled; hist pre-images (loaded + written) agree", out, ok,
                        notes="hist row 1 is the loader's copy of the Oracle trigger row (histDt verbatim, histDate derived); hist row 2 is written by change_plan")
        finally:
            self.restore_s5()

    def probe_same_day(self):
        out = {}
        for name in ("oracle", "mongo"):
            self.fixture.reset()
            backend, _ = self.use(name)
            backend.change_plan(T[1], P[2], "2026-01-01")
            out[name] = {"after": sorted(self.rows(name, T[1]), key=lambda r: (r["plan_id"], r["starts_on"])),
                         "hist": self.hist(name, T[1]),
                         "open_subscriptions": sum(1 for r in self.rows(name, T[1]) if r["ends_on"] is None),
                         "entitlement(2026-02-28).plan_code": [e["plan_code"] for e in backend.entitlement(T[1], "2026-02-28")],
                         "raw_multiset (independent of Fixture.probe)": sorted(self.raw_rows(name, T[1]).elements())}
        strip = lambda rows: [{k: v for k, v in h.items() if k != "hist_date_derived_from_hist_dt"} for h in rows]
        ok = (out["oracle"]["after"] == out["mongo"]["after"] and strip(out["oracle"]["hist"]) == strip(out["mongo"]["hist"])
              and out["oracle"]["entitlement(2026-02-28).plan_code"] == out["mongo"]["entitlement(2026-02-28).plan_code"])
        self.record("EDGE-005", "same-day change_plan: backends/oracle.change_plan first closes subscriptions with starts_on = effective_on (ends_on = effective_on - 1) before PKG_PLANS.sp_change_plan; the Mongo port must do the same", out, ok,
                    notes=("backends/mongo.change_plan only closes starts_on < effective_on (the PL/SQL cursor) and skips the Oracle backend's "
                           "same-day UPDATE, so it leaves two open subscriptions and no hist pre-image, and entitlement becomes a sort tie" if not ok else None))

    def probe_duplicate_change_via_facade(self):
        out = {}
        future = (dt.date.today() + dt.timedelta(days=45)).isoformat()
        for name in ("oracle", "mongo"):
            self.fixture.reset()
            _, client = self.use(name)
            headers = {"X-User-ID": T[1], "X-User-Email": "tenant-one@example.com"}
            payload = {"plan_id": P[3], "effective_on": future}
            first = client.post("/api/v1/billing/plan-change", headers=headers, json=payload)
            rows_after_first = self.rows(name, T[1])
            second = client.post("/api/v1/billing/plan-change", headers=headers, json=payload)
            second_body = second.get_json() or {}
            out[name] = {"first": {"status": first.status_code, "body": first.get_json()},
                         "second": {"status": second.status_code, "error": second_body.get("error"), "detail (backend-specific, not compared)": second_body.get("detail")},
                         "rows_unchanged_by_second": rows_after_first == self.rows(name, T[1]),
                         "after": self.rows(name, T[1]), "hist": self.hist(name, T[1])}
        comparable = lambda o: {k: ({kk: vv for kk, vv in v.items() if not kk.startswith("detail")} if k == "second" else v)
                                for k, v in o.items() if k != "hist"}
        strip = lambda rows: [{k: v for k, v in h.items() if k != "hist_date_derived_from_hist_dt"} for h in rows]
        ok = (comparable(out["oracle"]) == comparable(out["mongo"]) and strip(out["oracle"]["hist"]) == strip(out["mongo"]["hist"])
              and out["mongo"]["first"]["status"] == 200 and out["mongo"]["second"]["status"] == 503
              and out["mongo"]["rows_unchanged_by_second"] and len(out["mongo"]["hist"]) == 1)
        self.record("EDGE-006", "repeating the same plan change: deterministic id collides (ORA-00001 / DuplicateKeyError) -> 503 on both, state unchanged", out, ok)

    def probe_insert_conflict_atomicity(self):
        out = {}
        conflict_id = self.backends["mongo"].f_md5_uuid(f"{T[4]}{P[2]}2026-06-01")
        for name in ("oracle", "mongo"):
            self.fixture.reset()
            self.oracle([f"INSERT INTO subscriptions (id, tenant_id, plan_id, starts_on, ends_on, status_cd) "
                         f"VALUES ('{conflict_id}', '{T[4]}', '{P[2]}', DATE '2026-05-01', DATE '2026-05-31', 10)"])
            self.reload_mongo()
            backend, _ = self.use(name)
            before, hist_before = self.rows(name, T[4]), self.hist(name, T[4])
            try:
                backend.change_plan(T[4], P[2], "2026-06-01")
                raised = None
            except backend.ESTATE_ERRORS as exc:
                raised = type(exc).__name__
            out[name] = {"raised": raised, "rows_unchanged": before == self.rows(name, T[4]),
                         "hist_unchanged": hist_before == self.hist(name, T[4]), "after": self.rows(name, T[4])}
        ok = all(o["raised"] and o["rows_unchanged"] and o["hist_unchanged"] for o in out.values()) and out["oracle"]["after"] == out["mongo"]["after"]
        self.record("EDGE-007", "close+insert atomicity: when the new id already exists, neither backend leaves the open subscription closed or a stray hist row", out, ok,
                    notes="Oracle: PL/SQL statement-level rollback of sp_change_plan; Mongo: session.with_transaction aborts")

    def probe_decimal_edges(self):
        self.fixture.reset()
        self.oracle([
            f"INSERT INTO plans (id, code, tier_cd, monthly_fee, included_units, overage_rate, active_yn) VALUES ('{EDGE_PLAN}', 'EDGE', 1, 0.01, 0, 0.000001, 'Y')",
            f"INSERT INTO plans (id, code, tier_cd, monthly_fee, included_units, overage_rate, active_yn) VALUES ('{EDGE_PLAN_INACTIVE}', 'EDGE_INACTIVE', 9, 9999999999.99, 2147483647, 999999.999999, 'N')",
        ])
        self.reload_mongo()
        out = {}
        from bson.decimal128 import Decimal128
        try:
            for name in ("oracle", "mongo"):
                backend, client = self.use(name)
                out[name] = {"list_plans()": backend.list_plans(),
                             "GET /api/v1/billing/plans": client.get("/api/v1/billing/plans", headers={"X-User-ID": T[1]}).get_json(),
                             "GET /plans": client.get("/plans").get_json()}
            docs = {d["code"]: d for d in self.mdb.plans.find({"code": {"$in": ["EDGE", "EDGE_INACTIVE"]}})}
            stored = {code: {k: [type(d[k]).__name__, str(d[k])] for k in ("monthlyFee", "overageRate", "includedUnits")} for code, d in docs.items()}
            edge = [p for p in out["mongo"]["list_plans()"] if p["code"] == "EDGE"]
            ok = (out["oracle"] == out["mongo"] and len(edge) == 1 and edge[0]["monthly_fee"] == "0.01" and edge[0]["overage_rate"] == "0.000001"
                  and not any(p["code"] == "EDGE_INACTIVE" for p in out["mongo"]["list_plans()"])
                  and all(isinstance(docs[c]["monthlyFee"], Decimal128) and isinstance(docs[c]["overageRate"], Decimal128) for c in docs)
                  and stored["EDGE_INACTIVE"]["monthlyFee"][1] == "9999999999.99" and stored["EDGE"]["overageRate"][1] == "0.000001")
            self.record("EDGE-008", "decimal edges: 0.01 / 0.000001 and NUMBER(12,2)/(12,6) maxima load as exact Decimal128 and render identically; inactive plan hidden on both", out, ok,
                        mongo_stored_types=stored)
        finally:
            self.oracle([f"DELETE FROM plans WHERE id IN ('{EDGE_PLAN}', '{EDGE_PLAN_INACTIVE}')"])

    def probe_local_recon_with_hist(self, out_path: Path):
        self.fixture.reset()
        self.oracle([f"UPDATE subscriptions SET suspended_on = NULL WHERE id IN ('{S[6]}', '{S[7]}')"])  # row trigger fires per row
        self.reload_mongo()
        hist_rows = self.oracle([], fetch="SELECT COUNT(*) FROM subscriptions_hist")[0][0]
        cmd = [sys.executable, str(self.root / "migration/billing/recon/recon.py"), "run", "--mode", "local",
               "--collections", ",".join(U1), "--oracle-dsn-env", self.oracle_dsn_env, "--mongo-uri-env", self.mongo_uri_env,
               "--mongo-db", self.fixture.database, "--out", str(out_path)]
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=self.root)
        report = json.loads(out_path.read_text()) if out_path.exists() else {}
        hist_checks = [c for c in report.get("checks", []) if c.get("collection") == "subscriptions_hist" or "subscriptions_hist" in c.get("id", "")]
        summary = {"exit": proc.returncode, "stdout": proc.stdout.strip().splitlines()[-3:], "stderr": proc.stderr.strip().splitlines()[-3:],
                   "verdict": report.get("verdict"), "run_mode": report.get("run_mode"), "merge_evidence": report.get("merge_evidence"),
                   "oracle_subscriptions_hist_rows": int(hist_rows),
                   "subscriptions_hist_checks": [{"id": c["id"], "status": c.get("status"), "expected": c.get("expected"), "actual": c.get("actual")} for c in hist_checks]}
        ok = proc.returncode == 0 and report.get("verdict") == "pass" and report.get("merge_evidence") is False and int(hist_rows) >= 2 and hist_checks
        self.record("EDGE-009", "recon.py --mode local over the five U1 collections with subscriptions_hist rows present (dirty-date derived rule exercised)", {"fixture": summary}, ok,
                    report_path=str(out_path))

    def probe_quarantine_na(self, live_report: Path):
        report = json.loads(live_report.read_text()) if live_report.exists() else {}
        unverified = report.get("unverified_paths", [])
        quarantine_collections = [c for c in self.fixture.loader.recon.build_inputs(
            Path(self.root / "migration/billing/mapping_spec.json"), Path(self.root / "migration/billing/tolerances.json"), None).collections
            if c.quarantine_of is not None]
        names = [c.name for c in quarantine_collections]
        ok = not any(n in U1 for n in names)
        self.record("EDGE-010", "quarantined rows: no U1 collection has a quarantine sibling; quarantine lives in later units and is listed unverified in the live report", {
            "quarantine_collections_in_mapping_spec": names,
            "live_unverified_paths": [u.get("path") if isinstance(u, dict) else u for u in unverified]}, ok)

    def probe_bootstrap_then_same_day_change(self):
        out = {}
        today = dt.date.today().isoformat()
        try:
            for name in ("oracle", "mongo"):
                self.fixture.reset()
                backend, client = self.use(name)
                headers = {"X-User-ID": NEW_TENANT, "X-User-Email": "edge-new@example.com"}
                me = client.get("/api/v1/billing/me", query_string={"on": today}, headers=headers)
                change = client.post("/api/v1/billing/plan-change", headers=headers, json={"plan_id": P[2], "effective_on": today})
                ent_after = client.get("/api/v1/billing/entitlement", query_string={"on": today}, headers=headers).get_json()
                rows = self.rows(name, NEW_TENANT)
                out[name] = {"bootstrap /me status": me.status_code, "plan-change": {"status": change.status_code, "body": change.get_json()},
                             "GET /entitlement after": ent_after, "subscriptions_after": rows,
                             "open_subscriptions": sum(1 for r in rows if r["ends_on"] is None), "hist": self.hist(name, NEW_TENANT),
                             "raw_multiset (independent of Fixture.probe)": sorted(self.raw_rows(name, NEW_TENANT).elements())}
                if name == "oracle":
                    self.oracle([f"DELETE FROM subscriptions WHERE tenant_id = '{NEW_TENANT}'",
                                 f"DELETE FROM subscriptions_hist WHERE tenant_id = '{NEW_TENANT}'",  # after the DEL trigger rows
                                 f"DELETE FROM tenants WHERE id = '{NEW_TENANT}'"])
            strip = lambda rows: [{k: v for k, v in h.items() if k != "hist_date_derived_from_hist_dt"} for h in rows]
            cmp = lambda o: {k: v for k, v in o.items() if k != "hist"}
            ok = cmp(out["oracle"]) == cmp(out["mongo"]) and strip(out["oracle"]["hist"]) == strip(out["mongo"]["hist"]) and out["oracle"]["open_subscriptions"] == 1
            self.record("EDGE-011", "facade path: new identity bootstrapped today, then POST /plan-change effective today -> one open subscription and identical entitlement on both backends", out, ok,
                        notes=None if ok else "reachable through the public facade: the Mongo port leaves the bootstrap subscription open next to the new one")
        finally:
            self.oracle([f"DELETE FROM subscriptions WHERE tenant_id = '{NEW_TENANT}'",
                         f"DELETE FROM subscriptions_hist WHERE tenant_id = '{NEW_TENANT}'",  # after the DEL trigger rows
                         f"DELETE FROM tenants WHERE id = '{NEW_TENANT}'"])

    def probe_ordering_hides_nothing(self):
        """86c634ae changed Fixture.probe to sort rows by (starts_on, closed-before-open, ends_on, plan_id) on both estates
        instead of ORDER BY starts_on / sort(startsOn), whose tie order was engine-specific. Check it is a pure
        canonicalisation: probe(...) must be a permutation of the raw rows (nothing dropped, merged or rewritten),
        and equality of probe outputs must coincide with equality of the independent multisets."""
        from collections import Counter
        out = {}
        for name in ("oracle", "mongo"):
            self.fixture.reset()
            backend, _ = self.use(name)
            backend.change_plan(T[1], P[2], "2026-01-01")      # same-day tie on starts_on
            backend.change_plan(T[4], P[2], "2026-03-15")      # second row starting the day PLANS-005's row would
            per_tenant = {}
            for n in range(1, 10):
                probe = self.rows(name, T[n])
                raw = self.raw_rows(name, T[n])
                per_tenant[T[n]] = {"probe_is_permutation_of_raw": Counter((r["plan_id"], r["starts_on"], r["ends_on"], r["status"]) for r in probe) == raw,
                                    "rows": len(probe)}
            out[name] = per_tenant
        agree = all(out["oracle"][t]["probe_is_permutation_of_raw"] and out["mongo"][t]["probe_is_permutation_of_raw"] for t in out["oracle"])
        self.fixture.reset()
        for name in ("oracle", "mongo"):
            backend, _ = self.use(name)
            backend.change_plan(T[1], P[2], "2026-01-01")
            backend.change_plan(T[4], P[2], "2026-03-15")
        probe_eq = {t: self.rows("oracle", t) == self.rows("mongo", t) for t in out["oracle"]}
        multiset_eq = {t: self.raw_rows("oracle", t) == self.raw_rows("mongo", t) for t in out["oracle"]}
        ok = agree and probe_eq == multiset_eq and all(multiset_eq.values())
        self.record("EDGE-013", "Fixture.probe canonical ordering (86c634ae) is a permutation of the raw rows and agrees with independent multiset equality on every static tenant", 
                    {"per_backend": out, "probe_equal_by_tenant": probe_eq, "raw_multiset_equal_by_tenant": multiset_eq}, ok,
                    notes="sort key (starts_on, ends_on is None, ends_on, plan_id) omits status; two rows equal on all four would keep input order, "
                          "which the deterministic md5 subscription id (tenant+plan+effective) makes unreachable through change_plan")

    def probe_loader_hist_date(self):
        import recon

        docs = getattr(self, "loaded_hist_sample", [])
        d = docs[0] if docs else {}
        sample = {"histDt": d.get("histDt"), "histDate_present": "histDate" in d,
                  "recon.parse_ddmonyy(histDt)": str(recon.parse_ddmonyy(d.get("histDt"))),
                  "backends.mongo.f_str2dt(histDt)": str(self.backends["mongo"].f_str2dt(d.get("histDt")))} if docs else {}
        trigger_format = "TO_CHAR(SYSDATE, 'DD-MON-YY HH24:MI:SS') (TRG_SUBSCRIPTIONS_HIST, 01_tables.sql)"
        ok = bool(docs) and sample["histDate_present"]
        self.record("EDGE-012", "loader-carried subscriptions_hist row written by the Oracle trigger has a derived histDate", {
            "oracle_trigger_hist_dt_format": trigger_format, "loader_copy": sample,
            "recon.DDMONYY_RE": recon.DDMONYY_RE.pattern, "backends.mongo.DDMONYY_RE": self.backends["mongo"].DDMONYY_RE.pattern}, ok,
            notes=None if ok else ("recon.parse_ddmonyy (also the loader's derived rule via map_source_row) accepts DD-MON-YY only, while every "
                                   "trigger-written HIST_DT carries a time suffix; carried hist rows therefore have no histDate and recon's "
                                   "derived_fields.rules treats that as correct (vacuous live: 0 hist rows). The app's own f_str2dt accepts the suffix, "
                                   "so app-written hist rows do get histDate -> inconsistent shape post-cutover"))

    def run(self, out_dir: Path, live_report: Path):
        self.probe_empty_tenant()
        self.probe_unknown_tenant()
        self.probe_bootstrap()
        self.probe_cancelled_stays_cancelled()
        self.probe_same_day()
        self.probe_duplicate_change_via_facade()
        self.probe_insert_conflict_atomicity()
        self.probe_decimal_edges()
        self.probe_local_recon_with_hist(out_dir / "U1.verify.local_edge.recon.json")
        self.probe_quarantine_na(live_report)
        self.probe_bootstrap_then_same_day_change()
        self.probe_ordering_hides_nothing()
        self.probe_loader_hist_date()
        self.fixture.reset()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--repo-root", default=str(HERE.parents[4]), help="checkout whose recon/loader/backends to exercise")
    p.add_argument("--oracle-dsn-env", default="OW_TP_ORACLE_FIXTURE_DSN")
    p.add_argument("--mongo-uri-env", default="OW_TP_MONGO_FIXTURE_URI")
    p.add_argument("--live-report", default=str(HERE / "U1.verify.live.recon.json"))
    p.add_argument("--out", default=str(HERE / "U1.verify.edge_probes.json"))
    args = p.parse_args(argv)
    root = Path(args.repo_root).resolve()
    setup_paths(root)
    os.environ["MONGODB_ATLAS_URI"] = os.environ[args.mongo_uri_env]  # process-local: the fixture mongod
    os.environ.setdefault("ORACLE_PORT", "52521")

    probes = Probes(root, args.oracle_dsn_env, args.mongo_uri_env)
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=root).stdout.strip()
    probes.run(Path(args.out).parent, Path(args.live_report))
    report = {
        "kind": "u1-edge-probes", "unit": "U1", "run_mode": "fixture", "merge_evidence": False,
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
