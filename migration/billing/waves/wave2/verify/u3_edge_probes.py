#!/usr/bin/env python3
"""UNT-22 edge-case probes for U3 (usage + rating: USAGE_EVENTS, RATING_PERIODS with the embedded RATING_RESULTS)
on the local fixtures only. Drives PKG_RATING on the Oracle Free fixture and the Mongo port (loopback mongod,
reloaded from the Oracle fixture by the batch's own loader) through the same inputs past rating_parity.py:
empty tenants and tenants without a covering plan, the TO_CHAR(.., 'YYYYMMDD') day-string window edges,
ADD_MONTHS' end-of-month rollover window, ROUND half-away-from-zero on money and on the suspension proration,
NUMBER(12,6) rates, sp_finalize_rating atomicity (business rollback with the autonomous log_msg surviving),
re-finalising an existing period (the id-derivation path a port can miss), TRG_USAGE_EVENTS_CHECK equivalents and
a USAGE_KIND code outside fn_usage_summary's DECODE, loader embedding of periods without results and the exact
Decimal128 money, local recon over the edge rows, and the write scope.

    TZ=UTC LC_ALL=C OW_TP_ORACLE_FIXTURE_DSN=... OW_TP_MONGO_FIXTURE_URI=... \
      uv run --no-project --with oracledb==2.5.1 --with pymongo==4.10.1 --with flask==3.1.1 \
        --with pyyaml==6.0.2 --with jsonschema==4.25.1 --with rfc3339-validator==0.1.4 \
        python3 migration/billing/waves/wave2/verify/u3_edge_probes.py --repo-root <PR checkout>

Refuses non-loopback hosts on either side (via rating_parity.Fixture). Fixture evidence only, never merge evidence.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
U3 = ["usage_events", "rating_periods"]
E_NOSUB = "e3000000-0000-0000-0000-0000000000e0"   # tenant with no subscription at all
E_PLAN = "e3000000-0000-0000-0000-0000000000e1"    # tenant on the probe plan, no seeded events
E_SUSP = "e3000000-0000-0000-0000-0000000000e2"    # suspended mid-period
E_RATE6 = "e3000000-0000-0000-0000-0000000000e3"   # plan with a 6-decimal overage rate
PLAN_EDGE = "e3000000-0000-0000-0000-00000000a001"  # 100 included, 0.055 (tier rounding lands on a half cent)
PLAN_RATE6 = "e3000000-0000-0000-0000-00000000a002"  # 1 included, 0.123456
FEB = ("2026-02-01", "2026-02-28")
SEEDED_TENANT = "00000000-0000-0000-0000-000000000001"
EDGE_PREFIX = "e3000000-0000-0000-0000-"


def setup_paths(root: Path):
    for rel in (("migration", "billing", "loaders"), ("migration", "billing", "recon"), ("migration", "billing", "waves", "wave1"),
                ("migration", "billing", "waves", "wave2"), ("procs", "harness"), ("services", "legacy-billing", "app")):
        sys.path.insert(0, str(root.joinpath(*rel)))


def jsonable(value):
    return json.loads(json.dumps(value, default=str))


def rating_row(body):
    """The fields of fn_usage_rating's single row that the probes compare."""
    row = body[0] if isinstance(body, list) and body else {}
    return {k: row.get(k) for k in ("used_units", "quota_units", "rollover_units", "billable_units", "first_tier_units", "second_tier_units", "overage_amount")}


class Probes:
    def __init__(self, root: Path, oracle_dsn_env: str, mongo_uri_env: str):
        import oracledb
        import rating_parity
        from backends import mongo as mongo_backend
        from backends import oracle as oracle_backend
        from app import app

        oracledb.defaults.fetch_decimals = True
        self.root, self.oracledb = root, oracledb
        self.fixture = rating_parity.Fixture(oracle_dsn_env, mongo_uri_env)
        self.parity = rating_parity
        self.oracle_dsn_env, self.mongo_uri_env = oracle_dsn_env, mongo_uri_env
        self.backends = {"oracle": oracle_backend, "mongo": mongo_backend}
        self.app = app
        self.mdb = self.fixture.mongo[self.fixture.database]
        self.results = []
        self.event_seq = 0

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

    def oracle_error(self, statement):
        """Run one statement in its own transaction; return the ORA error code (or None) and roll back."""
        with self.oracledb.connect(**self.fixture.dsn_kw) as conn, conn.cursor() as cur:
            try:
                cur.execute(statement)
            except self.oracledb.Error as exc:
                conn.rollback()
                return exc.args[0].code if exc.args and hasattr(exc.args[0], "code") else str(exc)[:60]
            conn.rollback()
            return None

    def reload(self, collections, mongo_db=None):
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

    def event(self, tenant, occurred_at, units, kind_cd=1):
        self.event_seq += 1
        eid = f"{EDGE_PREFIX}{self.event_seq:012x}"
        self.oracle([f"INSERT INTO usage_events (id, tenant_id, occurred_at, units, kind_cd) VALUES "
                     f"('{eid}', '{tenant}', TO_TIMESTAMP('{occurred_at}', 'YYYY-MM-DD HH24:MI:SS'), {units}, {kind_cd})"])
        return eid

    def usage(self, client, tenant, start, end):
        resp = client.get("/api/v1/billing/usage", headers={"X-User-ID": tenant, "X-User-Email": f"{tenant}@example.com"},
                          query_string={"period_start": start, "period_end": end})
        body = resp.get_json() or {}
        return {"status": resp.status_code, "summary": body.get("summary"), "rating": rating_row(body.get("rating")),
                "events": [(e.get("id"), e.get("occurred_at"), e.get("units"), e.get("kind")) for e in body.get("events") or []]}

    def preview(self, client, tenant, start, end):
        resp = client.post("/api/rating/preview", json={"tenant_id": tenant, "period_start": start, "period_end": end})
        return {"status": resp.status_code, "rating": rating_row(resp.get_json())}

    def finalize(self, client, tenant, start, end):
        try:
            resp = client.post("/api/rating/finalize", json={"tenant_id": tenant, "period_start": start, "period_end": end})
            return {"status": resp.status_code, "body": resp.get_json()}
        except Exception as exc:  # the app has no error handler: the test client re-raises what the backend raised
            return {"status": "exception", "error": type(exc).__name__, "detail": str(exc)[:160]}

    def both(self, fn, *args):
        out = {}
        for name in ("oracle", "mongo"):
            _backend, client = self.use(name)
            out[name] = fn(client, *args)
        return out

    def period_state(self, tenant, start):
        rows = self.oracle([], fetch="""SELECT rp.id, TO_CHAR(rp.period_end, 'YYYY-MM-DD'), rr.id, rr.subscription_id, rr.used_units, rr.quota_units,
                                              rr.rollover_units, rr.billable_units, TO_CHAR(rr.overage_amount), TO_CHAR(rr.created_at, 'YYYY-MM-DD')
                                         FROM rating_periods rp LEFT JOIN rating_results rr ON rr.period_id = rp.id
                                        WHERE rp.tenant_id = :1 AND rp.period_start = TO_DATE(:2, 'YYYY-MM-DD')""", binds=(tenant, start))
        oracle = [{"period_id": r[0], "period_end": r[1], "result_id": r[2], "subscription_id": r[3], "used": str(r[4]), "quota": str(r[5]),
                   "rollover": str(r[6]), "billable": str(r[7]), "overage": r[8], "created": r[9]} for r in rows]
        docs = list(self.mdb.rating_periods.find({"tenantId": tenant, "periodStart": dt.datetime.fromisoformat(start).replace(tzinfo=dt.timezone.utc)}))
        mongo = []
        for d in docs:
            r = d.get("result") or {}
            mongo.append({"period_id": d["_id"], "period_end": d["periodEnd"].date().isoformat(), "result_id": r.get("id"), "subscription_id": r.get("subscriptionId"),
                          "used": str(r.get("usedUnits")), "quota": str(r.get("quotaUnits")), "rollover": str(r.get("rolloverUnits")), "billable": str(r.get("billableUnits")),
                          "overage": None if r.get("overageAmount") is None else str(r["overageAmount"].to_decimal()),
                          "created": None if r.get("createdAt") is None else r["createdAt"].date().isoformat()})
        return {"oracle": oracle, "mongo": mongo}

    def audit_tail(self, needle):
        oracle = self.oracle([], fetch="SELECT COUNT(*) FROM billing_audit_log WHERE module = 'RATING' AND message LIKE :1", binds=(f"%{needle}%",))[0][0]
        mongo = self.mdb.billing_audit_log.count_documents({"module": "RATING", "message": {"$regex": needle}})
        return {"oracle": int(oracle), "mongo": int(mongo)}

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

    # ---- fixture setup -----------------------------------------------------------------------
    def plant(self):
        self.oracle([
            f"INSERT INTO plans (id, code, tier_cd, monthly_fee, included_units, overage_rate, active_yn) VALUES ('{PLAN_EDGE}', 'EDGE-U3-055', 1, 10, 100, 0.055, 'N')",
            f"INSERT INTO plans (id, code, tier_cd, monthly_fee, included_units, overage_rate, active_yn) VALUES ('{PLAN_RATE6}', 'EDGE-U3-RATE6', 1, 10, 1, 0.123456, 'N')",
            f"INSERT INTO tenants (id, name, tax_exempt_yn, status_cd) VALUES ('{E_NOSUB}', 'Edge U3 no subscription', 'N', 10)",
            f"INSERT INTO tenants (id, name, tax_exempt_yn, status_cd) VALUES ('{E_PLAN}', 'Edge U3 plan tenant', 'N', 10)",
            f"INSERT INTO tenants (id, name, tax_exempt_yn, status_cd) VALUES ('{E_SUSP}', 'Edge U3 suspended tenant', 'N', 10)",
            f"INSERT INTO tenants (id, name, tax_exempt_yn, status_cd) VALUES ('{E_RATE6}', 'Edge U3 rate6 tenant', 'N', 10)",
            f"INSERT INTO subscriptions (id, tenant_id, plan_id, starts_on, ends_on, status_cd, suspended_on) VALUES ('{EDGE_PREFIX}0000000000b1', '{E_PLAN}', '{PLAN_EDGE}', DATE '2025-01-01', NULL, 10, NULL)",
            f"INSERT INTO subscriptions (id, tenant_id, plan_id, starts_on, ends_on, status_cd, suspended_on) VALUES ('{EDGE_PREFIX}0000000000b2', '{E_SUSP}', '{PLAN_EDGE}', DATE '2025-01-01', NULL, 20, DATE '2026-02-15')",
            f"INSERT INTO subscriptions (id, tenant_id, plan_id, starts_on, ends_on, status_cd, suspended_on) VALUES ('{EDGE_PREFIX}0000000000b3', '{E_RATE6}', '{PLAN_RATE6}', DATE '2025-01-01', NULL, 10, NULL)",
        ])
        self.reload(["plans", "tenants", "subscriptions"])

    # ---- probes --------------------------------------------------------------------------
    def probe_empty_and_no_plan(self):
        out = {
            "plan_tenant_no_events": self.both(self.usage, E_PLAN, *FEB),
            "plan_tenant_preview": self.both(self.preview, E_PLAN, *FEB),
            "no_subscription_preview": self.both(self.preview, E_NOSUB, *FEB),
        }
        empty = out["plan_tenant_no_events"]["oracle"]
        ok = (all(v["oracle"] == v["mongo"] for v in out.values())
              and empty["summary"] == [] and empty["events"] == [] and empty["rating"]["used_units"] == "0" and empty["rating"]["quota_units"] == "100"
              and empty["rating"]["overage_amount"] == "0"
              and out["no_subscription_preview"]["oracle"]["rating"]["quota_units"] is None and out["no_subscription_preview"]["oracle"]["rating"]["overage_amount"] is None
              and out["no_subscription_preview"]["oracle"]["rating"]["billable_units"] == "0")
        self.record("EDGE-U3-001", "empty tenant (plan, no events): summary [], events [], rating used 0 / overage 0 on both; tenant with no subscription: "
                    "quota and overage NULL, billable 0 (NVL) on both; GET /usage and POST /api/rating/preview identical", out, ok)

    def probe_window_edges(self):
        ids = [self.event(E_PLAN, "2026-01-31 23:59:59", 1000), self.event(E_PLAN, "2026-02-01 00:00:00", 3),
               self.event(E_PLAN, "2026-02-28 23:59:59", 4, 2), self.event(E_PLAN, "2026-02-28 23:59:59", 5, 3), self.event(E_PLAN, "2026-03-01 00:00:00", 1000)]
        self.reload(U3)
        out = self.both(self.usage, E_PLAN, *FEB)
        o = out["oracle"]
        ok = (o == out["mongo"] and o["rating"]["used_units"] == "12" and sorted(s["kind"] for s in o["summary"]) == ["api", "compute", "storage"]
              and [e[0] for e in o["events"]] == [ids[3], ids[2], ids[1]] and all(e[0] not in (ids[0], ids[4]) for e in o["events"]))
        self.record("EDGE-U3-002", "TO_CHAR(occurred_at, 'YYYYMMDD') window: 00:00:00 on period_start and 23:59:59 on period_end count, the second before and the "
                    "midnight after do not; events listed occurred_at DESC, id DESC on a timestamp tie; identical on both", out, ok)

    def probe_add_months_window(self):
        start, end = "2026-05-31", "2026-06-29"
        rows = [("2026-02-28", 30, True), ("2026-02-27", 7, False), ("2026-05-30", 11, True), ("2026-05-31", 500, False)]
        stmts = []
        for n, (pstart, rollover, _inc) in enumerate(rows, 1):
            pid, rid = f"{EDGE_PREFIX}0000000000c{n}", f"{EDGE_PREFIX}0000000000d{n}"
            stmts.append(f"INSERT INTO rating_periods (id, tenant_id, period_start, period_end) VALUES ('{pid}', '{E_PLAN}', DATE '{pstart}', DATE '{pstart}')")
            stmts.append(f"INSERT INTO rating_results (id, period_id, subscription_id, used_units, quota_units, rollover_units, billable_units, overage_amount, created_at) "
                         f"VALUES ('{rid}', '{pid}', '{EDGE_PREFIX}0000000000b1', 0, 100, {rollover}, 0, 0, TIMESTAMP '{pstart} 00:00:00')")
        self.oracle(stmts)
        self.reload(U3)
        self.event(E_PLAN, "2026-06-10 10:00:00", 150)
        self.reload(U3)
        out = self.both(self.preview, E_PLAN, start, end)
        expected_rollover = str(sum(r for _p, r, inc in rows if inc))
        ok = out["oracle"] == out["mongo"] and out["oracle"]["rating"]["rollover_units"] == expected_rollover and out["oracle"]["rating"]["billable_units"] == "9"
        self.record("EDGE-U3-003", "rollover window ADD_MONTHS(period_start, -3) from a month-end start (2026-05-31 -> 2026-02-28 inclusive, 2026-02-27 out, "
                    "the period's own start out): prior rollover summed identically on both; port's _add_months carries Oracle's last-day rule", out, ok,
                    expected_rollover=expected_rollover)

    def probe_money_rounding(self):
        # 201 used, 100 included, no rollover -> billable 101 -> 101 * 0.055 = 5.555 -> ROUND(.., 2) = 5.56 (half away from zero, not banker's)
        self.event(E_PLAN, "2025-10-10 10:00:00", 201)  # a month before any planted rollover period
        # suspended on 2026-02-15 of a 28-day period: factor 14/28 = 0.5; billable 5 -> ROUND(2.5) = 3; overage 0.28 -> 0.14
        self.event(E_SUSP, "2026-02-10 10:00:00", 105)
        # 6-decimal rate: 1 included, 2 used -> 1 * 0.123456 -> 0.12; 1000001 used -> 101*r + 999899*r*1.5 -> 185,163.80 (NUMBER(12,2) range)
        self.event(E_RATE6, "2026-02-10 10:00:00", 2)
        self.event(E_RATE6, "2026-03-10 10:00:00", 1000001)
        self.reload(U3)
        out = {
            "half_cent_tier": self.both(self.preview, E_PLAN, "2025-10-01", "2025-10-31"),
            "suspension_half_unit": self.both(self.preview, E_SUSP, *FEB),
            "rate6_small": self.both(self.preview, E_RATE6, *FEB),
            "rate6_large": self.both(self.preview, E_RATE6, "2026-03-01", "2026-03-31"),
        }
        o = {k: v["oracle"]["rating"] for k, v in out.items()}
        large = Decimal(101) * Decimal("0.123456") + Decimal(1_000_000 - 101) * Decimal("0.123456") * Decimal("1.5")
        ok = (all(v["oracle"] == v["mongo"] for v in out.values())
              and o["half_cent_tier"]["billable_units"] == "101" and o["half_cent_tier"]["overage_amount"] == "5.56"
              and o["suspension_half_unit"]["billable_units"] == "3" and o["suspension_half_unit"]["overage_amount"] == "0.14"
              and o["rate6_small"]["overage_amount"] == "0.12"
              and Decimal(o["rate6_large"]["overage_amount"]) == large.quantize(Decimal("0.01")))
        self.record("EDGE-U3-004", "money edges: ROUND half away from zero on the 2-dp overage (5.555 -> 5.56) and on the suspension-prorated units (2.5 -> 3, "
                    "overage 0.28 * 0.5 -> 0.14), a NUMBER(12,6) rate (0.123456) small and large (185177.77); identical on both", out, ok)

    def probe_finalize_atomicity(self):
        before = self.period_state(E_NOSUB, FEB[0])
        audit_before = self.audit_tail(f"compute tenant={E_NOSUB}")
        resp = self.both(self.finalize, E_NOSUB, *FEB)
        after = self.period_state(E_NOSUB, FEB[0])
        audit_after = self.audit_tail(f"compute tenant={E_NOSUB}")
        out = {"response": resp, "periods_before": before, "periods_after": after, "audit_compute_rows_before": audit_before, "audit_compute_rows_after": audit_after}
        ok = (all(r["status"] != 200 for r in resp.values()) and before == {"oracle": [], "mongo": []} and after == before
              and audit_after["oracle"] == audit_before["oracle"] + 1 and audit_after["mongo"] == audit_before["mongo"] + 1)
        self.record("EDGE-U3-005", "sp_finalize_rating for a tenant with no covering subscription fails on both (rating_results.subscription_id NOT NULL / port's "
                    "ValueError) and leaves no rating_periods row/document (statement-level rollback / aborted transaction); the autonomous log_msg "
                    "'compute' audit row survives the rollback on both", out, ok)

    def probe_refinalize(self):
        out = {}
        out["first"] = {"response": self.both(self.finalize, E_PLAN, "2026-04-01", "2026-04-30")}
        state1 = self.period_state(E_PLAN, "2026-04-01")
        self.reload(U3)  # Oracle finalised twice (once per backend) -> reload so mongo starts from the same rows the Oracle side ends with
        self.event(E_PLAN, "2026-04-20 10:00:00", 50)
        self.reload(U3)
        out["second"] = {"response": self.both(self.finalize, E_PLAN, "2026-04-01", "2026-04-30")}
        state2 = self.period_state(E_PLAN, "2026-04-01")
        out["after_first"], out["after_second"] = state1, state2
        md5 = self.backends["mongo"].f_md5_uuid
        o1, o2 = state1["oracle"][0], state2["oracle"][0]
        fresh_ok = (len(state1["oracle"]) == len(state1["mongo"]) == 1 and state1["oracle"] == state1["mongo"] and state2["oracle"] == state2["mongo"]
                    and o1["period_id"] == md5(f"{E_PLAN}2026-04-01") and o1["result_id"] == md5(o1["period_id"])
                    and int(o2["used"]) == int(o1["used"]) + 50 and int(o2["billable"]) == max(int(o2["used"]) - int(o2["rollover"]) - int(o2["quota"]), 0)
                    and o2["quota"] == o1["quota"] and o2["created"] == o1["created"]
                    and all(r["status"] == 200 for r in out["first"]["response"].values()) and all(r["status"] == 200 for r in out["second"]["response"].values()))
        self.record("EDGE-U3-006", "re-finalising a period the module created (md5 ids): INSERT falls back to UPDATE on both, used/billable/rollover refreshed, "
                    "quota/subscription/created_at kept, result id = md5(period id); identical on both", out, fresh_ok)

        # Seeded periods carry hand-assigned ids (40000000-...), not f_md5_uuid(tenant || start): Oracle's INSERT hits uq_rating_periods, falls
        # back to the UPDATE, then INSERTs rating_results with period_id = the md5 id that does not exist -> ORA-02291, statement rolled back.
        seeded = {"response": None}
        seeded["before"] = self.period_state(SEEDED_TENANT, "2026-01-01")  # covered by the seeded subscription (starts 2026-01-01)
        seeded["response"] = self.both(self.finalize, SEEDED_TENANT, "2026-01-01", "2026-01-31")
        seeded["after"] = self.period_state(SEEDED_TENANT, "2026-01-01")
        seeded["seeded_period_id_is_md5"] = seeded["before"]["oracle"][0]["period_id"] == md5(f"{SEEDED_TENANT}2026-01-01")
        same_outcome = (seeded["response"]["oracle"]["status"] == seeded["response"]["mongo"]["status"]
                        and (seeded["after"]["oracle"] == seeded["before"]["oracle"]) == (seeded["after"]["mongo"] == seeded["before"]["mongo"]))
        self.record("EDGE-U3-007", "re-finalising a seeded period whose id is not f_md5_uuid(tenant || period_start) (all 3 live rating_periods are such rows): "
                    "Oracle fails with ORA-02291 and changes nothing; the port must fail the same way or the backends diverge", seeded, same_outcome,
                    notes=None if same_outcome else "DIVERGENCE: Oracle 500 (sp_finalize_rating recomputes v_period_id = f_md5_uuid(tenant || start) after the "
                    "DUP_VAL_ON_INDEX fallback, so its rating_results INSERT hits fk_rr_period: ORA-02291), rows unchanged; the port finalises by the existing "
                    "document's _id and returns 200, recomputing the embedded result in place. Repro: POST /api/rating/finalize "
                    f"{{tenant_id: {SEEDED_TENANT}, period_start: 2026-01-01, period_end: 2026-01-31}} on each backend after tp-u3-load")
        self.fixture.reset()  # puts the seeded period back on both sides (mongo reloaded from Oracle)

    def probe_trigger_equivalents(self):
        mongo = self.backends["mongo"]
        out = {"oracle": {}, "mongo": {}}
        eid = f"{EDGE_PREFIX}0000000000f1"
        out["oracle"]["units_zero"] = self.oracle_error(f"INSERT INTO usage_events (id, tenant_id, occurred_at, units, kind_cd) VALUES ('{eid}', '{E_PLAN}', SYSTIMESTAMP, 0, 1)")
        out["oracle"]["units_null"] = self.oracle_error(f"INSERT INTO usage_events (id, tenant_id, occurred_at, units, kind_cd) VALUES ('{eid}', '{E_PLAN}', SYSTIMESTAMP, NULL, 1)")
        out["oracle"]["unknown_kind"] = self.oracle_error(f"INSERT INTO usage_events (id, tenant_id, occurred_at, units, kind_cd) VALUES ('{eid}', '{E_PLAN}', SYSTIMESTAMP, 1, 9)")
        self.use("mongo")
        for key, units, kind in (("units_zero", 0, "api"), ("units_null", None, "api"), ("unknown_kind", 1, "gpu")):
            try:
                mongo.record_usage_event(eid, E_PLAN, "2026-02-10T10:00:00Z", units, kind)
                out["mongo"][key] = "accepted"
            except mongo.UsageEventRejected as exc:
                out["mongo"][key] = f"UsageEventRejected: {exc}"
        out["mongo"]["kind_case_insensitive"] = mongo._usage_kind("API")
        out["mongo"]["event_after_rejections"] = self.mdb.usage_events.count_documents({"_id": eid})
        # facade validation is identical before either estate is reached
        bad = {"event_id": f"{EDGE_PREFIX}0000000000f2", "tenant_id": E_PLAN, "kind": "gpu", "units": 1, "occurred_at": "2026-02-10T10:00:00Z"}
        facade = {}
        for name in ("oracle", "mongo"):
            _b, client = self.use(name)
            os.environ["USAGE_INTERNAL_TOKEN"] = "edge-u3"
            facade[name] = {payload_name: client.post("/internal/usage/events", json=payload, headers={"X-Internal-Token": "edge-u3"}).status_code
                            for payload_name, payload in (("unknown_kind", bad), ("units_zero", {**bad, "kind": "api", "units": 0}))}
        out["facade_status"] = facade
        # a USAGE_KIND code beyond fn_usage_summary's DECODE(1,2,3): the trigger accepts it, the summary says UNKNOWN, the event list shows its code_desc
        self.oracle(["INSERT INTO codes (code_type, code_val, code_desc) VALUES ('USAGE_KIND', 4, 'gpu')"])
        self.reload(["codes"])
        self.event(E_PLAN, "2026-07-10 10:00:00", 9, 4)
        self.reload(U3)
        out["kind_4_gpu"] = self.both(self.usage, E_PLAN, "2026-07-01", "2026-07-31")
        o = out["kind_4_gpu"]["oracle"]
        ok = (out["oracle"]["units_zero"] == 20001 and out["oracle"]["units_null"] == 20001 and out["oracle"]["unknown_kind"] == 20002
              and out["mongo"]["units_zero"].startswith("UsageEventRejected: units must be > 0") and out["mongo"]["units_null"].startswith("UsageEventRejected: units must be > 0")
              and out["mongo"]["unknown_kind"] == "UsageEventRejected: unknown usage kind gpu" and out["mongo"]["kind_case_insensitive"] == 1
              and out["mongo"]["event_after_rejections"] == 0 and facade["oracle"] == facade["mongo"] == {"unknown_kind": 400, "units_zero": 400}
              and o == out["kind_4_gpu"]["mongo"] and o["summary"] == [{"event_count": "1", "kind": "UNKNOWN", "units": "9"}] and o["events"][0][3] == "gpu")
        self.record("EDGE-U3-008", "TRG_USAGE_EVENTS_CHECK equivalents: units 0/NULL (ORA-20001) and an unknown kind (ORA-20002) are rejected by the port with "
                    "the same messages and nothing written; kind lookup case-insensitive like LOWER(code_desc); a USAGE_KIND code 4 'gpu' outside the "
                    "DECODE is 'UNKNOWN' in the summary and 'gpu' in the event list on both", out, ok)

    def probe_loader_shapes_and_local_recon(self, out_path: Path):
        pid = f"{EDGE_PREFIX}0000000000c9"
        self.oracle([f"INSERT INTO rating_periods (id, tenant_id, period_start, period_end) VALUES ('{pid}', '{E_RATE6}', DATE '2026-08-01', DATE '2026-08-31')",
                     f"UPDATE rating_results SET overage_amount = 9999999999.99 WHERE id = '{EDGE_PREFIX}0000000000d1'",
                     f"UPDATE rating_results SET overage_amount = 0.01 WHERE id = '{EDGE_PREFIX}0000000000d2'",
                     # recon's census_delta.USAGE_EVENTS requires source_rows == census + fixture_only_pks: drop the probe events before the local run
                     f"DELETE FROM usage_events WHERE tenant_id LIKE '{EDGE_PREFIX}%'"])
        rc = self.reload(U3)
        no_result = self.mdb.rating_periods.find_one({"_id": pid})
        d1 = self.mdb.rating_periods.find_one({"_id": f"{EDGE_PREFIX}0000000000c1"})
        d2 = self.mdb.rating_periods.find_one({"_id": f"{EDGE_PREFIX}0000000000c2"})
        cmd = [sys.executable, str(self.root / "migration/billing/recon/recon.py"), "run", "--mode", "local",
               "--collections", ",".join(U3), "--oracle-dsn-env", self.oracle_dsn_env, "--mongo-uri-env", self.mongo_uri_env,
               "--mongo-db", self.fixture.database, "--out", str(out_path)]
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=self.root)
        report = json.loads(out_path.read_text()) if out_path.exists() else {}
        out = {"loader_exit": rc, "period_without_result_has_no_result_key": no_result is not None and "result" not in no_result,
               "overage_max_decimal128": None if d1 is None else str(d1["result"]["overageAmount"]), "overage_min_decimal128": None if d2 is None else str(d2["result"]["overageAmount"]),
               "overage_type": None if d1 is None else type(d1["result"]["overageAmount"]).__name__,
               "local_recon": {"exit": proc.returncode, "verdict": report.get("verdict"), "run_mode": report.get("run_mode"), "merge_evidence": report.get("merge_evidence"),
                               "checks": report.get("summary", {}).get("checks"), "failed": [c["id"] for c in report.get("checks", []) if c.get("result") not in ("pass", None)],
                               "stderr": proc.stderr.strip().splitlines()[-2:]}}
        ok = (rc == 0 and out["period_without_result_has_no_result_key"] and out["overage_max_decimal128"] == "9999999999.99" and out["overage_min_decimal128"] == "0.01"
              and out["overage_type"] == "Decimal128" and proc.returncode == 0 and report.get("verdict") == "pass" and report.get("merge_evidence") is False)
        self.record("EDGE-U3-009", "loader embedding: a rating period without a result carries no `result` subdocument, NUMBER(12,2) overage extremes load as exact "
                    "Decimal128; recon.py --mode local over usage_events,rating_periods passes with the edge rows present", {"mongo": out}, ok)

    def probe_write_scope(self):
        scratch = "ow_tp_billing_u3_scope_probe"
        dbs_before = sorted(self.fixture.mongo.list_database_names())
        try:
            rc = self.reload(U3, mongo_db=scratch)
            scratch_colls = sorted(self.fixture.mongo[scratch].list_collection_names())
            indexes = {c: sorted(self.fixture.mongo[scratch][c].index_information()) for c in scratch_colls}
            dbs_after = sorted(self.fixture.mongo.list_database_names())
        finally:
            self.fixture.mongo.drop_database(scratch)
        _b, client = self.use("mongo")
        os.environ["USAGE_INTERNAL_TOKEN"] = "edge-u3"
        c0 = self.counts()
        self.usage(client, E_PLAN, *FEB)
        self.preview(client, E_PLAN, *FEB)
        c1 = self.counts()
        self.finalize(client, E_PLAN, "2026-09-01", "2026-09-30")
        c2 = self.counts()
        client.post("/internal/usage/events", json={"event_id": f"{EDGE_PREFIX}0000000000f3", "tenant_id": E_PLAN, "kind": "api", "units": 1,
                                                    "occurred_at": "2026-09-10T10:00:00Z"}, headers={"X-Internal-Token": "edge-u3"})
        c3 = self.counts()
        dbs_final = sorted(self.fixture.mongo.list_database_names())
        diff = lambda a, b: {k: b.get(k, 0) - a.get(k, 0) for k in set(a) | set(b) if a.get(k, 0) != b.get(k, 0)}  # noqa: E731
        out = {"loader_exit": rc, "scratch_collections": scratch_colls, "indexes": indexes,
               "other_databases_touched": sorted((set(dbs_after) | set(dbs_final)) - set(dbs_before) - {scratch}),
               "reads_changed": diff(c0, c1), "finalize_changed": diff(c1, c2), "ingest_changed": diff(c2, c3)}
        ok = (rc == 0 and scratch_colls == sorted(U3) and not out["other_databases_touched"] and out["reads_changed"] == {"billing_audit_log": 2}
              and out["finalize_changed"] == {"rating_periods": 1, "billing_audit_log": 2} and out["ingest_changed"] == {"usage_events": 1})
        self.record("EDGE-U3-010", "write scope: the U3 loader writes only usage_events and rating_periods (plus spec indexes) in the target database and touches "
                    "no other database; on the Mongo backend GET /usage + preview write only log_msg audit rows (2, as PKG_RATING does), finalize writes one "
                    "rating_periods document + 2 audit rows, ingest writes one usage_events document and nothing else", {"mongo": out}, ok,
                    notes="billing_audit_log is PKG_OW_UTIL.log_msg's collection (U1 port, wave 1); U5 owns its load")

    def cleanup(self):
        self.fixture.reset()
        self.oracle([
            f"DELETE FROM rating_results WHERE period_id IN (SELECT id FROM rating_periods WHERE tenant_id LIKE '{EDGE_PREFIX}%')",
            f"DELETE FROM rating_periods WHERE tenant_id LIKE '{EDGE_PREFIX}%'",
            f"DELETE FROM usage_events WHERE tenant_id LIKE '{EDGE_PREFIX}%'",
            f"DELETE FROM subscriptions WHERE tenant_id LIKE '{EDGE_PREFIX}%'",
            f"DELETE FROM tenants WHERE id LIKE '{EDGE_PREFIX}%'",
            f"DELETE FROM plans WHERE id LIKE '{EDGE_PREFIX}%'",
            "DELETE FROM codes WHERE code_type = 'USAGE_KIND' AND code_val = 4",
        ])
        self.reload(["codes", "plans", "tenants", "subscriptions"] + U3)
        left = {t: int(self.oracle([], fetch=f"SELECT COUNT(*) FROM {t} WHERE {col} LIKE '{EDGE_PREFIX}%'")[0][0])
                for t, col in (("tenants", "id"), ("plans", "id"), ("subscriptions", "tenant_id"), ("usage_events", "tenant_id"), ("rating_periods", "tenant_id"))}
        left["codes_usage_kind_4"] = int(self.oracle([], fetch="SELECT COUNT(*) FROM codes WHERE code_type = 'USAGE_KIND' AND code_val = 4")[0][0])
        left["mongo_edge_docs"] = sum(self.mdb[c].count_documents({"tenantId": {"$regex": f"^{EDGE_PREFIX}"}}) for c in U3 + ["subscriptions"]) \
            + self.mdb.tenants.count_documents({"_id": {"$regex": f"^{EDGE_PREFIX}"}}) + self.mdb.plans.count_documents({"_id": {"$regex": f"^{EDGE_PREFIX}"}})
        self.record("EDGE-U3-011", "fixture restored: static tenants reset (rating_parity.Fixture.reset), no probe tenants/plans/codes/events/periods left on either side",
                    {"both": left}, all(v == 0 for v in left.values()))

    # ---- driver ---------------------------------------------------------------------------------
    def run(self, out_dir: Path):
        print("resetting the rating baseline and reloading U3 from the Oracle fixture (batch loader) ...")
        self.fixture.reset()
        self.plant()
        try:
            self.probe_empty_and_no_plan()
            self.probe_window_edges()
            self.probe_add_months_window()
            self.probe_money_rounding()
            self.probe_finalize_atomicity()
            self.probe_refinalize()
            self.probe_trigger_equivalents()
            self.probe_loader_shapes_and_local_recon(out_dir / "U3.verify.edge_local.recon.json")
            self.probe_write_scope()
        finally:
            self.cleanup()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--repo-root", default=str(HERE.parents[4]), help="checkout whose loader/backends/recon to exercise (the PR head)")
    p.add_argument("--oracle-dsn-env", default="OW_TP_ORACLE_FIXTURE_DSN")
    p.add_argument("--mongo-uri-env", default="OW_TP_MONGO_FIXTURE_URI")
    p.add_argument("--out", default=str(HERE / "U3.verify.edge_probes.json"))
    args = p.parse_args(argv)
    root = Path(args.repo_root).resolve()
    setup_paths(root)
    os.environ["MONGODB_ATLAS_URI"] = os.environ[args.mongo_uri_env]  # process-local: the fixture mongod
    os.environ.setdefault("ORACLE_PORT", "52521")

    probes = Probes(root, args.oracle_dsn_env, args.mongo_uri_env)
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=root).stdout.strip()
    try:
        probes.run(Path(args.out).parent)
    except Exception as exc:  # keep the probes that did run as evidence
        probes.record("EDGE-U3-ABORT", f"probe run aborted: {type(exc).__name__}: {str(exc)[:200]}", {}, False)
    report = {
        "kind": "u3-edge-probes", "unit": "U3", "run_mode": "fixture", "merge_evidence": False,
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
