#!/usr/bin/env python3
"""Build (or check) migration/billing/mapping_spec.json for plan step s3.1-mapping-spec.

The model below is hand-authored; everything mechanical (column lists, BSON types, money
columns, entrypoint coverage, size guards) is derived from the merged inputs so the spec
cannot drift from them:

    migration/billing/census.json                     table/column/constraint inventory (#1772)
    migration/billing/census/buckets.json             migrate bucket membership (#1772)
    migration/billing/access_patterns/access_patterns.json
    migration/billing/access_patterns.md              entrypoint -> tables, atomic units (#1774)
    migration/billing/tolerances.json                 money columns compared as decimal (#1771)
    migration/billing/fixtures/demo.json              planted anomalies, legacy representations (#1773)
    migration/billing/mapping/cardinality.json        live child-per-parent bounds (mapping/cardinality.py)
    migration/billing/mapping/dispositions.py         Oracle-specific construct dispositions (s3.2-known-incompatibilities)

Usage:
    build_mapping_spec.py            # (re)write migration/billing/mapping_spec.json
    build_mapping_spec.py --check    # exit 1 if the committed file differs or any invariant fails

No database connection is made; nothing is read from the environment.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from dispositions import incompatibilities

REPO = Path(__file__).resolve().parents[3]
BILLING = REPO / "migration/billing"
OUT = BILLING / "mapping_spec.json"

RUN = "20261001T233613Z"
RUN_BRANCH = f"tp-run/mongodb-{RUN}"
DATABASE = f"ow_tp_billing_{RUN}"  # d-migration-db (UNT-3): fresh database ow_tp_billing_<run> per run
BSON_MAX = 16 * 1024 * 1024

DOCS = {
    "embed_vs_reference": "https://www.mongodb.com/docs/manual/data-modeling/best-practices/",
    "map_relationships": "https://www.mongodb.com/docs/manual/data-modeling/schema-design-process/map-relationships/",
    "unbounded_arrays": "https://www.mongodb.com/docs/manual/data-modeling/design-antipatterns/unbounded-arrays/",
    "bson_limit": "https://www.mongodb.com/docs/manual/reference/limits/#bson-documents",
    "monetary_data": "https://www.mongodb.com/docs/manual/tutorial/model-monetary-data/",
    "unique_indexes": "https://www.mongodb.com/docs/manual/core/index-unique/",
    "ttl_indexes": "https://www.mongodb.com/docs/manual/core/index-ttl/",
    "esr_rule": "https://www.mongodb.com/docs/manual/tutorial/equality-sort-range-guideline/",
}


def load(rel: str):
    with open(BILLING / rel, encoding="utf-8") as fh:
        return json.load(fh)


def camel(col: str) -> str:
    parts = col.lower().split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


# ----------------------------------------------------------------------------------------------
# Type rules (column -> BSON). Money is decided by tolerances.json, not by hand.
# ----------------------------------------------------------------------------------------------
def bson_type(table: str, col: dict, money_cols: set[tuple[str, str]]) -> dict:
    name, dt = col["column_name"], col["data_type"]
    key = (table.lower(), name.lower())
    if dt == "NUMBER":
        scale = col.get("data_scale") or 0
        prec = col.get("data_precision")
        if key in money_cols:
            return {"bson": "decimal", "note": f"Decimal128 from Oracle NUMBER({prec},{scale}); never double"}
        if scale > 0:
            raise SystemExit(f"{table}.{name} has scale {scale} but is not a tolerances.json money column")
        return {"bson": "long" if (prec or 38) > 9 else "int", "note": f"NUMBER({prec},0)"}
    if dt in ("VARCHAR2", "CHAR"):
        if dt == "VARCHAR2" and name.endswith("_DT"):
            return {"bson": "string", "note": "DD-MON-YY text kept verbatim; typed sibling see field rules"}
        return {"bson": "string", "note": dt + (" Y/N kept as the 1-char string" if name.endswith("_YN") else "")}
    if dt == "DATE":
        return {"bson": "date", "note": "Oracle DATE (second precision) -> BSON UTC datetime"}
    if dt.startswith("TIMESTAMP"):
        return {"bson": "date", "note": "TIMESTAMP(6) -> BSON UTC datetime (ms precision; recon compares whole seconds, tolerances.timestamp.absolute_seconds=0)"}
    raise SystemExit(f"unmapped Oracle type {dt} on {table}.{name}")


DD_MON_YY = {"bson": "date", "nullable": True,
             "rule": "parsed from the verbatim DD-MON-YY text under the Oracle RR rule; absent when the text is malformed or not a calendar date (fixture anomaly dirty_dates); the verbatim string is the recon value"}
CSV_LIST = {"bson": "array<string>", "nullable": True,
            "rule": "split of the verbatim CSV on ',' only when it matches the clean form; absent when malformed (fixture anomaly malformed_csv_lists); the verbatim string is the recon value"}
CSV_CLEAN = {"RELATED_ACCT_IDS": r"^\d{5}(,\d{5}){0,3}$", "CHILD_ACCT_IDS": r"^\d{5}(,\d{5}){0,3}$",
             "PROMO_CODES_CSV": r"^[A-Z0-9]+(,[A-Z0-9]+)*$", "GL_ACCT_CSV": r"^\d+(,\d+)*$"}


def fields_for(table: dict, money_cols, skip: set[str] = frozenset(), rename: dict[str, str] | None = None,
               typed_siblings: bool = True) -> list[dict]:
    rename = rename or {}
    out = []
    for col in table["columns"]:
        name = col["column_name"]
        if name in skip:
            continue
        t = bson_type(table["name"], col, money_cols)
        field = rename.get(name, camel(name))
        entry = {"field": field, "source": f"{table['name']}.{name}", "bson": t["bson"],
                 "nullable": col["nullable"] == "Y", "note": t["note"]}
        out.append(entry)
        if typed_siblings and col["data_type"] == "VARCHAR2" and name.endswith("_DT"):
            out.append({"field": field[:-2] + "Date", "source": f"{table['name']}.{name} (derived)", **DD_MON_YY})
        if typed_siblings and name in CSV_CLEAN:
            out.append({"field": field + "List", "source": f"{table['name']}.{name} (derived)", **CSV_LIST,
                        "clean_form": CSV_CLEAN[name]})
    return out


# ----------------------------------------------------------------------------------------------
# Hand-authored model
# ----------------------------------------------------------------------------------------------
def ix(name, keys, serves, query, **opts):
    d = {"name": name, "keys": keys, "options": opts, "serves": serves, "query": query}
    return d


def model(t: dict, money_cols, card: dict) -> list[dict]:
    """t: census tables by name. Returns the collection list."""
    fan = card["fanout"]
    rl = card["row_length"]

    def pk(table):
        return [c["columns"] for c in t[table]["constraints"] if c["constraint_type"] == "P"][0]

    def embed(path, child, parent_edge, order, identity, bound, parent_bytes_table=None, extra=None):
        f = fan[parent_edge]
        child_max_bytes = rl[child]["max_row_bytes"]
        parent_max_bytes = rl[parent_bytes_table]["max_row_bytes"] if parent_bytes_table else 0
        e = {
            "path": path, "source_table": child, "relationship": "one-to-few",
            "observed": {"edge": parent_edge, "children_per_parent": f["children_per_parent"],
                         "child_rows": f["child_rows"], "parents_with_children": f["parents_with_children"],
                         "child_max_row_bytes": child_max_bytes, "captured_at": card["captured_at"], "mode": card["source"]["mode"]},
            "order": order, "identity": identity,
            "bound": bound,
            "size_guard": {
                "limit_bytes": BSON_MAX,
                "projected_max_doc_bytes": parent_max_bytes + bound["max_elements"] * child_max_bytes * 2,
                "projection": "parent max row bytes + max_elements x child max row bytes x 2 (BSON key/overhead factor); Oracle VSIZE is a proxy, not a guarantee",
                "writer_rule": "before $push/replace the writer computes the document's BSON size (bsonsize()/$bsonSize) and refuses the write above 12 MiB (75% of the limit) instead of letting Atlas reject it at 16 MiB; the refusal is a recon anomaly, never a silent drop",
                "validator_rule": f"$jsonSchema maxItems on '{path}' = bound.max_elements",
            },
        }
        if extra:
            e.update(extra)
        return e

    cols = []

    # --- codes --------------------------------------------------------------------------------
    cols.append({
        "name": "codes", "source_tables": ["CODES"], "kind": "reference",
        "why": "static lookup decoding every *_CD column (9 read sites, 0 writes); read by exact (code_type, code_val) and listed per code_type. Kept as its own collection, not denormalised into every document, so historical codes keep decoding and the recon stays a row-for-row set compare.",
        "_id": {"from": ["CODES.CODE_TYPE", "CODES.CODE_VAL"], "shape": {"codeType": "string", "codeVal": "int"},
                "rule": "compound Oracle PK as an embedded-document _id with keys in exactly this order (BSON compares documents field-by-field in order)"},
        "fields": fields_for(t["CODES"], money_cols),
        "embedded": [],
        "indexes": [],
        "writes": {"post_cutover": "none (static reference data, loaded once per run)"},
        "notes": ["_id already covers lookup by (code_type, code_val) and the per-type listing (prefix scan on _id.codeType) that every *_CD decode needs; no secondary index."],
    })

    # --- tenants ------------------------------------------------------------------------------
    cols.append({
        "name": "tenants", "source_tables": ["TENANTS"], "kind": "entity",
        "why": "parent of every tenant-scoped collection; 69 rows, read by _id in entitlement/preview/issue and updated per tenant by suspend_overdue. Children (subscriptions, usage_events, invoices, customers) are referenced by tenantId, never embedded: usage_events is append-heavy, customers per tenant_id reach 8,575 live (unbounded), and each child is queried independently.",
        "_id": {"from": ["TENANTS.ID"], "shape": "string", "rule": "Oracle PK VARCHAR2 uuid kept verbatim"},
        "fields": fields_for(t["TENANTS"], money_cols, skip={"ID"}),
        "embedded": [],
        "indexes": [ix("uq_tenants_name", {"name": 1}, ["ensure_tenant (bootstrap)"], "UQ_TENANTS_NAME carried; ensure_tenant inserts by id and the unique name prevents a second tenant doc for one name", unique=True)],
        "writes": {"post_cutover": "ensure_tenant inserts; suspend_overdue sets statusCd"},
        "notes": [],
    })

    # --- plans --------------------------------------------------------------------------------
    cols.append({
        "name": "plans", "source_tables": ["PLANS"], "kind": "reference",
        "why": "static rate card (6 read sites, 0 writes) read by _id and listed ORDER BY monthly_fee, id.",
        "_id": {"from": ["PLANS.ID"], "shape": "string", "rule": "Oracle PK VARCHAR2 kept verbatim"},
        "fields": fields_for(t["PLANS"], money_cols, skip={"ID"}),
        "embedded": [],
        "indexes": [ix("uq_plans_code", {"code": 1}, ["list_plans"], "UQ_PLANS_CODE carried", unique=True)],
        "writes": {"post_cutover": "none"},
        "notes": ["fn_list_plans sorts 3 rows by monthlyFee, _id: an in-memory sort, no index."],
    })

    # --- subscriptions ------------------------------------------------------------------------
    cols.append({
        "name": "subscriptions", "source_tables": ["SUBSCRIPTIONS"], "kind": "entity",
        "why": "1 per tenant live but open-ended (change_plan closes one and opens another), read on its own by entitlement/usage_rating/issue_invoice ('latest covering subscription for a date') and updated independently of the tenant by change_plan and suspend_overdue -> referenced from tenants, not embedded.",
        "_id": {"from": ["SUBSCRIPTIONS.ID"], "shape": "string", "rule": "Oracle PK VARCHAR2 kept verbatim"},
        "fields": fields_for(t["SUBSCRIPTIONS"], money_cols, skip={"ID"}),
        "embedded": [],
        "indexes": [ix("ix_subscriptions_tenant_starts", {"tenantId": 1, "startsOn": -1},
                       ["entitlement", "usage_rating", "finalize_rating", "invoice_preview", "issue_invoice", "change_plan", "suspend_overdue"],
                       "{tenantId: t, startsOn: {$lte: d}, $or: [{endsOn: null}, {endsOn: {$gte: d}}]} sort startsOn desc limit 1 (covering subscription); change_plan/suspend_overdue update all docs with tenantId = t")],
        "writes": {"post_cutover": "change_plan (close + insert, with subscriptions_hist copies, in one transaction); suspend_overdue (statusCd/suspendedOn)"},
        "notes": [],
    })

    # --- subscriptions_hist (d-history-tables) ---------------------------------------------
    cols.append({
        "name": "subscriptions_hist", "source_tables": ["SUBSCRIPTIONS_HIST"], "kind": "history",
        "decision": "d-history-tables",
        "why": "full-row copies written by TRG_SUBSCRIPTIONS_HIST on every update/delete; never read by the app, grows with every plan change -> separate collection (d-history-tables), not an array on the subscription (unbounded, write-only).",
        "_id": {"from": ["SUBSCRIPTIONS_HIST.HIST_ID"], "shape": "long",
                "rule": "SEQ_SUBSCRIPTIONS_HIST value kept for carried rows; after cutover the app issues the next value (see key_strategy.sequences)"},
        "fields": fields_for(t["SUBSCRIPTIONS_HIST"], money_cols, skip={"HIST_ID"}, rename={"ID": "subscriptionId"}),
        "embedded": [],
        "indexes": [ix("ix_subscriptions_hist_subscription", {"subscriptionId": 1, "_id": 1}, ["recon", "change_plan (write side)"],
                       "history of one subscription in write order; no app read path, kept for recon/audit")],
        "writes": {"post_cutover": "change_plan and suspend_overdue copy the pre-image of each updated subscription (migrate-as-logic replacement for the trigger) in the same transaction"},
        "notes": ["histDt is VARCHAR2 in Oracle and is kept verbatim with a typed histDate sibling."],
    })

    # --- usage_events -------------------------------------------------------------------------
    cols.append({
        "name": "usage_events", "source_tables": ["USAGE_EVENTS"], "kind": "event",
        "why": "the only append-heavy table (814 rows / 69 tenants live, max 25 per tenant today but unbounded by design: bridge ingest appends forever). Always read per tenant: compute_rating scans every event of a tenant and filters the period in PL/SQL; GET /usage reads a tenant's events in a date window newest-first. Referenced from tenants by tenantId; embedding would be the textbook unbounded-array anti-pattern.",
        "_id": {"from": ["USAGE_EVENTS.ID"], "shape": "string", "rule": "deterministic event id from the bridge kept verbatim; the duplicate-insert ORA-00001 contract becomes a duplicate-key error on _id"},
        "fields": fields_for(t["USAGE_EVENTS"], money_cols, skip={"ID"}),
        "embedded": [],
        "indexes": [ix("ix_usage_events_tenant_occurred", {"tenantId": 1, "occurredAt": -1, "_id": -1},
                       ["usage_rating", "usage_summary", "finalize_rating", "invoice_preview", "issue_invoice", "GET /usage (facade)", "POST /internal/usage/events"],
                       "{tenantId: t, occurredAt: {$gte: start, $lt: end+1d}} sort occurredAt desc, _id desc (ESR: equality tenantId, sort occurredAt/_id, range occurredAt); compute_rating's whole-tenant scan is the same prefix without the range")],
        "writes": {"post_cutover": "POST /internal/usage/events inserts one document per event after ensure_tenant"},
        "notes": ["Not a time-series collection: the ingest contract needs a caller-supplied unique _id and duplicate detection, which time-series collections do not provide."],
    })

    # --- rating_periods (+ embedded rating_results) -----------------------------------------
    cols.append({
        "name": "rating_periods", "source_tables": ["RATING_PERIODS", "RATING_RESULTS"], "kind": "entity",
        "decision": "d-embed-rating-result (this spec): one-to-one, embed",
        "why": "rating_results is never read without its period (access_patterns §6) and is exactly one per period: sp_finalize_rating derives the result id as md5(period_id) and upserts it, and both rows are written in the same transaction. MongoDB guidance for a 1:1 written-together pair is to embed; the join GET /invoices needs is then a single $lookup on rating_periods._id.",
        "_id": {"from": ["RATING_PERIODS.ID"], "shape": "string", "rule": "Oracle PK VARCHAR2 kept verbatim"},
        "fields": fields_for(t["RATING_PERIODS"], money_cols, skip={"ID"}),
        "embedded": [{
            "path": "result", "source_table": "RATING_RESULTS", "relationship": "one-to-one",
            "shape": "sub-document (not an array)",
            "observed": {"edge": "RATING_PERIODS->RATING_RESULTS", "children_per_parent": fan["RATING_PERIODS->RATING_RESULTS"]["children_per_parent"],
                         "child_rows": fan["RATING_PERIODS->RATING_RESULTS"]["child_rows"], "captured_at": card["captured_at"], "mode": card["source"]["mode"]},
            "identity": "result.id keeps RATING_RESULTS.ID (= md5(period id)); RATING_RESULTS.PERIOD_ID is the parent _id and is not repeated",
            "fields": fields_for(t["RATING_RESULTS"], money_cols, skip={"PERIOD_ID"}),
            "bound": {"max_elements": 1, "basis": "sp_finalize_rating upserts a single result keyed by md5(period_id)"},
            "size_guard": {"limit_bytes": BSON_MAX, "projected_max_doc_bytes": rl["RATING_RESULTS"]["max_row_bytes"] * 2 + 200, "projection": "one fixed sub-document; no array"},
            "absent_when": "the period exists but has not been finalised (preview-only periods)",
        }],
        "indexes": [ix("uq_rating_periods_tenant_start", {"tenantId": 1, "periodStart": 1},
                       ["usage_rating", "finalize_rating", "invoice_preview", "issue_invoice", "GET /invoices (facade, via $lookup on _id)"],
                       "tenant + period: {tenantId: t, periodStart: s} point lookup/upsert (UQ_RATING_PERIODS carried) and the rollover window {tenantId: t, periodStart: {$gte: s-3mo, $lt: s}} reading result.rolloverUnits", unique=True)],
        "writes": {"post_cutover": "finalize_rating / issue_invoice upsert the period and set result in one document write"},
        "notes": ["Recon reconciles RATING_RESULTS against the unwound result sub-document (row count = documents with result present)."],
    })

    # --- invoices (+ embedded invoice_lines) ------------------------------------------------
    il = fan["INVOICES->INVOICE_LINES"]
    cols.append({
        "name": "invoices", "source_tables": ["INVOICES", "INVOICE_LINES"], "kind": "entity",
        "decision": "d-embed-invoice-lines",
        "why": "lines are written with the header in sp_issue_invoice's single transaction, cascade-deleted with it, and are never read without it (fn_invoice_lines first checks the header by (id, tenant_id)). Line count is bounded by the issuing logic (one line per charge kind: fee, overage, credit) - live max 2 per invoice. GET /invoices is header-only and projects lines away.",
        "_id": {"from": ["INVOICES.ID"], "shape": "string", "rule": "Oracle PK VARCHAR2 kept verbatim"},
        "fields": fields_for(t["INVOICES"], money_cols, skip={"ID"}),
        "embedded": [embed("lines", "INVOICE_LINES", "INVOICES->INVOICE_LINES",
                           order="lineNo ascending (fn_invoice_lines ORDER BY line_no)",
                           identity="lines[].id keeps INVOICE_LINES.ID; (invoice _id, lines[].lineNo) is unique within the document (UQ_INVOICE_LINES); INVOICE_LINES.INVOICE_ID is the parent _id and is not repeated",
                           bound={"max_elements": 50, "basis": "sp_issue_invoice emits at most one line per charge kind (live max 2, p99 2); 50 is the validator ceiling with headroom for new charge kinds"},
                           parent_bytes_table="INVOICES",
                           extra={"fields": fields_for(t["INVOICE_LINES"], money_cols, skip={"INVOICE_ID"})})],
        "indexes": [
            ix("ix_invoices_tenant_issued", {"tenantId": 1, "issuedAt": -1, "_id": -1},
               ["GET /invoices (facade)", "invoice_lines (ownership check {_id, tenantId})"],
               "{tenantId: t} sort issuedAt desc, _id desc; projection excludes lines"),
            ix("ix_invoices_status_issued", {"statusCd": 1, "issuedAt": 1, "_id": 1},
               ["overdue", "schedule_dunning", "suspend_overdue", "GET /admin/overdue (facade)"],
               "overdue by date: {statusCd: 40, issuedAt: {$lt: asOf}} sort issuedAt, _id (fn_overdue_accounts compares issued_at as YYYYMMDD; the core estate has no due date column - the only due date is INVOICE_HEADER.DUE_DT in the report feed, indexed there)"),
            ix("uq_invoices_lines_id", {"lines.id": 1}, ["recon", "issue_invoice"],
               "PK_INVOICE_LINES carried across documents as a unique multikey index (partial so invoices without lines do not collide on a missing key)",
               unique=True, partialFilterExpression={"lines.id": {"$exists": True}}),
        ],
        "writes": {"post_cutover": "sp_issue_invoice replacement inserts header+lines as one document inside the issue_invoice transaction; statusCd 40/30 is never written by the app (access_patterns §2.10) and has no named owner after cutover: open behavior difference incompatibilities bd-overdue-status-owner"},
        "notes": ["invoice by tenant/status (ticket) = ix_invoices_tenant_issued prefix + statusCd filter in memory per tenant (<= tens of invoices per tenant); overdue by status across tenants = ix_invoices_status_issued.",
                  "Uniqueness of (invoice, lineNo) inside one document cannot be expressed as a MongoDB unique index (multikey indexes do not compare entries of the same document); the writer and the $jsonSchema validator enforce it."],
    })

    # --- credit_notes -------------------------------------------------------------------------
    cols.append({
        "name": "credit_notes", "source_tables": ["CREDIT_NOTES"], "kind": "entity",
        "why": "read per tenant (preview sums remainingAmount; issue_invoice burns balances oldest-first FOR UPDATE) and mutated independently of invoices and tenants (max 2 per tenant live, open-ended) -> referenced by tenantId.",
        "_id": {"from": ["CREDIT_NOTES.ID"], "shape": "string", "rule": "Oracle PK VARCHAR2 kept verbatim"},
        "fields": fields_for(t["CREDIT_NOTES"], money_cols, skip={"ID"}),
        "embedded": [],
        "indexes": [ix("ix_credit_notes_tenant_issued", {"tenantId": 1, "issuedOn": 1, "_id": 1}, ["invoice_preview", "issue_invoice"],
                       "{tenantId: t, remainingAmount: {$gt: 0}} sort issuedOn, _id (oldest first burn-down)")],
        "writes": {"post_cutover": "issue_invoice decrements remainingAmount inside the issue_invoice transaction"},
        "notes": [],
    })

    # --- dunning_attempts ---------------------------------------------------------------------
    cols.append({
        "name": "dunning_attempts", "source_tables": ["DUNNING_ATTEMPTS"], "kind": "entity",
        "why": "read across tenants by scheduledFor (GET /admin/dunning, newest 200) and per invoice by attemptNo (schedule_dunning) - a cross-tenant query shape an embedded array on invoices cannot serve.",
        "_id": {"from": ["DUNNING_ATTEMPTS.ID"], "shape": "string", "rule": "Oracle PK VARCHAR2 kept verbatim"},
        "fields": fields_for(t["DUNNING_ATTEMPTS"], money_cols, skip={"ID"}),
        "embedded": [],
        "indexes": [
            ix("uq_dunning_attempts_invoice_attempt", {"invoiceId": 1, "attemptNo": 1}, ["schedule_dunning"],
               "UQ_DUNNING_ATTEMPTS carried: next attemptNo per invoice = max(attemptNo)+1 with the unique key refusing a race", unique=True),
            ix("ix_dunning_attempts_scheduled", {"scheduledFor": -1, "_id": -1}, ["GET /admin/dunning (facade)"],
               "{scheduledFor: {$lte: asOf}} sort scheduledFor desc, _id desc limit 200"),
        ],
        "writes": {"post_cutover": "schedule_dunning inserts one attempt per overdue invoice (own transaction)"},
        "notes": [],
    })

    # --- notifications ------------------------------------------------------------------------
    cols.append({
        "name": "notifications", "source_tables": ["NOTIFICATIONS"], "kind": "entity",
        "why": "written per tenant by suspend_overdue inside the suspend transaction; the Oracle unique key (tenant, kind, sent_at) is the idempotency guard and is carried as the only index.",
        "_id": {"from": ["NOTIFICATIONS.ID"], "shape": "string", "rule": "Oracle PK VARCHAR2 kept verbatim"},
        "fields": fields_for(t["NOTIFICATIONS"], money_cols, skip={"ID"}),
        "embedded": [],
        "indexes": [ix("uq_notifications_tenant_kind_sent", {"tenantId": 1, "kindCd": 1, "sentAt": 1}, ["suspend_overdue"],
                       "UQ_NOTIFICATIONS carried; also serves any per-tenant listing", unique=True)],
        "writes": {"post_cutover": "suspend_overdue inserts"},
        "notes": [],
    })

    # --- billing_audit_log --------------------------------------------------------------------
    cols.append({
        "name": "billing_audit_log", "source_tables": ["BILLING_AUDIT_LOG"], "kind": "log",
        "why": "written by pkg_ow_util.log_msg under PRAGMA AUTONOMOUS_TRANSACTION from 8 call sites including read-only entrypoints (list_plans, usage_rating, invoice_preview); never read. It is outside every business transaction and must stay so: an insert that commits even when the enclosing transaction aborts cannot live inside any other document.",
        "_id": {"from": ["BILLING_AUDIT_LOG.LOG_ID"], "shape": "long",
                "rule": "SEQ_BILLING_AUDIT_LOG value (TRG_BILLING_AUDIT_LOG_ID) kept for carried rows; new rows get the app-issued next value"},
        "fields": fields_for(t["BILLING_AUDIT_LOG"], money_cols, skip={"LOG_ID"}),
        "embedded": [],
        "indexes": [],
        "writes": {"post_cutover": "log_msg replacement: a single-document insert issued OUTSIDE any session/transaction (its own connection or no session); an insert failure is raised to the caller (incompatibilities bd-log-msg-swallow); never part of an atomic unit",
                   "autonomous": True},
        "retention": {"decision": "d-audit-retention", "chosen": "match-live",
                      "rule": "no TTL index and no purge: JOB_PURGE_AUDIT_LOG is DISABLED live (run_count 0), so matching live keeps every row; recon compares every row",
                      "alternative": "ttl-90d (human pick on the plan): add ttl_billing_audit_log_logged_at {loggedAt: 1} expireAfterSeconds 7776000 and exclude rows older than 90 days from recon"},
        "notes": ["Never read by the app, so no secondary index; the census bucket note's 'retire -> TTL' for JOB_PURGE_AUDIT_LOG is superseded by d-audit-retention = match-live."],
    })

    # --- customers (CUSTOMER_MASTER + ENTITY_ATTR_VALUE, d-customer-eav) -----------------------
    eav = fan["CUSTOMER_MASTER->ENTITY_ATTR_VALUE"]
    cm_fields = fields_for(t["CUSTOMER_MASTER"], money_cols, skip={"CUST_ID"})
    cols.append({
        "name": "customers", "source_tables": ["CUSTOMER_MASTER", "ENTITY_ATTR_VALUE"], "kind": "entity",
        "decision": "d-customer-eav",
        "why": "GET /customer reads one customer_master row per tenant then its EAV rows; nothing reads EAV rows independently and ENTITY_TYPE is 'CUSTOMER' for every live row. Attributes are 1-5 per customer (p99 3) with 16-char values: a bounded one-to-few array, embedded and typed (d-customer-eav). All 155 columns are carried flat under their camelCase names so SELECT * parity and exact recon hold; regrouping the repeating address/phone/flag/udf groups is a service-side refactor outside this spec.",
        "_id": {"from": ["CUSTOMER_MASTER.CUST_ID"], "shape": "string",
                "rule": "CUST_ID kept verbatim; CUST_SEQ_NO (SEQ_CUSTOMER_MASTER via TRG_CUSTOMER_MASTER_SEQ) is carried as custSeqNo and issued by the app after cutover"},
        "fields": cm_fields,
        "embedded": [embed("attributes", "ENTITY_ATTR_VALUE", "CUSTOMER_MASTER->ENTITY_ATTR_VALUE",
                           order="eavId ascending (facade ORDER BY eav_id)",
                           identity="attributes[].eavId keeps ENTITY_ATTR_VALUE.EAV_ID (SEQ_ENTITY_ATTR_VALUE); ENTITY_TYPE ('CUSTOMER') and ENTITY_ID (= parent _id) are not repeated; a non-CUSTOMER entity_type row fails the load (0 live)",
                           bound={"max_elements": 64, "basis": "live max 5, p99 3; 7 distinct attribute names; 64 is the validator ceiling"},
                           parent_bytes_table="CUSTOMER_MASTER",
                           extra={"fields": [
                               {"field": "eavId", "source": "ENTITY_ATTR_VALUE.EAV_ID", "bson": "long", "nullable": False, "note": "NUMBER(14,0)"},
                               {"field": "name", "source": "ENTITY_ATTR_VALUE.ATTR_NAME", "bson": "string", "nullable": False, "note": "verbatim"},
                               {"field": "value", "source": "ENTITY_ATTR_VALUE.ATTR_VALUE", "bson": "string", "nullable": True, "note": "verbatim free text; this is the recon value (fixture anomaly eav_boolean_spellings compares the (name, value) vocabulary)"},
                               {"field": "type", "source": "ENTITY_ATTR_VALUE.ATTR_TYPE", "bson": "string", "nullable": True, "note": "verbatim ('STR' for every live row)"},
                               {"field": "createdDt", "source": "ENTITY_ATTR_VALUE.CREATED_DT", "bson": "string", "nullable": True, "note": "DD-MON-YY text kept verbatim"},
                               {"field": "createdDate", "source": "ENTITY_ATTR_VALUE.CREATED_DT (derived)", **DD_MON_YY},
                               {"field": "typed", "source": "ENTITY_ATTR_VALUE.ATTR_VALUE (derived)", "bson": "bool | decimal | string", "nullable": True,
                                "note": "typed reading of value: bool when value (trimmed, upper-cased) is in {Y,TRUE,1} -> true or {N,FALSE,0} -> false; decimal (Decimal128) when it parses as a plain decimal number; otherwise the string itself. Derived only; never used by recon"},
                           ]})],
        "indexes": [
            ix("ix_customers_tenant_seq", {"tenantId": 1, "custSeqNo": 1}, ["GET /customer (facade)"],
               "{tenantId: t} sort custSeqNo limit 1 (facade FETCH FIRST 1 ROWS ONLY ORDER BY cust_seq_no); 48-8,575 customers per tenant_id live, so the index does the ordering"),
            ix("ix_customers_conversion_batch", {"conversionBatchNo": 1}, ["reports.py BALANCES_SQL"],
               "$group by conversionBatchNo summing curBalAmt/pastDueAmt (reports bypass the backend switch, U4)"),
            ix("uq_customers_attributes_eav_id", {"attributes.eavId": 1}, ["recon"],
               "PK_ENTITY_ATTR_VALUE carried across documents as a unique multikey index (partial: 71.7% of customers have no attributes)",
               unique=True, partialFilterExpression={"attributes.eavId": {"$exists": True}}),
        ],
        "writes": {"post_cutover": "no app write path exists today (customer_master: 3 reads, 0 writes); loads are bulk"},
        "notes": [
            "Live TENANTS->CUSTOMER_MASTER join: 0 of 25,000 customer tenant_id values match a TENANTS row (50 distinct tenant_ids, 48-8,575 customers each). tenantId is therefore a plain string, not a validated reference, exactly as in Oracle (no FK).",
            "DD-MON-YY VARCHAR2 dates (signupDt, lastActivityDt, lastInvoiceDt, lastPaymentDt, terminateDt, udfDt01..10) keep the verbatim text plus a typed *Date sibling that is absent for the 50 dirty_dates rows.",
            "relatedAcctIds / childAcctIds / promoCodesCsv keep the verbatim CSV plus a *List sibling that is absent for the 31 malformed_csv_lists rows.",
        ],
    })

    # --- customers_hist (d-history-tables) --------------------------------------------------
    cols.append({
        "name": "customers_hist", "source_tables": ["CUSTOMER_MASTER_HIST"], "kind": "history",
        "decision": "d-history-tables",
        "why": "full-row copies from TRG_CUSTOMER_MASTER_HIST (0 live rows, SEQ_CUSTOMER_MASTER_HIST at 1); write-only, unbounded over time -> separate collection.",
        "_id": {"from": ["CUSTOMER_MASTER_HIST.HIST_ID"], "shape": "long", "rule": "SEQ_CUSTOMER_MASTER_HIST value kept; app-issued after cutover"},
        "fields": fields_for(t["CUSTOMER_MASTER_HIST"], money_cols, skip={"HIST_ID"}),
        "embedded": [],
        "indexes": [ix("ix_customers_hist_cust", {"custId": 1, "_id": 1}, ["recon"], "history of one customer in write order; no app read path")],
        "writes": {"post_cutover": "any future customer update copies the pre-image here in the same transaction (migrate-as-logic replacement for the trigger)"},
        "notes": ["Same flat column carry and DD-MON-YY/CSV sibling rules as customers; attributes are not versioned (Oracle has no EAV history)."],
    })

    # --- invoice_feed (INVOICE_HEADER + INVOICE_LINE) ----------------------------------------
    hl = fan["INVOICE_HEADER->INVOICE_LINE"]
    line_fields = fields_for(t["INVOICE_LINE"], money_cols, skip={"INVOICE_ID"})
    cols.append({
        "name": "invoice_feed", "source_tables": ["INVOICE_HEADER", "INVOICE_LINE"], "kind": "report-feed",
        "decision": "d-feed-embed-lines (this spec): one-to-few, embed matched lines; orphans quarantined",
        "why": "the mainframe bulk feed read only by services/legacy-billing/app/reports.py (STATUS_SQL groups headers by batch_no; LINE_SQL joins lines to headers by invoice_id and groups by status and line type). Lines are 1-23 per header live (p99 15), 291 bytes max, never read without the header join, and never written by the app -> embed under the header so LINE_SQL is a single $unwind. Kept apart from 'invoices': different key space (INVOICE_ID vs INVOICES.ID), different columns, a different owner (mainframe conversion) and no entrypoint reads both.",
        "_id": {"from": ["INVOICE_HEADER.INVOICE_ID"], "shape": "string", "rule": "INVOICE_HEADER PK kept verbatim"},
        "fields": fields_for(t["INVOICE_HEADER"], money_cols, skip={"INVOICE_ID"}),
        "embedded": [embed("lines", "INVOICE_LINE", "INVOICE_HEADER->INVOICE_LINE",
                           order="lineNo ascending, then lineId (lineNo is NOT unique: 19,512 duplicate (invoice_id, line_no) groups live)",
                           identity="lines[].lineId keeps INVOICE_LINE.LINE_ID (the only key); lineNo is data, not identity; the feed's denormalised invoiceNo/custId/custNo/custName/tenantId/invoiceDt/batchNo stay on each line verbatim because they can disagree with the header and recon compares them",
                           bound={"max_elements": 200, "basis": "live max 23, p99 15; 200 is the validator ceiling (projected 200 x 291 x 2 + 152 bytes ~ 117 KB, 0.7% of the limit)"},
                           parent_bytes_table="INVOICE_HEADER",
                           extra={"fields": line_fields})],
        "indexes": [
            ix("ix_invoice_feed_batch", {"batchNo": 1}, ["reports.py STATUS_SQL", "reports.py LINE_SQL"],
               "$group by batchNo (+ statusCd decoded via codes) over headers; LINE_SQL $unwind lines then $group by statusCd, lines.lineTypeCd"),
            ix("ix_invoice_feed_status_due", {"statusCd": 1, "dueDate": 1}, ["overdue by due date (ticket s3.1)"],
               "{statusCd: s, dueDate: {$lt: asOf}}: the only due date in the estate; no current reader (reports.py groups, the facade's overdue uses invoices.issuedAt). Declared so the typed dueDate sibling is queryable; build is deferred until a reader exists",
               build="deferred"),
            ix("uq_invoice_feed_lines_line_id", {"lines.lineId": 1}, ["recon"],
               "PK_INVOICE_LINE carried across documents as a unique multikey index",
               unique=True, partialFilterExpression={"lines.lineId": {"$exists": True}}),
        ],
        "writes": {"post_cutover": "none from the app; feed loads are bulk and idempotent on _id / lines.lineId"},
        "notes": ["INVOICE_HEADER count 18,750 but 18,782 distinct INVOICE_ID values among lines: the 32 extra ids (37 rows) are the orphans below."],
    })

    cols.append({
        "name": "invoice_feed_quarantine", "source_tables": ["INVOICE_LINE"], "kind": "quarantine",
        "why": f"the {card['orphans']['INVOICE_LINE_without_INVOICE_HEADER']} live INVOICE_LINE rows whose INVOICE_ID has no INVOICE_HEADER (fixture anomaly orphaned_rows, INVOICE_NO '<NS>-GHOST-<n>') have no parent document to embed into. They are carried one document per row so the row-diff stays 0 (tolerances.planted_anomalies: quarantined_rows_must_match exact) and LINE_SQL's inner join still excludes them.",
        "_id": {"from": ["INVOICE_LINE.LINE_ID"], "shape": "string", "rule": "INVOICE_LINE PK kept verbatim"},
        "fields": fields_for(t["INVOICE_LINE"], money_cols, skip={"LINE_ID"}) + [
            {"field": "quarantine", "source": "(derived)", "bson": "object", "nullable": False,
             "note": "{reason: 'orphaned_rows', rule: 'INVOICE_ID not in invoice_feed._id', capturedAt: date}"}],
        "embedded": [],
        "indexes": [ix("ix_invoice_feed_quarantine_invoice", {"invoiceId": 1}, ["recon", "reconciliation of late-arriving headers"],
                       "{invoiceId: id}: if a header arrives later the loader moves the rows into invoice_feed.lines in one transaction")],
        "writes": {"post_cutover": "loader only"},
        "notes": ["A line is quarantined by parent absence only; duplicate (invoice_id, line_no) groups are NOT an anomaly in the source (no unique key exists) and are embedded as-is."],
    })

    return cols


# ----------------------------------------------------------------------------------------------
def build() -> dict:
    census = load("census.json")
    buckets = load("census/buckets.json")
    ap = load("access_patterns/access_patterns.json")
    tol = load("tolerances.json")
    fixture = load("fixtures/demo.json")
    card = load("mapping/cardinality.json")

    t = {e["name"]: e for e in census["tables"]}
    migrate = sorted(k.split(":", 1)[1] for k, v in buckets["objects"].items() if k.startswith("TABLE:") and v["bucket"] == "migrate")
    money_cols = {(tbl, c) for tbl, cs in tol["numeric_tolerances"]["money"]["columns"].items() for c in cs}

    collections = model(t, money_cols, card)

    # table -> target map (every migrate table lands exactly once)
    tables = {}
    for c in collections:
        for e in c["embedded"]:
            tables.setdefault(e["source_table"], []).append({"collection": c["name"], "mode": "embedded", "path": e["path"]})
        for st in c["source_tables"]:
            if st not in {e["source_table"] for e in c["embedded"]}:
                mode = "quarantine" if c["kind"] == "quarantine" else "collection"
                tables.setdefault(st, []).append({"collection": c["name"], "mode": mode, "path": None})
    table_map = {}
    for tbl in migrate:
        hits = tables.get(tbl, [])
        if not hits:
            raise SystemExit(f"migrate table {tbl} is not mapped")
        primary = [h for h in hits if h["mode"] != "quarantine"]
        if len(primary) != 1:
            raise SystemExit(f"migrate table {tbl} mapped {len(primary)} times: {hits}")
        table_map[tbl] = {"bucket": "migrate", "rows_live": census["row_counts"]["tables"][tbl], **primary[0],
                          "quarantine": [h["collection"] for h in hits if h["mode"] == "quarantine"] or None}
    extra = set(tables) - set(migrate)
    if extra:
        raise SystemExit(f"non-migrate tables mapped: {sorted(extra)}")

    # money coverage: every tolerances money column appears as a decimal field exactly once
    decimal_fields = set()
    for c in collections:
        for f in c["fields"]:
            if f["bson"] == "decimal":
                decimal_fields.add(tuple(f["source"].split(".")))
        for e in c["embedded"]:
            for f in e.get("fields", []):
                if f["bson"] == "decimal":
                    decimal_fields.add(tuple(f["source"].split(".")))
    want = {(tb.upper(), col.upper()) for tb, col in money_cols}
    missing = want - decimal_fields
    if missing:
        raise SystemExit(f"money columns without a Decimal128 field: {sorted(missing)}")

    # index fields exist in the collection (top-level or embedded path)
    def field_names(c):
        names = {"_id"} | {f["field"] for f in c["fields"]}
        for e in c["embedded"]:
            names.add(e["path"])
            for f in e.get("fields", []):
                names.add(f"{e['path']}.{f['field']}")
        return names
    index_count = 0
    for c in collections:
        names = field_names(c)
        for i in c["indexes"]:
            index_count += 1
            for k in i["keys"]:
                if k not in names:
                    raise SystemExit(f"{c['name']}.{i['name']} indexes unknown field {k}")

    # entrypoint coverage: every access_patterns.json entrypoint's read/write tables map to collections
    lower = {k.lower(): v for k, v in table_map.items()}
    coverage = {}
    for name, ep in ap["entrypoints"].items():
        touched = sorted(set(ep["reads"]) | set(ep["writes"]))
        colls = sorted({lower[x]["collection"] for x in touched})
        served_by = sorted({i["name"] for c in collections if c["name"] in colls for i in c["indexes"]
                            if any(s.split(" ")[0] == name for s in i["serves"])})
        coverage[name] = {"plsql": ep["plsql"], "tables": touched, "collections": colls, "indexes": served_by,
                          "audit_write": ep["audit"], "atomic_unit": ep["atomic_unit"]}

    atomic_units = [
        {"name": "issue_invoice", "collections": ["rating_periods", "invoices", "credit_notes"],
         "documents": "1 rating_periods (header + result) + 1 invoices (header + lines) + N credit_notes",
         "mechanism": "multi-document transaction (3 collections, single replica set); audit insert outside it",
         "oracle": "sp_issue_invoice: one transaction, FOR UPDATE on credit_notes"},
        {"name": "change_plan", "collections": ["subscriptions", "subscriptions_hist"],
         "documents": "close-outs + 1 insert + pre-image copies", "mechanism": "multi-document transaction",
         "oracle": "sp_change_plan: FOR UPDATE row locks to commit; trigger copies"},
        {"name": "suspend_overdue (per tenant)", "collections": ["tenants", "subscriptions", "subscriptions_hist", "notifications"],
         "documents": "1 tenant + its subscriptions (+ copies) + 1 notification", "mechanism": "multi-document transaction per tenant",
         "oracle": "sp_suspend_overdue: one transaction for all tenants; the Mongo unit is per tenant, the unique notification key makes a rerun idempotent"},
        {"name": "ensure_tenant", "collections": ["tenants", "subscriptions"], "documents": "1 + 1",
         "mechanism": "multi-document transaction", "oracle": "facade bootstrap commit before the event insert"},
        {"name": "finalize_rating", "collections": ["rating_periods"], "documents": "1 (period + embedded result)",
         "mechanism": "single-document write (atomic by construction)", "oracle": "sp_finalize_rating: period upsert + result upsert in one transaction"},
        {"name": "schedule_dunning", "collections": ["dunning_attempts"], "documents": "1 per overdue invoice",
         "mechanism": "single-document inserts; uq_dunning_attempts_invoice_attempt rejects duplicates", "oracle": "sp_schedule_dunning: one transaction"},
        {"name": "usage ingest", "collections": ["usage_events"], "documents": "1", "mechanism": "single-document insert; duplicate _id -> 'duplicate'",
         "oracle": "POST /internal/usage/events: second transaction after ensure_tenant"},
        {"name": "log_msg (audit)", "collections": ["billing_audit_log"], "documents": "1",
         "mechanism": "single-document insert outside any transaction/session; failure raised to the caller (bd-log-msg-swallow)", "oracle": "PRAGMA AUTONOMOUS_TRANSACTION; WHEN OTHERS THEN ROLLBACK"},
    ]

    anomalies = {a["kind"]: {"count": a.get("count"), "handling": h} for a, h in zip(
        fixture["anomalies"],
        ["invoice_feed_quarantine (one document per orphan line)",
         "customers: verbatim *Dt string + absent typed *Date sibling",
         "customers: verbatim CSV string + absent *List sibling",
         "customers.attributes[].value verbatim; attributes[].typed is derived only"])}
    assert [a["kind"] for a in fixture["anomalies"]] == ["orphaned_rows", "dirty_dates", "malformed_csv_lists", "eav_boolean_spellings"]

    spec = {
        "kind": "mapping-spec",
        "version": 1,
        "plan_step": "s3.1-mapping-spec",
        "run_branch": RUN_BRANCH,
        "generator": "migration/billing/mapping/build_mapping_spec.py (run with --check to verify this file and its invariants)",
        "inputs": {
            "census": {"path": "migration/billing/census.json", "captured_at": census["captured_at"], "pr": 1772},
            "buckets": {"path": "migration/billing/census/buckets.json", "migrate_tables": len(migrate)},
            "access_patterns": {"path": "migration/billing/access_patterns/access_patterns.json", "md": "migration/billing/access_patterns.md", "entrypoints": len(ap["entrypoints"]), "pr": 1774},
            "tolerances": {"path": "migration/billing/tolerances.json", "money_columns": len(money_cols)},
            "fixture": {"path": "migration/billing/fixtures/demo.json", "pr": 1773},
            "cardinality": {"path": "migration/billing/mapping/cardinality.json", "captured_at": card["captured_at"],
                            "source": card["source"], "note": "read-only live measurement; observed bounds, not limits"},
        },
        "decisions": {
            "applied": {
                "d-embed-invoice-lines": "Embed lines in the invoice -> invoices.lines",
                "d-customer-eav": "One customer doc, EAV embedded and typed -> customers.attributes[] with value (verbatim) + typed",
                "d-history-tables": "Separate history collections -> subscriptions_hist, customers_hist",
                "d-migration-db": f"Fresh database ow_tp_billing_<run> per run (UNT-3) -> {DATABASE}",
                "d-audit-retention": "match-live (default; the live purge job is DISABLED) -> billing_audit_log has no TTL index and no purge; ttl-90d is the human's alternative (billing_audit_log.retention)",
            },
            "made_here": {
                "d-embed-rating-result": "RATING_RESULTS is a 1:1 child written with its period (md5(period_id) id, same transaction) and never read alone -> rating_periods.result sub-document",
                "d-reference-usage-events": "USAGE_EVENTS append-heavy and unbounded -> own collection, {tenantId, occurredAt} index",
                "d-feed-embed-lines": "INVOICE_LINE embedded under INVOICE_HEADER (1-23 live, read only via the header join); orphans to invoice_feed_quarantine",
                "d-flat-customer-columns": "all 155 CUSTOMER_MASTER columns carried flat (camelCase) for SELECT * parity; regrouping deferred to the service refactor",
                "d-null-absent": "an Oracle NULL is an absent field; '' is the string '' (tolerances.null.null_equals_empty_string = false)",
            },
            "open": {
                "d-cdc-connector": "human decision on s2.3-dependency-register (off-repo CDC principal); not taken here - nothing in this spec depends on it except who writes the delta after the initial load (s5.1)",
                "d-mainframe-load": "human decision on s2.3-dependency-register (CUSTBILL month-end load); not taken here - it names the post-cutover loader of invoice_feed / invoice_feed_quarantine, whose shape is fixed above",
                "bd-overdue-status-owner": "who sets invoices.statusCd = 40 after cutover; nobody in the app does today (incompatibilities.behavior_differences)",
            },
        },
        "target": {
            "system": "mongodb-atlas", "uri_secret": "MONGODB_ATLAS_URI", "database": DATABASE,
            "cluster_tier_note": "M0 (512 MB): SCALE=demo data only; Atlas recommends keeping collections + indexes small on shared tiers - this spec declares 16 collections and %d secondary indexes (1 deferred)",
            "writes_limited_to": DATABASE,
            "collection_prefix": "none (the database name scopes the run; collection names are the plain nouns)",
        },
        "guidance": DOCS,
        "conventions": {
            "field_names": "camelCase of the Oracle column (CUST_SEQ_NO -> custSeqNo, ADDR_LINE_1 -> addrLine1); the FK column that names the parent of an embedded child is not repeated inside the child",
            "null": "Oracle NULL -> field absent; recon treats absent as NULL and '' as ''",
            "strings": "VARCHAR2/CHAR verbatim, no trim, no case folding (tolerances.string)",
            "yn_flags": "CHAR(1) Y/N kept as the string 'Y'/'N' (absent when NULL); no boolean coercion, so recon is exact",
            "codes": "*_CD columns stay int codes; decoding goes through the codes collection exactly as Oracle joins CODES",
            "dates": {"DATE": "BSON date (UTC)", "TIMESTAMP(6)": "BSON date (ms); sub-ms digits dropped, recon at whole seconds (tolerances.timestamp.absolute_seconds = 0)",
                      "VARCHAR2 *_DT": "verbatim text + typed *Date sibling (absent when invalid) - see legacy_representations.dd_mon_yy_string_dates in the fixture"},
            "csv_lists": "verbatim text + *List sibling (absent when malformed)",
            "money": {"bson": "Decimal128", "source": "Oracle NUMBER(p,s>0) read as decimal.Decimal, written as bson.Decimal128; float/double never used in the loader, the app or the recon",
                      "columns": {tb: cs for tb, cs in sorted(tol["numeric_tolerances"]["money"]["columns"].items())}},
            "integers": "NUMBER(p,0): int for p <= 9, long otherwise (BSON int32/int64)",
        },
        "key_strategy": {
            "rule": "Oracle primary key kept as _id, verbatim, for every collection; compound PK (CODES) as an embedded-document _id with fixed key order",
            "sequence_ids": {
                "carried": "sequence-generated ids (SEQ_* via TRG_*_SEQ / TRG_BILLING_AUDIT_LOG_ID) are copied as BSON long _id / field values",
                "post_cutover": "new ids are issued by the application, not by the database: one 'counters' document per sequence is NOT used; the app seeds its allocator from max(_id)+1 at startup for each history/audit collection (write-only, single writer) and from max(custSeqNo)+1 for customers; uuid-keyed collections keep their existing generators (bridge event id, f_md5_uuid-derived ids)",
                "sequences": {s["sequence_name"]: {"last_number": s["last_number"], "lands_in": {
                    "SEQ_BILLING_AUDIT_LOG": "billing_audit_log._id", "SEQ_CUSTOMER_MASTER": "customers.custSeqNo",
                    "SEQ_CUSTOMER_MASTER_HIST": "customers_hist._id", "SEQ_ENTITY_ATTR_VALUE": "customers.attributes[].eavId",
                    "SEQ_SUBSCRIPTIONS_HIST": "subscriptions_hist._id"}[s["sequence_name"]]} for s in census["sequences"]},
            },
            "embedded_children": "keep their Oracle PK as an element field (lines[].id, lines[].lineId, attributes[].eavId, result.id) and the PK is enforced across documents by a partial unique multikey index",
            "no_objectid": "ObjectId is not used anywhere; every _id is the Oracle key",
        },
        "size_guard": {
            "bson_limit_bytes": BSON_MAX,
            "policy": "an array is embedded only when (a) the access patterns never read the child alone, (b) the child is written with the parent, and (c) the live child-per-parent maximum is bounded by the writing logic; every embedded array declares max_elements (validator maxItems), a projected worst-case document size from live row-byte proxies, and the writer's 12 MiB pre-check",
            "embedded_arrays": [{"collection": c["name"], "path": e["path"], "observed_max": e["observed"]["children_per_parent"]["max"],
                                 "max_elements": e["bound"]["max_elements"], "projected_max_doc_bytes": e["size_guard"]["projected_max_doc_bytes"],
                                 "pct_of_limit": round(100.0 * e["size_guard"]["projected_max_doc_bytes"] / BSON_MAX, 3)}
                                for c in collections for e in c["embedded"] if e["relationship"] != "one-to-one"],
            "not_embedded_because_unbounded": [
                {"child": "USAGE_EVENTS", "parent": "TENANTS", "observed_max": card["fanout"]["TENANTS->USAGE_EVENTS"]["children_per_parent"]["max"], "reason": "append-only ingest, no product bound"},
                {"child": "CUSTOMER_MASTER", "parent": "TENANTS", "observed_max": card["fanout"]["TENANTS->CUSTOMER_MASTER"]["children_per_parent"]["max"], "reason": "8,575 x 387 bytes already 3.3 MB for one tenant_id; grows with conversion batches"},
                {"child": "INVOICES", "parent": "TENANTS", "observed_max": card["fanout"]["TENANTS->INVOICES"]["children_per_parent"]["max"], "reason": "one per period forever; read by status across tenants"},
                {"child": "SUBSCRIPTIONS_HIST", "parent": "SUBSCRIPTIONS", "observed_max": card["fanout"]["SUBSCRIPTIONS->SUBSCRIPTIONS_HIST"]["children_per_parent"]["max"], "reason": "write-only history (d-history-tables)"},
                {"child": "CUSTOMER_MASTER_HIST", "parent": "CUSTOMER_MASTER", "observed_max": card["fanout"]["CUSTOMER_MASTER->CUSTOMER_MASTER_HIST"]["children_per_parent"]["max"], "reason": "write-only history (d-history-tables)"},
                {"child": "DUNNING_ATTEMPTS", "parent": "INVOICES", "observed_max": card["fanout"]["INVOICES->DUNNING_ATTEMPTS"]["children_per_parent"]["max"], "reason": "read across tenants by scheduledFor (GET /admin/dunning)"},
            ],
        },
        "collections": collections,
        "tables": table_map,
        "access_pattern_coverage": coverage,
        "facade_dominant_queries": {
            "tenant + period": "rating_periods.uq_rating_periods_tenant_start {tenantId, periodStart}; usage window usage_events.ix_usage_events_tenant_occurred {tenantId, occurredAt}",
            "invoice by tenant/status": "invoices.ix_invoices_tenant_issued {tenantId, issuedAt, _id} (status filtered in the per-tenant result set; status across tenants -> ix_invoices_status_issued)",
            "overdue by due date": "invoices.ix_invoices_status_issued {statusCd, issuedAt, _id} (fn_overdue_accounts: status 40 + issued_at as YYYYMMDD; INVOICES has no due date); invoice_feed.ix_invoice_feed_status_due {statusCd, dueDate} declared for the feed's DUE_DT, build deferred (no reader)",
        },
        "atomic_units": atomic_units,
        "anomaly_handling": anomalies,
        "out_of_scope": [
            "FIXTURE_META (not in the migrate bucket; census coverage only)",
            "collection creation, validators and index builds (s3.4 recon/load scripts consume this spec)",
            "the application code that implements the dispositions in 'incompatibilities' (billing service refactor, CDC connector, mainframe loader)",
        ],
        "incompatibilities": incompatibilities(census, buckets),
        "stats": {"collections": len(collections), "secondary_indexes": index_count,
                  "deferred_indexes": sum(1 for c in collections for i in c["indexes"] if i["options"].get("build") == "deferred"),
                  "embedded_arrays": sum(1 for c in collections for e in c["embedded"] if e["relationship"] != "one-to-one"),
                  "embedded_subdocuments": sum(1 for c in collections for e in c["embedded"] if e["relationship"] == "one-to-one"),
                  "migrate_tables": len(migrate), "fields": sum(len(c["fields"]) + sum(len(e.get("fields", [])) for e in c["embedded"]) for c in collections)},
    }
    spec["target"]["cluster_tier_note"] = spec["target"]["cluster_tier_note"] % index_count
    return spec


def main() -> int:
    apr = argparse.ArgumentParser()
    apr.add_argument("--check", action="store_true", help="verify the committed spec equals the regenerated one")
    apr.add_argument("--out", default=str(OUT))
    args = apr.parse_args()
    spec = build()
    text = json.dumps(spec, indent=2, sort_keys=False) + "\n"
    if args.check:
        current = Path(args.out).read_text(encoding="utf-8")
        if current != text:
            print(f"FAIL {args.out} differs from the generated spec; rerun build_mapping_spec.py", file=sys.stderr)
            return 1
        s, inc = spec["stats"], spec["incompatibilities"]["coverage"]
        print(f"OK {args.out}: {s['migrate_tables']} migrate tables -> {s['collections']} collections, "
              f"{s['embedded_arrays']} embedded arrays + {s['embedded_subdocuments']} sub-document, {s['secondary_indexes']} indexes "
              f"({s['deferred_indexes']} deferred), {s['fields']} fields, {len(spec['access_pattern_coverage'])} entrypoints covered, "
              f"{inc['dispositions']} dispositions / {inc['behavior_differences']} behavior differences ({len(inc['open'])} open)")
        return 0
    Path(args.out).write_text(text, encoding="utf-8")
    print(f"wrote {args.out} ({len(text)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
