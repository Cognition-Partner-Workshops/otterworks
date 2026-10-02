#!/usr/bin/env python3
"""UNT-22 edge-case probes for U4 (invoicing: INVOICES with embedded INVOICE_LINES, CREDIT_NOTES, the INVOICE_HEADER /
INVOICE_LINE report feed as invoice_feed + invoice_feed_quarantine) on the local fixtures only. Drives PKG_INVOICING on the
Oracle Free fixture and the Mongo port (loopback mongod, reloaded from the Oracle fixture by the batch's own loader) through
the same inputs past invoicing_parity.py: a tenant without a covering plan (NULL preview amounts, issue fails atomically),
the half-cent tax tie (g_tax/2 unrounded in the preview, rounded half-away-from-zero into NUMBER(12,2) lines, the charge cap
computed from the unrounded tax), the credit-note burn-down running counter across three notes and a second issue over the
burned balance (same invoice id, issued_at kept, lines rebuilt), sp_issue_invoice atomicity when the credit burn-down fails
after the period/header/lines were written (forced on both estates; the autonomous 'finalized' audit row survives, no
'issued' row), issuing against a hand-seeded rating period (d-refinalize-seeded-period's consequence for invoices),
GET /invoices ordering ties and an INV_STATUS code outside CODES, feed rows past the gate (orphan and NULL-parent lines,
an unknown status / line type, a NULL header total, an unparsable DD-MON-YY date, a line on another batch) through the
loader, both month-end / reconciliation reports and the CUSTBILL extract, local recon over the edge rows, and write scope.

    TZ=UTC LC_ALL=C OW_TP_ORACLE_FIXTURE_DSN=... OW_TP_MONGO_FIXTURE_URI=... \
      uv run --no-project --with oracledb==2.5.1 --with pymongo==4.10.1 --with flask==3.1.1 \
        --with pyyaml==6.0.2 --with jsonschema==4.25.1 --with rfc3339-validator==0.1.4 \
        python3 migration/billing/waves/wave2/verify/u4_edge_probes.py --repo-root <PR checkout>

The only DDL is a probe trigger on the fixture's CREDIT_NOTES (forced burn-down failure), dropped in cleanup; the Mongo
side uses a collMod validator on the fixture's credit_notes for the same purpose, cleared by the reload. Refuses
non-loopback hosts on either side (via invoicing_parity.Fixture). Fixture evidence only, never merge evidence.
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
U4 = ["credit_notes", "invoice_feed", "invoice_feed_quarantine", "invoices"]
P = "e4000000-0000-0000-0000-"
E_NOSUB = f"{P}0000000000e0"   # no subscription at all
E_TAX = f"{P}0000000000e1"     # 4.00 plan: tax 0.33, each half 0.165 (the tie), one 10.00 credit note
E_BURN = f"{P}0000000000e2"    # STARTER, three 20.00 credit notes on consecutive days
E_ATOM = f"{P}0000000000e3"    # STARTER, one credit note; its burn-down is forced to fail on both estates
E_SCOPE = f"{P}0000000000e4"   # STARTER, no credit; write-scope counting
PLAN_FEE4 = f"{P}00000000a001"
STARTER = "10000000-0000-0000-0000-000000000001"
FEB = ("2026-02-01", "2026-02-28")
SEEDED_TENANT = "00000000-0000-0000-0000-000000000001"
SEEDED_JAN = ("2026-01-01", "2026-01-31")
SEEDED_JAN_PERIOD = "40000000-0000-0000-0000-000000000002"
TENANT2 = "00000000-0000-0000-0000-000000000002"
SEEDED_INVOICE = "60000000-0000-0000-0000-000000000001"
FEED_HDR = f"{P}0000000000f1"
FEED_NOHDR = f"{P}0000000000f9"
TRIGGER = "trg_edge_u4_atom"


def setup_paths(root: Path):
    for rel in (("migration", "billing", "loaders"), ("migration", "billing", "recon"), ("migration", "billing", "waves", "wave2"),
                ("procs", "harness"), ("services", "legacy-billing", "app"), ("etl", "legacy-extra", "tools")):
        sys.path.insert(0, str(root.joinpath(*rel)))


def jsonable(value):
    return json.loads(json.dumps(value, default=str))


def money(value):
    if value is None:
        return None
    if hasattr(value, "to_decimal"):
        value = value.to_decimal()
    return str(Decimal(str(value)).quantize(Decimal("0.01")))


def day(value):
    return None if value is None else value.date().isoformat() if hasattr(value, "date") else str(value)[:10]


class Probes:
    def __init__(self, root: Path, oracle_dsn_env: str, mongo_uri_env: str):
        import oracledb
        import invoicing_parity
        from backends import mongo as mongo_backend
        from backends import oracle as oracle_backend
        from app import app
        import reports

        oracledb.defaults.fetch_decimals = True
        self.root, self.oracledb = root, oracledb
        self.parity = invoicing_parity
        self.fixture = invoicing_parity.Fixture(oracle_dsn_env, mongo_uri_env)
        self.oracle_dsn_env, self.mongo_uri_env = oracle_dsn_env, mongo_uri_env
        self.backends = {"oracle": oracle_backend, "mongo": mongo_backend}
        self.app = app
        self.batch_no = reports.ns_batch_no(invoicing_parity.NS)
        self.mdb = self.fixture.mongo[self.fixture.database]
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

    def oracle_quiet(self, statement):
        try:
            self.oracle([statement])
            return None
        except self.oracledb.Error as exc:
            return exc.args[0].code if exc.args and hasattr(exc.args[0], "code") else str(exc)[:80]

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

    def both(self, fn, *args):
        out = {}
        for name in ("oracle", "mongo"):
            _backend, client = self.use(name)
            out[name] = fn(client, *args)
        return out

    def preview(self, client, tenant, start, end):
        resp = client.get(f"/api/invoices/{tenant}/preview", query_string={"period_start": start, "period_end": end})
        return {"status": resp.status_code, "lines": resp.get_json()}

    def issue(self, client, tenant, start, end):
        try:
            resp = client.post(f"/api/invoices/{tenant}/issue", data={"period_start": start, "period_end": end})
            return {"status": resp.status_code, "body": resp.get_json()}
        except Exception as exc:  # the app has no error handler: the test client re-raises what the backend raised
            return {"status": "exception", "error": type(exc).__name__, "detail": str(exc)[:160]}

    def lines(self, client, invoice_id):
        resp = client.get(f"/api/invoices/{invoice_id}/lines")
        return {"status": resp.status_code, "lines": resp.get_json()}

    def facade_invoices(self, client, tenant):
        headers = {"X-User-ID": tenant, "X-User-Email": f"{tenant}@example.com"}
        resp = client.get("/api/v1/billing/invoices", headers=headers)
        return {"status": resp.status_code, "body": resp.get_json()}

    def facade_lines(self, client, tenant, invoice_id):
        headers = {"X-User-ID": tenant, "X-User-Email": f"{tenant}@example.com"}
        resp = client.get(f"/api/v1/billing/invoices/{invoice_id}/lines", headers=headers)
        return {"status": resp.status_code, "body": resp.get_json()}

    def state(self, tenant):
        """Invoices (+lines), rating periods and credit notes of a tenant, same shape on both estates."""
        inv = self.oracle([], fetch="""SELECT id, period_id, TO_CHAR(issued_at, 'YYYY-MM-DD'), subtotal, tax, total, status_cd FROM invoices
                                        WHERE tenant_id = :1 ORDER BY id""", binds=(tenant,))
        oracle = {"invoices": []}
        for r in inv:
            lines = self.oracle([], fetch="SELECT id, line_no, line_type, description, amount FROM invoice_lines WHERE invoice_id = :1 ORDER BY line_no",
                                binds=(r[0],))
            oracle["invoices"].append({"id": r[0], "period_id": r[1], "issued_at": r[2], "subtotal": money(r[3]), "tax": money(r[4]), "total": money(r[5]),
                                       "status_cd": int(r[6]), "lines": [{"id": line[0], "line_no": int(line[1]), "line_type": line[2], "description": line[3],
                                                                          "amount": money(line[4])} for line in lines]})
        oracle["periods"] = [{"id": r[0], "start": r[1], "has_result": int(r[2]) > 0} for r in self.oracle(
            [], fetch="""SELECT rp.id, TO_CHAR(rp.period_start, 'YYYY-MM-DD'), (SELECT COUNT(*) FROM rating_results rr WHERE rr.period_id = rp.id)
                           FROM rating_periods rp WHERE rp.tenant_id = :1 ORDER BY rp.period_start""", binds=(tenant,))]
        oracle["credit_notes"] = [{"id": r[0], "issued_on": r[1], "remaining": money(r[2])} for r in self.oracle(
            [], fetch="SELECT id, TO_CHAR(issued_on, 'YYYY-MM-DD'), remaining_amount FROM credit_notes WHERE tenant_id = :1 ORDER BY issued_on, id", binds=(tenant,))]
        mongo = {"invoices": [], "periods": [], "credit_notes": []}
        for d in self.mdb.invoices.find({"tenantId": tenant}, sort=[("_id", 1)]):
            mongo["invoices"].append({"id": d["_id"], "period_id": d.get("periodId"), "issued_at": day(d.get("issuedAt")), "subtotal": money(d.get("subtotal")),
                                      "tax": money(d.get("tax")), "total": money(d.get("total")), "status_cd": d.get("statusCd"),
                                      "lines": [{"id": line.get("id"), "line_no": int(line.get("lineNo")), "line_type": line.get("lineType"),
                                                 "description": line.get("description"), "amount": money(line.get("amount"))}
                                                for line in sorted(d.get("lines") or [], key=lambda x: int(x.get("lineNo", 0)))]})
        for d in self.mdb.rating_periods.find({"tenantId": tenant}, sort=[("periodStart", 1)]):
            mongo["periods"].append({"id": d["_id"], "start": day(d.get("periodStart")), "has_result": isinstance(d.get("result"), dict)})
        for d in self.mdb.credit_notes.find({"tenantId": tenant}, sort=[("issuedOn", 1), ("_id", 1)]):
            mongo["credit_notes"].append({"id": d["_id"], "issued_on": day(d.get("issuedOn")), "remaining": money(d.get("remainingAmount"))})
        return {"oracle": oracle, "mongo": mongo}

    def audit(self, module, needle):
        oracle = self.oracle([], fetch="SELECT COUNT(*) FROM billing_audit_log WHERE module = :1 AND message LIKE :2", binds=(module, f"%{needle}%"))[0][0]
        mongo = self.mdb.billing_audit_log.count_documents({"module": module, "message": {"$regex": needle}})
        return {"oracle": int(oracle), "mongo": int(mongo)}

    def audit_delta(self, before, after):
        return {k: {"oracle": after[k]["oracle"] - before[k]["oracle"], "mongo": after[k]["mongo"] - before[k]["mongo"]} for k in before}

    def audits(self, tenant, invoice_id):
        return {"compute": self.audit("RATING", f"compute tenant={tenant}"), "finalized": self.audit("RATING", "finalized period="),
                "issued": self.audit("INVOICING", f"issued invoice={invoice_id}")}

    def counts(self, db=None):
        d = self.fixture.mongo[db or self.fixture.database]
        return {name: d[name].count_documents({}) for name in sorted(d.list_collection_names())}

    def ids(self, tenant, start):
        period_id = self.parity.md5_uuid(f"{tenant}{start}")
        return period_id, self.parity.md5_uuid(f"{period_id}invoice")

    def record(self, pid, description, per_backend, passed, notes=None, **extra):
        entry = {"id": pid, "description": description, "backends": jsonable(per_backend), "pass": bool(passed)}
        if notes:
            entry["notes"] = notes
        entry.update(extra)
        self.results.append(entry)
        print(f"{pid}: {'pass' if passed else 'FAIL'} - {description[:110]}")
        return entry

    # ---- fixture setup -----------------------------------------------------------------------
    def plant(self):
        subs = [(E_TAX, PLAN_FEE4, "b1"), (E_BURN, STARTER, "b2"), (E_ATOM, STARTER, "b3"), (E_SCOPE, STARTER, "b4")]
        self.oracle([
            f"INSERT INTO plans (id, code, tier_cd, monthly_fee, included_units, overage_rate, active_yn) VALUES ('{PLAN_FEE4}', 'EDGE-U4-FEE4', 1, 4.00, 100, 0.055, 'N')",
            *[f"INSERT INTO tenants (id, name, tax_exempt_yn, status_cd) VALUES ('{t}', 'Edge U4 {n}', 'N', 10)"
              for t, n in ((E_NOSUB, "no subscription"), (E_TAX, "tax tie"), (E_BURN, "burn-down"), (E_ATOM, "atomicity"), (E_SCOPE, "scope"))],
            *[f"INSERT INTO subscriptions (id, tenant_id, plan_id, starts_on, ends_on, status_cd, suspended_on) VALUES ('{P}0000000000{s}', '{t}', '{p}', DATE '2025-01-01', NULL, 10, NULL)"
              for t, p, s in subs],
            f"INSERT INTO credit_notes (id, tenant_id, issued_on, amount, remaining_amount) VALUES ('{P}0000000000c1', '{E_TAX}', DATE '2026-01-10', 10.00, 10.00)",
            f"INSERT INTO credit_notes (id, tenant_id, issued_on, amount, remaining_amount) VALUES ('{P}0000000000c2', '{E_BURN}', DATE '2026-01-01', 20.00, 20.00)",
            f"INSERT INTO credit_notes (id, tenant_id, issued_on, amount, remaining_amount) VALUES ('{P}0000000000c3', '{E_BURN}', DATE '2026-01-02', 20.00, 20.00)",
            f"INSERT INTO credit_notes (id, tenant_id, issued_on, amount, remaining_amount) VALUES ('{P}0000000000c4', '{E_BURN}', DATE '2026-01-03', 20.00, 20.00)",
            f"INSERT INTO credit_notes (id, tenant_id, issued_on, amount, remaining_amount) VALUES ('{P}0000000000c5', '{E_ATOM}', DATE '2026-01-05', 10.00, 10.00)",
        ])
        self.reload(["plans", "tenants", "subscriptions", "credit_notes"])

    # ---- probes --------------------------------------------------------------------------
    def probe_no_plan(self):
        _period_id, invoice_id = self.ids(E_NOSUB, FEB[0])
        before, a0 = self.state(E_NOSUB), self.audits(E_NOSUB, invoice_id)
        preview = self.both(self.preview, E_NOSUB, *FEB)
        a1 = self.audits(E_NOSUB, invoice_id)
        issue = self.both(self.issue, E_NOSUB, *FEB)
        after, a2 = self.state(E_NOSUB), self.audits(E_NOSUB, invoice_id)
        out = {"preview": preview, "issue": issue, "state_before": before, "state_after": after,
               "audit_delta_preview": self.audit_delta(a0, a1), "audit_delta_issue": self.audit_delta(a1, a2)}
        null_rows = preview["oracle"]["lines"]
        ok = (preview["oracle"]["status"] == 200 and preview["oracle"]["lines"] == preview["mongo"]["lines"] and len(null_rows) == 5
              and null_rows[0]["amount"] is None and null_rows[0]["description"] is None and null_rows[2]["amount"] is None and null_rows[4]["total"] == "0"
              and all(r["status"] != 200 for r in issue.values()) and before == after == {"oracle": {"invoices": [], "periods": [], "credit_notes": []},
                                                                                            "mongo": {"invoices": [], "periods": [], "credit_notes": []}}
              and out["audit_delta_preview"]["compute"] == {"oracle": 1, "mongo": 1} and out["audit_delta_issue"]["issued"] == {"oracle": 0, "mongo": 0}
              and out["audit_delta_issue"]["compute"]["oracle"] == out["audit_delta_issue"]["compute"]["mongo"])
        self.record("EDGE-U4-001", "tenant without a covering subscription: fn_invoice_preview returns the five rows with NULL plan/overage/tax amounts and a NULL "
                    "plan description, credit applied 0, identical on both; sp_issue_invoice fails on both (sp_finalize_rating's rating_results NOT NULL / the "
                    "port's ValueError) leaving no period, invoice or line; only the autonomous 'compute' audit rows are written", out, ok)

    def probe_tax_tie(self):
        period_id, invoice_id = self.ids(E_TAX, FEB[0])
        preview = self.both(self.preview, E_TAX, *FEB)
        a0 = self.audits(E_TAX, invoice_id)
        issue = self.both(self.issue, E_TAX, *FEB)
        a1 = self.audits(E_TAX, invoice_id)
        state = self.state(E_TAX)
        lines = self.both(self.lines, invoice_id)
        out = {"preview": preview, "issue": issue, "state": state, "lines": lines, "audit_delta_issue": self.audit_delta(a0, a1)}
        o = state["oracle"]
        inv = o["invoices"][0] if o["invoices"] else {}
        ok = (preview["oracle"] == preview["mongo"] and preview["oracle"]["lines"][2]["amount"] == "0.165" and preview["oracle"]["lines"][4]["credit_applied"] == "4.33"
              and all(r["status"] == 200 for r in issue.values()) and state["oracle"] == state["mongo"] and lines["oracle"] == lines["mongo"]
              and inv.get("id") == invoice_id and inv.get("period_id") == period_id and inv.get("issued_at") == FEB[1]
              and [line["amount"] for line in inv.get("lines", [])] == ["4.00", "0.00", "0.17", "0.17", "-4.33"]
              and (inv.get("subtotal"), inv.get("tax"), inv.get("total")) == ("4.00", "0.34", "0.01")
              and o["credit_notes"] == [{"id": f"{P}0000000000c1", "issued_on": "2026-01-10", "remaining": "5.67"}]
              and o["periods"] == [{"id": period_id, "start": FEB[0], "has_result": True}]
              and out["audit_delta_issue"]["issued"] == {"oracle": 1, "mongo": 1} and out["audit_delta_issue"]["finalized"] == {"oracle": 1, "mongo": 1})
        self.record("EDGE-U4-002", "half-cent tax tie (4.00 plan: tax 0.33, g_tax/2 = 0.165): the preview carries the unrounded 0.165 on both; the issued lines "
                    "hold 0.17 twice (NUMBER(12,2) column rounding half away from zero == port _money), tax 0.34 while the charge cap is ROUND(4+0+0.33) = 4.33, "
                    "so a 10.00 credit note is burned by 4.33 (not 4.34) and the invoice totals 0.01; period/header/lines/credit note identical", out, ok)

    def probe_burn_down_and_reissue(self):
        period_id, invoice_id = self.ids(E_BURN, FEB[0])
        first = self.both(self.issue, E_BURN, *FEB)
        s1 = self.state(E_BURN)
        preview2 = self.both(self.preview, E_BURN, *FEB)
        second = self.both(self.issue, E_BURN, *FEB)
        s2 = self.state(E_BURN)
        out = {"first_issue": first, "state_after_first": s1, "preview_before_second": preview2, "second_issue": second, "state_after_second": s2}
        o1, o2 = s1["oracle"], s2["oracle"]
        inv1 = o1["invoices"][0] if o1["invoices"] else {}
        inv2 = o2["invoices"][0] if o2["invoices"] else {}
        ok = (all(r["status"] == 200 for r in {**first, **{f"2{k}": v for k, v in second.items()}}.values())
              and s1["oracle"] == s1["mongo"] and s2["oracle"] == s2["mongo"] and preview2["oracle"] == preview2["mongo"]
              and [n["remaining"] for n in o1["credit_notes"]] == ["0.00", "0.00", "6.96"] and (inv1.get("subtotal"), inv1.get("tax"), inv1.get("total")) == ("49.00", "4.04", "0.00")
              and [n["remaining"] for n in o2["credit_notes"]] == ["0.00", "0.00", "0.00"] and (inv2.get("subtotal"), inv2.get("tax"), inv2.get("total")) == ("49.00", "4.04", "46.08")
              and len(o2["invoices"]) == 1 and inv2.get("id") == invoice_id and inv2.get("issued_at") == inv1.get("issued_at") == FEB[1] and inv2.get("status_cd") == 20
              and [line["id"] for line in inv2.get("lines", [])] == [line["id"] for line in inv1.get("lines", [])] and len(inv2.get("lines", [])) == 5
              and inv2["lines"][4]["amount"] == "-6.96" and len(o2["periods"]) == 1)
        self.record("EDGE-U4-003", "credit burn-down running counter over three 20.00 notes (STARTER 49.00 + 4.04 tax = 53.04 cap): oldest two to 0.00, the third to "
                    "6.96, total 0.00; a second sp_issue_invoice over the burned balance keeps the invoice id and issued_at, re-sets status 20, rebuilds the five "
                    "lines with the same md5 ids (credit line -6.96), totals 46.08 and burns the last note to 0.00; identical on both", out, ok)

    def probe_issue_atomicity(self):
        period_id, invoice_id = self.ids(E_ATOM, FEB[0])
        self.oracle([f"""CREATE OR REPLACE TRIGGER {TRIGGER} BEFORE UPDATE ON credit_notes FOR EACH ROW
WHEN (new.tenant_id = '{E_ATOM}')
BEGIN
    RAISE_APPLICATION_ERROR(-20999, 'EDGE-U4 forced burn-down failure');
END;"""])
        self.mdb.command("collMod", "credit_notes", validator={"tenantId": {"$ne": E_ATOM}}, validationLevel="strict", validationAction="error")
        try:
            before, a0 = self.state(E_ATOM), self.audits(E_ATOM, invoice_id)
            issue = self.both(self.issue, E_ATOM, *FEB)
            after, a1 = self.state(E_ATOM), self.audits(E_ATOM, invoice_id)
        finally:
            self.oracle([f"DROP TRIGGER {TRIGGER}"])
            self.mdb.command("collMod", "credit_notes", validator={}, validationLevel="off")
        retry = self.both(self.issue, E_ATOM, *FEB)
        healed = self.state(E_ATOM)
        out = {"issue_forced_failure": issue, "state_before": before, "state_after": after, "audit_delta": self.audit_delta(a0, a1),
               "issue_after_removing_the_fault": retry, "state_after_retry": healed}
        ok = (all(r["status"] != 200 for r in issue.values()) and after == before and before["oracle"]["invoices"] == [] and before["oracle"]["periods"] == []
              and before["oracle"]["credit_notes"] == [{"id": f"{P}0000000000c5", "issued_on": "2026-01-05", "remaining": "10.00"}] and before["oracle"] == before["mongo"]
              and out["audit_delta"]["issued"] == {"oracle": 0, "mongo": 0} and out["audit_delta"]["finalized"] == {"oracle": 1, "mongo": 1}
              and out["audit_delta"]["compute"]["oracle"] == out["audit_delta"]["compute"]["mongo"] >= 1
              and all(r["status"] == 200 for r in retry.values()) and healed["oracle"] == healed["mongo"] and len(healed["oracle"]["invoices"]) == 1
              and healed["oracle"]["credit_notes"][0]["remaining"] == "0.00" and healed["oracle"]["invoices"][0]["total"] == "43.04")
        self.record("EDGE-U4-004", "sp_issue_invoice atomicity: with the credit-note burn-down forced to fail (fixture trigger on CREDIT_NOTES / collMod validator on "
                    "credit_notes) after the period, result, header and lines were written, both estates roll everything back (no rating_periods, invoices or "
                    "invoice_lines row/document, credit note untouched); the autonomous 'finalized' and 'compute' audit rows survive the rollback on both and "
                    "no 'issued' row is written; the same call succeeds once the fault is removed, identical on both", out, ok)

    def probe_seeded_period(self):
        period_id, invoice_id = self.ids(SEEDED_TENANT, SEEDED_JAN[0])
        before = self.state(SEEDED_TENANT)
        issue = self.both(self.issue, SEEDED_TENANT, *SEEDED_JAN)
        after = self.state(SEEDED_TENANT)
        listing = self.both(self.facade_invoices, SEEDED_TENANT)
        lines = self.both(self.facade_lines, SEEDED_TENANT, invoice_id)
        out = {"md5_period_id": period_id, "seeded_period_id": SEEDED_JAN_PERIOD, "issue": issue, "state_before": before, "state_after": after,
               "facade_invoices": listing, "facade_lines": lines}
        same = issue["oracle"]["status"] == issue["mongo"]["status"] and after["oracle"] == after["mongo"]
        m_inv = [i for i in after["mongo"]["invoices"] if i["id"] == invoice_id]
        dangling = bool(m_inv) and m_inv[0]["period_id"] == period_id and period_id not in [p["id"] for p in after["mongo"]["periods"]]
        self.record("EDGE-U4-005", "issuing against a hand-seeded rating period (tenant 1, Jan 2026, id 40000000-...-0002 != f_md5_uuid): Oracle fails in "
                    "sp_finalize_rating (ORA-02291) and writes nothing; the port (d-refinalize-seeded-period, keep-port) finalizes the seeded document in place "
                    "and then inserts an invoice whose periodId is the md5 id no rating_periods document has, so GET /invoices ($lookup+$unwind) hides it "
                    "while /invoices/<id>/lines serves it", out, same,
                    notes=None if same else ("behaviour difference downstream of the ruled EDGE-U3-007: the port issues the invoice (200) with a dangling periodId"
                                             f" ({'confirmed' if dangling else 'not observed'}); Oracle returns an error and leaves the tenant untouched"))

    def probe_facade_edges(self):
        unknown = f"{P}0000000000d1"
        self.oracle([f"INSERT INTO invoices (id, tenant_id, period_id, issued_at, subtotal, tax, total, status_cd) VALUES ('{unknown}', '{TENANT2}', "
                     f"'40000000-0000-0000-0000-000000000001', TIMESTAMP '2026-02-01 00:00:00', 1.00, 0.00, 1.00, 99)"])
        rc = self.reload(["invoices"])
        listing = self.both(self.facade_invoices, TENANT2)
        own_lines = self.both(self.facade_lines, TENANT2, unknown)
        missing = self.both(self.facade_lines, TENANT2, f"{P}0000000000d2")
        seeded_lines = self.both(self.facade_lines, TENANT2, SEEDED_INVOICE)
        out = {"loader_exit": rc, "invoices": listing, "lines_of_invoice_without_lines": own_lines, "lines_of_unknown_invoice": missing, "lines_seeded": seeded_lines}
        rows = listing["oracle"]["body"] if isinstance(listing["oracle"]["body"], list) else []
        ok = (rc == 0 and listing["oracle"] == listing["mongo"] and [r["invoice_id"] for r in rows] == [unknown, SEEDED_INVOICE] and rows[0]["status"] is None
              and own_lines["oracle"] == own_lines["mongo"] == {"status": 200, "body": []} and missing["oracle"]["status"] == missing["mongo"]["status"] == 404
              and seeded_lines["oracle"] == seeded_lines["mongo"] and seeded_lines["oracle"]["status"] == 200 and len(seeded_lines["oracle"]["body"]) == 2)
        self.record("EDGE-U4-006", "GET /invoices: an invoice with an INV_STATUS code outside CODES lists with status null (LEFT JOIN / $lookup) and an "
                    "issued_at tie orders by id DESC on both; lines of an owned invoice without lines -> 200 [], an unknown invoice -> 404, the seeded "
                    "invoice's two lines identical", out, ok)

    def probe_feed_edges(self, out_path: Path):
        b = self.batch_no
        hdr = "INSERT INTO invoice_header (invoice_id, invoice_no, cust_id, tenant_id, invoice_dt, due_dt, status_cd, total_amt, batch_no) VALUES "
        line = ("INSERT INTO invoice_line (line_id, invoice_no, invoice_id, cust_id, cust_no, cust_name, tenant_id, line_no, line_type_cd, item_desc, qty, "
                "unit_price, amount, tax_amt, invoice_dt, service_period, posted_yn, gl_acct_csv, batch_no, src_system) VALUES ")
        self.oracle([
            hdr + f"('{FEED_HDR}', 'EDGE-U4-000001', NULL, NULL, '31-FEB-26', NULL, 99, NULL, {b})",
            line + f"('{P}0000000000a1', 'EDGE-U4-000001', '{FEED_HDR}', NULL, NULL, NULL, NULL, 1, 7, 'edge unknown type', 1, 10.005, 10.005, NULL, '31-FEB-26', NULL, NULL, NULL, {b}, 'EDGE')",
            line + f"('{P}0000000000a2', 'EDGE-U4-000001', '{FEED_HDR}', NULL, NULL, NULL, NULL, 2, 1, 'edge other batch', 1, 1, 1.00, 0.10, '01-JAN-26', NULL, 'N', '1,2', 1, 'EDGE')",
            line + f"('{P}0000000000a3', 'EDGE-U4-GHOST-1', '{FEED_NOHDR}', NULL, NULL, NULL, NULL, 1, 1, 'edge orphan', 1, 5, 5.00, 0.50, '01-JAN-26', NULL, 'N', NULL, {b}, 'EDGE')",
            line + f"('{P}0000000000a4', 'EDGE-U4-GHOST-2', NULL, NULL, NULL, NULL, NULL, 1, 1, 'edge null parent', 1, 6, 6.00, 0.60, '01-JAN-26', NULL, 'N', NULL, {b}, 'EDGE')",
        ])
        c0 = self.counts()
        rc = self.reload(["invoice_feed", "invoice_feed_quarantine"])
        c1 = self.counts()
        doc = self.mdb.invoice_feed.find_one({"_id": FEED_HDR})
        q = list(self.mdb.invoice_feed_quarantine.find({"_id": {"$regex": f"^{P}"}}, sort=[("_id", 1)]))
        reports = self.both(lambda client: self.parity.reports_snapshot(client))
        rollups = {k: self.parity.report_rollups(v) for k, v in reports.items()}
        unknown_status = [r for r in rollups["oracle"]["by_status"] if r["status"] == "UNKNOWN(99)"]
        unknown_lines = [r for r in rollups["oracle"]["by_status_line_type"] if r["status"] == "UNKNOWN(99)"]
        custbill = {k: self.parity.custbill_extract(self.fixture, k) for k in ("oracle", "mongo")}
        cmd = [sys.executable, str(self.root / "migration/billing/recon/recon.py"), "run", "--mode", "local", "--collections", ",".join(U4),
               "--oracle-dsn-env", self.oracle_dsn_env, "--mongo-uri-env", self.mongo_uri_env, "--mongo-db", self.fixture.database, "--out", str(out_path)]
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=self.root)
        report = json.loads(out_path.read_text()) if out_path.exists() else {}
        failed = [c["id"] for c in report.get("checks", []) if c.get("result") not in ("pass", None)]
        out = {"loader_exit": rc, "feed_delta": {k: c1.get(k, 0) - c0.get(k, 0) for k in ("invoice_feed", "invoice_feed_quarantine")},
               "header_doc": {k: doc.get(k) for k in ("invoiceNo", "invoiceDt", "invoiceDate", "statusCd", "totalAmt", "batchNo")} if doc else None,
               "header_lines": [{k: l.get(k) for k in ("lineNo", "lineTypeCd", "amount", "taxAmt", "batchNo", "glAcctCsv")} for l in (doc or {}).get("lines", [])],
               "quarantine_docs": [{k: d.get(k) for k in ("_id", "invoiceNo", "invoiceId", "amount")} for d in q],
               "reports": {"rollups_equal": rollups["oracle"] == rollups["mongo"], "unknown_status_row": unknown_status, "unknown_status_lines": unknown_lines,
                           "mongo_reconciliation": {k: reports["mongo"]["reconciliation"].get(k) for k in ("status", "checks")},
                           "oracle_reconciliation_status": reports["oracle"]["reconciliation"].get("status")},
               "custbill": {"oracle_sha256": custbill["oracle"]["sha256"], "mongo_sha256": custbill["mongo"]["sha256"], "records": custbill["oracle"]["records"],
                            "byte_identical": custbill["oracle"]["sha256"] == custbill["mongo"]["sha256"]},
               "local_recon": {"exit": proc.returncode, "verdict": report.get("verdict"), "run_mode": report.get("run_mode"), "merge_evidence": report.get("merge_evidence"),
                               "checks": report.get("summary", {}).get("checks"), "failed": failed, "stderr": proc.stderr.strip().splitlines()[-2:]}}
        amounts = [money(l.get("amount")) for l in (doc or {}).get("lines", [])]
        ok = (rc == 0 and out["feed_delta"] == {"invoice_feed": 1, "invoice_feed_quarantine": 2} and doc is not None and doc.get("totalAmt") is None
              and doc.get("invoiceDt") == "31-FEB-26" and "invoiceDate" not in doc and amounts == ["10.01", "1.00"]
              and [d["_id"] for d in q] == [f"{P}0000000000a3", f"{P}0000000000a4"] and rollups["oracle"] == rollups["mongo"]
              and unknown_status == [{"status": "UNKNOWN(99)", "invoice_count": 1, "header_total_amt": None}]
              and sorted(r["line_type"] for r in unknown_lines) == ["CHARGE", "UNKNOWN(7)"] and custbill["oracle"]["sha256"] == custbill["mongo"]["sha256"]
              and proc.returncode == 0 and report.get("verdict") == "pass" and report.get("merge_evidence") is False)
        self.record("EDGE-U4-007", "feed rows past the gate: a header with INV_STATUS 99, NULL total and the unparsable '31-FEB-26' loads verbatim (no derived "
                    "invoiceDate), its lines embed with NUMBER(14,2) amounts (10.005 -> 10.01) including a line on another batch; the orphan and the "
                    "NULL-parent line land in invoice_feed_quarantine; month-end / reconciliation rollups stay identical to the cent (UNKNOWN(99) row with null "
                    "total, UNKNOWN(7) line type); CUSTBILL extract byte-identical; recon.py --mode local over the U4 collections passes with the edge rows present",
                    out, ok, notes="the mongo reconciliation report's own data-quality checks (stray batch line, unmapped status) are recorded, not graded")

    def probe_write_scope(self):
        scratch = "ow_tp_billing_u4_scope_probe"
        dbs_before = sorted(self.fixture.mongo.list_database_names())
        try:
            rc = self.reload(U4, mongo_db=scratch)
            scratch_colls = sorted(self.fixture.mongo[scratch].list_collection_names())
            indexes = {c: sorted(self.fixture.mongo[scratch][c].index_information()) for c in scratch_colls}
            dbs_after = sorted(self.fixture.mongo.list_database_names())
        finally:
            self.fixture.mongo.drop_database(scratch)
        _period_id, invoice_id = self.ids(E_SCOPE, FEB[0])
        _b, client = self.use("mongo")
        c0 = self.counts()
        self.preview(client, E_SCOPE, *FEB)
        c1 = self.counts()
        self.issue(client, E_SCOPE, *FEB)
        c2 = self.counts()
        self.issue(client, E_SCOPE, *FEB)
        c3 = self.counts()
        self.lines(client, invoice_id)
        self.facade_invoices(client, E_SCOPE)
        c4 = self.counts()
        a0 = self.audits(E_SCOPE, invoice_id)
        _b, oclient = self.use("oracle")
        self.preview(oclient, E_SCOPE, *FEB)
        self.issue(oclient, E_SCOPE, *FEB)
        a1 = self.audits(E_SCOPE, invoice_id)
        dbs_final = sorted(self.fixture.mongo.list_database_names())
        diff = lambda a, b: {k: b.get(k, 0) - a.get(k, 0) for k in set(a) | set(b) if a.get(k, 0) != b.get(k, 0)}  # noqa: E731
        oracle_audit = {k: v["oracle"] for k, v in self.audit_delta(a0, a1).items()}
        out = {"loader_exit": rc, "scratch_collections": scratch_colls, "indexes": indexes,
               "other_databases_touched": sorted((set(dbs_after) | set(dbs_final)) - set(dbs_before) - {scratch}),
               "preview_changed": diff(c0, c1), "issue_changed": diff(c1, c2), "reissue_changed": diff(c2, c3), "reads_changed": diff(c3, c4),
               "oracle_audit_rows_for_preview_plus_issue": oracle_audit}
        ok = (rc == 0 and scratch_colls == sorted(U4) and not out["other_databases_touched"] and out["preview_changed"] == {"billing_audit_log": 1}
              and out["issue_changed"] == {"invoices": 1, "rating_periods": 1, "billing_audit_log": 4} and out["reissue_changed"] == {"billing_audit_log": 4}
              and out["reads_changed"] == {} and oracle_audit == {"compute": 3, "finalized": 1, "issued": 1})
        self.record("EDGE-U4-008", "write scope: the U4 loader writes only credit_notes, invoice_feed, invoice_feed_quarantine and invoices (plus spec indexes) in "
                    "the target database and touches no other database; on the Mongo backend preview writes one log_msg row, issue writes one invoices + one "
                    "rating_periods document and 4 audit rows (compute, finalized, compute, issued: the same rows PKG_INVOICING logs on Oracle), a re-issue only "
                    "the 4 audit rows, lines/GET /invoices nothing", {"mongo": out}, ok,
                    notes="billing_audit_log is PKG_OW_UTIL.log_msg's collection (U1 port); U5 owns its load")

    def cleanup(self):
        self.oracle_quiet(f"DROP TRIGGER {TRIGGER}")
        self.fixture.reset()
        for stmt in [
            f"DELETE FROM invoice_lines WHERE invoice_id IN (SELECT id FROM invoices WHERE tenant_id LIKE '{P}%')",
            f"DELETE FROM invoices WHERE tenant_id LIKE '{P}%'",
            f"DELETE FROM rating_results WHERE period_id IN (SELECT id FROM rating_periods WHERE tenant_id LIKE '{P}%')",
            f"DELETE FROM rating_periods WHERE tenant_id LIKE '{P}%'",
            f"DELETE FROM credit_notes WHERE tenant_id LIKE '{P}%'",
            f"DELETE FROM subscriptions WHERE tenant_id LIKE '{P}%'",
            f"DELETE FROM subscriptions_hist WHERE tenant_id LIKE '{P}%'",
            f"DELETE FROM tenants WHERE id LIKE '{P}%'",
            f"DELETE FROM plans WHERE id LIKE '{P}%'",
            f"DELETE FROM invoice_line WHERE line_id LIKE '{P}%'",
            f"DELETE FROM invoice_header WHERE invoice_id LIKE '{P}%'",
        ]:
            self.oracle_quiet(stmt)
        rc = self.reload(["plans", "tenants", "subscriptions", "rating_periods"] + U4)
        left = {t: int(self.oracle([], fetch=f"SELECT COUNT(*) FROM {t} WHERE {col} LIKE '{P}%'")[0][0])
                for t, col in (("tenants", "id"), ("plans", "id"), ("subscriptions", "tenant_id"), ("credit_notes", "tenant_id"), ("invoices", "tenant_id"),
                               ("rating_periods", "tenant_id"), ("invoice_header", "invoice_id"), ("invoice_line", "line_id"))}
        left["invoices_of_static_tenants_not_seeded"] = int(self.oracle([], fetch="""SELECT COUNT(*) FROM invoices WHERE tenant_id LIKE '00000000-%'
            AND id NOT LIKE '60000000-%'""")[0][0])
        left["probe_trigger"] = int(self.oracle([], fetch=f"SELECT COUNT(*) FROM user_triggers WHERE UPPER(trigger_name) = '{TRIGGER.upper()}'")[0][0])
        left["mongo_edge_docs"] = (sum(self.mdb[c].count_documents({"tenantId": {"$regex": f"^{P}"}}) for c in ("invoices", "credit_notes", "rating_periods", "subscriptions"))
                                   + sum(self.mdb[c].count_documents({"_id": {"$regex": f"^{P}"}}) for c in ("tenants", "plans", "invoice_feed", "invoice_feed_quarantine", "invoices")))
        left["mongo_credit_notes_validator"] = len((self.mdb.command("listCollections", filter={"name": "credit_notes"})["cursor"]["firstBatch"] or [{}])[0]
                                                   .get("options", {}).get("validator", {}))
        left["reload_exit"] = rc
        self.record("EDGE-U4-009", "fixture restored: static tenants reset (invoicing_parity.Fixture.reset), no probe tenants/plans/notes/invoices/periods/feed rows, "
                    "no probe trigger or validator left on either side", {"both": left}, all(v == 0 for v in left.values()))

    # ---- driver ---------------------------------------------------------------------------------
    def run(self, out_dir: Path):
        print("resetting the invoicing baseline and reloading U4 from the Oracle fixture (batch loader) ...")
        self.fixture.reset()
        self.reload(U4)
        self.plant()
        try:
            self.probe_no_plan()
            self.probe_tax_tie()
            self.probe_burn_down_and_reissue()
            self.probe_issue_atomicity()
            self.probe_seeded_period()
            self.probe_facade_edges()
            self.probe_feed_edges(out_dir / "U4.verify.edge_local.recon.json")
            self.probe_write_scope()
        finally:
            self.cleanup()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--repo-root", default=str(HERE.parents[4]), help="checkout whose loader/backends/recon to exercise (the PR head)")
    p.add_argument("--oracle-dsn-env", default="OW_TP_ORACLE_FIXTURE_DSN")
    p.add_argument("--mongo-uri-env", default="OW_TP_MONGO_FIXTURE_URI")
    p.add_argument("--out", default=str(HERE / "U4.verify.edge_probes.json"))
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
        probes.record("EDGE-U4-ABORT", f"probe run aborted: {type(exc).__name__}: {str(exc)[:200]}", {}, False)
    report = {
        "kind": "u4-edge-probes", "unit": "U4", "run_mode": "fixture", "merge_evidence": False,
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
