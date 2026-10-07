"""Characterization scenario for legacy-billing, engine-independent.

An ordered list of HTTP calls against the running app: reads first, then
writes, then reads again to observe what the writes did. Recorded once on the
Oracle-backed app (golden/oracle.json) and replayed unchanged on the
Postgres-backed app; both must start from the same estate state (Postgres
freshly migrated from the Oracle the golden was recorded on).
"""
from __future__ import annotations

import hashlib

INTERNAL_TOKEN = "characterization-token"
NS = "demo"


def md5_uuid(text: str) -> str:
    h = hashlib.md5(text.encode()).hexdigest()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


STATIC = [f"00000000-0000-0000-0000-00000000000{n}" for n in range(1, 10)]
ADMIN_TENANT = "a0000000-0000-0000-0000-000000000001"
DEMO = [md5_uuid(f"{NS}:tenant:{i}") for i in (0, 1, 2)]
# Owner of the most CUSTOMER_MASTER rows; not in TENANTS, so the facade
# onboards it on first call (a write hidden in a GET).
WHALE = md5_uuid(f"{NS}:htenant:0")
TENANTS = STATIC + [ADMIN_TENANT] + DEMO
STATIC_INVOICES = [f"60000000-0000-0000-0000-00000000000{n}" for n in (1, 2, 3, 9)]
PLAN_GROWTH = "10000000-0000-0000-0000-000000000002"
FEB = {"period_start": "2026-02-01", "period_end": "2026-02-28"}

ADMIN = {"X-User-ID": ADMIN_TENANT, "X-User-Roles": "ADMIN"}


def user(tenant: str) -> dict:
    return {"X-User-ID": tenant, "X-User-Email": f"{tenant[:8]}@char.example.com"}


def _reports(tag: str) -> list[dict]:
    return [
        {"id": f"{tag}:month-end", "path": f"/api/reports/month-end?ns={NS}"},
        {"id": f"{tag}:reconciliation", "path": f"/api/reports/reconciliation?ns={NS}"},
        {"id": f"{tag}:admin-month-end", "path": f"/api/v1/billing/admin/reports/month-end?ns={NS}",
         "headers": ADMIN},
        {"id": f"{tag}:admin-reconciliation",
         "path": f"/api/v1/billing/admin/reports/reconciliation?ns={NS}", "headers": ADMIN},
    ]


def _tenant_reads(tag: str, tenants: list[str]) -> list[dict]:
    steps = []
    for t in tenants:
        h = user(t)
        steps += [
            {"id": f"{tag}:me:{t}", "path": "/api/v1/billing/me?on=2026-02-15", "headers": h},
            {"id": f"{tag}:entitlement:{t}", "path": "/api/v1/billing/entitlement?on=2026-02-15",
             "headers": h},
            {"id": f"{tag}:usage:{t}",
             "path": "/api/v1/billing/usage?period_start=2026-02-01&period_end=2026-02-28",
             "headers": h},
            {"id": f"{tag}:invoices:{t}", "path": "/api/v1/billing/invoices", "headers": h,
             "follow_invoice_lines": True},
            {"id": f"{tag}:customer:{t}", "path": "/api/v1/billing/customer", "headers": h},
        ]
    return steps


def steps() -> list[dict]:
    s: list[dict] = [{"id": "health", "path": "/health"}]
    s += _reports("before")
    s += [
        {"id": "admin-month-end:forbidden", "path": f"/api/v1/billing/admin/reports/month-end?ns={NS}",
         "headers": user(STATIC[0])},
        {"id": "month-end:unknown-ns", "path": "/api/reports/month-end?ns=nosuchns"},
        {"id": "reconciliation:unknown-ns", "path": "/api/reports/reconciliation?ns=nosuchns"},
        {"id": "plans", "path": "/api/v1/billing/plans", "headers": user(STATIC[0])},
        {"id": "plans:no-identity", "path": "/api/v1/billing/plans"},
        {"id": "entitlement:bad-date", "path": "/api/v1/billing/entitlement?on=2026-13-01",
         "headers": user(STATIC[0])},
        {"id": "usage:inverted-range",
         "path": "/api/v1/billing/usage?period_start=2026-03-01&period_end=2026-02-01",
         "headers": user(STATIC[0])},
        {"id": "invoice-lines:not-owner", "path": f"/api/v1/billing/invoices/{STATIC_INVOICES[0]}/lines",
         "headers": user(STATIC[0])},
        {"id": "admin-overdue:forbidden", "path": "/api/v1/billing/admin/overdue?as_of=2026-03-31",
         "headers": user(STATIC[0])},
        {"id": "admin-overdue", "path": "/api/v1/billing/admin/overdue?as_of=2026-03-31", "headers": ADMIN},
        {"id": "admin-dunning", "path": "/api/v1/billing/admin/dunning?as_of=2026-12-31", "headers": ADMIN},
        {"id": "legacy:plans", "path": "/plans"},
        {"id": "legacy:entitlement", "path": f"/plans/{STATIC[0]}/entitlement?on=2026-02-28"},
        {"id": "legacy:overdue", "path": "/api/dunning/overdue?as_of=2026-02-28"},
    ]
    for t in STATIC + [ADMIN_TENANT, DEMO[0]]:
        s += [
            {"id": f"legacy:rating-preview:{t}", "method": "POST", "path": "/api/rating/preview",
             "json": {"tenant_id": t, **FEB}},
            {"id": f"legacy:invoice-preview:{t}", "path": f"/api/invoices/{t}/preview"
             "?period_start=2026-02-01&period_end=2026-02-28"},
        ]
    for inv in STATIC_INVOICES:
        s.append({"id": f"legacy:invoice-lines:{inv}", "path": f"/api/invoices/{inv}/lines"})
    s += _tenant_reads("before", TENANTS + [WHALE])

    # --- writes ---
    event = {"tenant_id": DEMO[0], "event_id": md5_uuid("char:event:1"), "kind": "api",
             "units": 120, "occurred_at": "2026-02-10T10:00:00Z"}
    token = {"X-Internal-Token": INTERNAL_TOKEN}
    s += [
        {"id": "ingest:new", "method": "POST", "path": "/internal/usage/events", "headers": token,
         "json": event},
        {"id": "ingest:duplicate", "method": "POST", "path": "/internal/usage/events",
         "headers": token, "json": event},
        {"id": "ingest:new-tenant", "method": "POST", "path": "/internal/usage/events",
         "headers": token,
         "json": {**event, "tenant_id": md5_uuid("char:new-tenant"), "event_id": md5_uuid("char:event:2"),
                  "kind": "compute", "units": 5000, "email": "newco@char.example.com"}},
        {"id": "ingest:bad-kind", "method": "POST", "path": "/internal/usage/events", "headers": token,
         "json": {**event, "kind": "fax"}},
        {"id": "ingest:bad-token", "method": "POST", "path": "/internal/usage/events",
         "headers": {"X-Internal-Token": "wrong"}, "json": event},
        {"id": "plan-change", "method": "POST", "path": "/api/v1/billing/plan-change",
         "headers": user(DEMO[0]), "json": {"plan_id": PLAN_GROWTH, "effective_on": "2026-12-01"}},
        {"id": "plan-change:again", "method": "POST", "path": "/api/v1/billing/plan-change",
         "headers": user(DEMO[0]), "json": {"plan_id": PLAN_GROWTH, "effective_on": "2026-12-01"}},
        {"id": "plan-change:unknown-plan", "method": "POST", "path": "/api/v1/billing/plan-change",
         "headers": user(DEMO[1]), "json": {"plan_id": "nope", "effective_on": "2026-12-01"}},
        {"id": "plan-change:past", "method": "POST", "path": "/api/v1/billing/plan-change",
         "headers": user(DEMO[1]), "json": {"plan_id": PLAN_GROWTH, "effective_on": "2026-01-01"}},
        {"id": "entitlement:after-plan-change", "path": "/api/v1/billing/entitlement?on=2026-12-15",
         "headers": user(DEMO[0])},
        {"id": "legacy:plan-change", "method": "POST", "path": f"/plans/{STATIC[2]}/change",
         "form": {"plan_id": PLAN_GROWTH, "effective_on": "2026-03-01"}},
        {"id": "legacy:entitlement-after-change", "path": f"/plans/{STATIC[2]}/entitlement?on=2026-03-15"},
    ]
    for t in STATIC + [ADMIN_TENANT, DEMO[0]]:
        s += [
            {"id": f"finalize:{t}", "method": "POST", "path": "/api/rating/finalize",
             "json": {"tenant_id": t, **FEB}},
            {"id": f"issue:{t}", "method": "POST", "path": f"/api/invoices/{t}/issue", "form": FEB},
        ]
    s += [
        {"id": "issue:again", "method": "POST", "path": f"/api/invoices/{STATIC[0]}/issue", "form": FEB},
        {"id": "dunning:schedule", "method": "POST", "path": "/api/dunning/schedule",
         "form": {"as_of": "2026-03-07"}},
        {"id": "dunning:schedule-again", "method": "POST", "path": "/api/dunning/schedule",
         "form": {"as_of": "2026-03-07"}},
        {"id": "dunning:suspend", "method": "POST", "path": "/api/dunning/suspend",
         "form": {"as_of": "2026-03-31"}},
        {"id": "after:admin-overdue", "path": "/api/v1/billing/admin/overdue?as_of=2026-03-31",
         "headers": ADMIN},
        {"id": "after:admin-dunning", "path": "/api/v1/billing/admin/dunning?as_of=2026-12-31",
         "headers": ADMIN},
    ]
    s += _tenant_reads("after", TENANTS + [WHALE])
    s += _reports("after")
    return s
