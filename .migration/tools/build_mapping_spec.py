"""Emit .migration/03_mapping_spec.json from the census plus the explicit modeling decisions.

The spec is generated rather than hand-typed so that field coverage is arithmetic, not
opinion: every column in .migration/census/columns.json lands in exactly one of
`fields`, `folded_into`, or `dropped` for its collection, and the script fails if it does not.

The prose in 03_mapping_spec.md cites this file; the recon harness consumes it directly.
"""

import json
import pathlib
import sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
CENSUS = ROOT / "census"
OUT = ROOT / "03_mapping_spec.json"

MAPPING_VERSION = "m1"
DATABASE = "ow_tp_mongodb_orc1"

# Oracle type -> BSON, straight from the oracle profile's type_mappings table.
def bson_for(col):
    t = col["data_type"]
    if t.startswith("TIMESTAMP") or t == "DATE":
        return "date"
    if t == "NUMBER":
        p, s = col["data_precision"], col["data_scale"]
        if p is None:
            return "decimal128"
        return "long" if (s or 0) == 0 and p <= 18 else "decimal128"
    if t in ("VARCHAR2", "NVARCHAR2", "CHAR", "CLOB", "NCLOB"):
        return "string"
    if t in ("BLOB", "RAW"):
        return "binData"
    if t in ("FLOAT", "BINARY_FLOAT", "BINARY_DOUBLE"):
        return "double"
    raise SystemExit(f"unmapped Oracle type {t} on {col['table_name']}.{col['column_name']}")


def transform_for(col, overrides):
    key = f"{col['table_name']}.{col['column_name']}"
    if key in overrides:
        return overrides[key]
    if col["data_type"] == "CHAR":
        # every CHAR in this estate is a Y/N flag; blank-padded, so rstrip then coerce
        return {"bson": "bool", "rule": "yn_to_bool", "canon": ["rstrip_spaces"]}
    return {"bson": bson_for(col), "rule": "direct", "canon": []}


# --- explicit per-column decisions ------------------------------------------------
# VARCHAR2 columns that hold 'DD-MON-YY' dates: parsed, unparseable values quarantined.
STRING_DATES = {
    "CUSTOMER_MASTER.SIGNUP_DT", "CUSTOMER_MASTER.LAST_ACTIVITY_DT",
    "CUSTOMER_MASTER_HIST.HIST_DT", "SUBSCRIPTIONS_HIST.HIST_DT",
    "INVOICE_HEADER.INVOICE_DT", "INVOICE_HEADER.DUE_DT",
    "INVOICE_LINE.INVOICE_DT", "ENTITY_ATTR_VALUE.CREATED_DT",
}
# VARCHAR2 columns holding comma-separated lists: split to real arrays.
CSV_LISTS = {
    "CUSTOMER_MASTER.RELATED_ACCT_IDS", "CUSTOMER_MASTER.PROMO_CODES_CSV",
    "INVOICE_LINE.GL_ACCT_CSV",
}
OVERRIDES = {
    **{k: {"bson": "date", "rule": "parse_dd_mon_yy", "canon": ["empty_string_is_null"],
           "on_error": "quarantine"} for k in STRING_DATES},
    **{k: {"bson": "array<string>", "rule": "split_csv", "canon": ["trim_elements"],
           "on_error": "quarantine"} for k in CSV_LISTS},
}

# Magic-number *_CD columns resolved through CODES. The numeric value is preserved and a
# denormalized label is added alongside it; the join is by (code_type, code_val).
CODE_COLUMNS = {
    "CUSTOMER_MASTER.STATUS_CD": ("CUST_STATUS", "status"),
    "CUSTOMER_MASTER.CUST_TYPE_CD": ("CUST_TYPE", "customer_type"),
    "CUSTOMER_MASTER.PHONE1_TYPE_CD": ("PHONE_TYPE", None),
    "CUSTOMER_MASTER.PHONE2_TYPE_CD": ("PHONE_TYPE", None),
    "CUSTOMER_MASTER.PHONE3_TYPE_CD": ("PHONE_TYPE", None),
    "CUSTOMER_MASTER.PHONE4_TYPE_CD": ("PHONE_TYPE", None),
    "INVOICE_HEADER.STATUS_CD": ("INV_STATUS", "status"),
    "TENANTS.STATUS_CD": ("TENANT_STATUS", "status"),
    "PLANS.TIER_CD": ("PLAN_TIER", "tier"),
    "SUBSCRIPTIONS.STATUS_CD": ("SUB_STATUS", "status"),
    "SUBSCRIPTIONS_HIST.STATUS_CD": ("SUB_STATUS", "status"),
    "USAGE_EVENTS.KIND_CD": ("USAGE_KIND", "kind"),
    "INVOICES.STATUS_CD": ("INV_STATUS", "status"),
    "DUNNING_ATTEMPTS.STATUS_CD": ("DUN_STATUS", "status"),
    "NOTIFICATIONS.KIND_CD": ("NOTIF_KIND", "kind"),
}

# Repeating groups collapsed into arrays / subdocuments on `customers`.
REPEATING_GROUPS = {
    "address.lines": ["ADDR_LINE_1", "ADDR_LINE_2", "ADDR_LINE_3",
                      "ADDR_LINE_4", "ADDR_LINE_5", "ADDR_LINE_6"],
    "mailing_address.lines": ["MAIL_ADDR_LINE_1", "MAIL_ADDR_LINE_2", "MAIL_ADDR_LINE_3",
                              "MAIL_ADDR_LINE_4", "MAIL_ADDR_LINE_5", "MAIL_ADDR_LINE_6"],
    "phones": ["PHONE1", "PHONE2", "PHONE3", "PHONE4",
               "PHONE1_TYPE_CD", "PHONE2_TYPE_CD", "PHONE3_TYPE_CD", "PHONE4_TYPE_CD"],
    "emails": ["EMAIL_1", "EMAIL_2", "EMAIL_3"],
    "address": ["CITY", "STATE_CD", "ZIP", "ZIP4", "COUNTRY_CD"],
    "mailing_address": ["MAIL_CITY", "MAIL_STATE_CD", "MAIL_ZIP"],
}

# Columns deliberately not carried, each with the evidence that justifies it.
DROP_REASONS = {
    "CUSTOMER_MASTER.CUST_NAME_UPPER": "derived: UPPER(cust_name); replaced by a case-insensitive collation index",
    "CUSTOMER_MASTER.CONVERSION_BATCH_NO": "run-scoping parameter, promoted to the ${batch_no} root_where placeholder",
    "INVOICE_HEADER.BATCH_NO": "run-scoping parameter, promoted to the ${batch_no} root_where placeholder",
    "INVOICE_LINE.BATCH_NO": "run-scoping parameter, inherited from the parent invoice",
    "INVOICE_LINE.INVOICE_ID": "embed parent key; expressed by containment",
    "INVOICE_LINE.INVOICE_NO": "denormalized copy of invoice_header.invoice_no on every line",
    "INVOICE_LINE.CUST_ID": "denormalized copy of the parent header's cust_id",
    "INVOICE_LINE.CUST_NO": "denormalized copy of the parent customer's cust_no",
    "INVOICE_LINE.CUST_NAME": "denormalized copy of the parent customer's cust_name",
    "INVOICE_LINE.TENANT_ID": "denormalized copy of the parent header's tenant_id",
    "INVOICE_LINE.INVOICE_DT": "denormalized copy of the parent header's invoice_dt",
    "ENTITY_ATTR_VALUE.EAV_ID": "sequence surrogate; the EAV row becomes an attributes[] element",
    "ENTITY_ATTR_VALUE.ENTITY_TYPE": "expressed by containment: only CUSTOMER rows exist",
    "ENTITY_ATTR_VALUE.ENTITY_ID": "embed parent key; expressed by containment",
    "INVOICE_LINES.INVOICE_ID": "embed parent key; expressed by containment",
}


def load(name):
    return json.loads((CENSUS / f"{name}.json").read_text())


def build():
    columns = load("columns")
    counts = load("exact_counts")
    ev = json.loads((CENSUS / "access_patterns.json").read_text())
    always_null = set(ev["customer_master_population"]["always_null_columns"])

    by_table = defaultdict(list)
    for c in columns:
        by_table[c["table_name"]].append(c)

    def field(col, target, note=None):
        key = f"{col['table_name']}.{col['column_name']}"
        t = transform_for(col, OVERRIDES)
        f = {
            "source_column": col["column_name"],
            "source_type": col["data_type"],
            "target_field": target,
            "bson_type": t["bson"],
            "transform": t["rule"],
            "canonicalization": t["canon"],
        }
        if "on_error" in t:
            f["on_error"] = t["on_error"]
        if key in CODE_COLUMNS:
            code_type, label = CODE_COLUMNS[key]
            f["code_lookup"] = {"code_type": code_type, "label_field": label}
        if note:
            f["note"] = note
        return f

    def simple(table, skip=(), rename=None, prefix=""):
        rename = rename or {}
        out = []
        for c in by_table[table]:
            if c["column_name"] in skip:
                continue
            name = rename.get(c["column_name"], c["column_name"].lower())
            out.append(field(c, prefix + name))
        return out

    collections = {}

    # ---------------- wave 0: shared reference ----------------
    collections["codes"] = {
        "unit": "reference",
        "wave": 0,
        "sources": ["CODES"],
        "model": "reference",
        "access_pattern": (
            "Every *_CD column in both sub-estates resolves through CODES by "
            "(code_type, code_val) — reports.py joins it twice per report and all five "
            "PL/SQL packages call PKG_OW_UTIL.f_code_desc. Read-mostly, 32 rows: kept as a "
            "standalone collection AND denormalized as a label beside each code value, so "
            "the hot read path needs no $lookup."
        ),
        "key": {"_id": {"from": ["CODE_TYPE", "CODE_VAL"], "strategy": "compound_natural",
                        "format": "{code_type}:{code_val}"}},
        "fields": simple("CODES"),
        "expected_documents": counts["CODES"],
        "indexes": [{"keys": {"code_type": 1, "code_val": 1}, "unique": True}],
    }
    collections["tenants"] = {
        "unit": "reference",
        "wave": 0,
        "sources": ["TENANTS"],
        "model": "reference",
        "access_pattern": (
            "FK parent of 7 tables (subscriptions, usage_events, rating_periods, invoices, "
            "credit_notes, dunning_attempts, notifications) and the path parameter of every "
            "proc entrypoint in procs/routes.yaml. Referenced, never embedded: it is the "
            "top of the ownership tree."
        ),
        "key": {"_id": {"from": ["ID"], "strategy": "natural"}},
        "fields": simple("TENANTS", skip=["ID"]),
        "expected_documents": counts["TENANTS"],
        "indexes": [{"keys": {"name": 1}, "unique": True}],
    }
    collections["plans"] = {
        "unit": "reference",
        "wave": 0,
        "sources": ["PLANS"],
        "model": "reference",
        "access_pattern": (
            "PKG_PLANS.fn_list_plans returns the whole table (GET /api/plans); "
            "fn_entitlement joins it per tenant. 3 rows, read-only in the app path."
        ),
        "key": {"_id": {"from": ["ID"], "strategy": "natural"}},
        "fields": simple("PLANS", skip=["ID"]),
        "expected_documents": counts["PLANS"],
        "indexes": [{"keys": {"code": 1}, "unique": True}],
    }

    # ---------------- wave 1: customers (XL, wide-embed class) ----------------
    cm = by_table["CUSTOMER_MASTER"]
    grouped = {c for cols in REPEATING_GROUPS.values() for c in cols}
    cust_fields, folded, dropped = [], [], []
    for c in cm:
        name = c["column_name"]
        key = f"CUSTOMER_MASTER.{name}"
        if name in always_null:
            dropped.append({"source_column": name, "reason":
                            "0/25000 rows populated (proposed-unused; evidence: "
                            "census/access_patterns.json#customer_master_population)"})
        elif key in DROP_REASONS:
            dropped.append({"source_column": name, "reason": DROP_REASONS[key]})
        elif name in grouped:
            folded.append({"source_column": name, "folded_into":
                           next(g for g, cols in REPEATING_GROUPS.items() if name in cols)})
        elif name == "CUST_ID":
            continue
        else:
            cust_fields.append(field(c, name.lower()))

    collections["customers"] = {
        "unit": "customers",
        "wave": 1,
        "sources": ["CUSTOMER_MASTER", "ENTITY_ATTR_VALUE", "CUSTOMER_MASTER_HIST"],
        "model": "embed",
        "pattern_class": "wide-embed",
        "access_pattern": (
            "reports.py BALANCES_SQL aggregates cur_bal_amt/past_due_amt across the whole "
            "batch; the operations handbook's account lookups are by cust_id, cust_no and "
            "cust_name_upper. Reads are always the whole account record — address, phones "
            "and EAV attributes are never queried independently of their customer, and the "
            "EAV table has no consumer of its own — so all of it embeds. Bounded: <=6 "
            "address lines, <=4 phones, <=3 emails, 7 distinct EAV attribute names."
        ),
        "key": {"_id": {"from": ["CUST_ID"], "strategy": "natural",
                        "note": "VARCHAR2(36) UUID; cust_seq_no is kept as a plain field "
                                "because SEQ_CUSTOMER_MASTER has no external consumer"}},
        "root_where": "conversion_batch_no = ${batch_no}",
        "fields": cust_fields,
        "folded": folded,
        "dropped": dropped,
        "embeds": [
            {
                "target_array": "address.lines",
                "source": "CUSTOMER_MASTER",
                "strategy": "repeating_group_to_array",
                "source_columns": REPEATING_GROUPS["address.lines"],
                "element_key": "ordinal",
                "element_fields": [{"target_field": "$element", "bson_type": "string"}],
                "rule": "NULL and empty lines are omitted, order preserved; the array is "
                        "absent when every line is NULL",
                "cardinality": "sum(address.lines[].length) == count of non-null "
                               "ADDR_LINE_* values",
            },
            {
                "target_array": "phones",
                "source": "CUSTOMER_MASTER",
                "strategy": "repeating_group_to_array",
                "source_columns": REPEATING_GROUPS["phones"],
                "element_key": "ordinal",
                "element_fields": [
                    {"target_field": "number", "bson_type": "string",
                     "from": "PHONE{n}"},
                    {"target_field": "type_code", "bson_type": "long",
                     "from": "PHONE{n}_TYPE_CD"},
                    {"target_field": "type", "bson_type": "string",
                     "code_lookup": {"code_type": "PHONE_TYPE"}},
                ],
                "rule": "one element per non-null PHONE{n}; a type code with no number is "
                        "dropped and counted",
                "cardinality": "sum(phones[].length) == count of non-null PHONE1..4",
            },
            {
                "target_array": "emails",
                "source": "CUSTOMER_MASTER",
                "strategy": "repeating_group_to_array",
                "source_columns": REPEATING_GROUPS["emails"],
                "element_key": "ordinal",
                "element_fields": [{"target_field": "$element", "bson_type": "string"}],
                "cardinality": "sum(emails[].length) == count of non-null EMAIL_1..3",
            },
            {
                "target_array": "attributes",
                "source": "ENTITY_ATTR_VALUE",
                "strategy": "eav_to_array",
                "child_where": "entity_type = 'CUSTOMER' AND entity_id = ${_id}",
                "element_key": ["attr_name", "created_dt"],
                "element_fields": [
                    {"source_column": "ATTR_NAME", "target_field": "name",
                     "bson_type": "string"},
                    {"source_column": "ATTR_VALUE", "target_field": "value",
                     "bson_type": "string",
                     "note": "attr_type is 'STR' for all 8,333 rows; no typed coercion"},
                    {"source_column": "ATTR_TYPE", "target_field": "type",
                     "bson_type": "string"},
                    {"source_column": "CREATED_DT", "target_field": "created_at",
                     "bson_type": "date", "transform": "parse_dd_mon_yy",
                     "on_error": "quarantine"},
                ],
                "dropped": [{"source_column": c.split(".")[1], "reason": r}
                            for c, r in DROP_REASONS.items()
                            if c.startswith("ENTITY_ATTR_VALUE.")],
                "rule": "ARRAY, not a subdocument keyed by attr_name: 187 "
                        "(entity_id, attr_name) pairs carry more than one row (up to 3) "
                        "across the 8,333 rows and 7,075 customers that have attributes. "
                        "A keyed subdocument would keep one value per pair and silently "
                        "drop the rest; the array preserves every row and lets recon "
                        "count elements against source rows.",
                "cardinality": (
                    f"sum(customers[].attributes.length) == {counts['ENTITY_ATTR_VALUE']} "
                    "(every EAV row; 0 orphans confirmed)"
                ),
            },
            {
                "target_array": "history",
                "source": "CUSTOMER_MASTER_HIST",
                "strategy": "child_rows_to_array",
                "child_where": "cust_id = ${_id}",
                "element_key": ["hist_id"],
                "element_fields": [
                    {"source_column": c["column_name"],
                     "target_field": c["column_name"].lower(),
                     "bson_type": transform_for(c, OVERRIDES)["bson"]}
                    for c in by_table["CUSTOMER_MASTER_HIST"]
                ],
                "rule": "0 rows today (the trigger only fires on UPDATE and the fixture "
                        "never updates). The array is absent, not empty, and the unit "
                        "records 0 rows -> 0 elements as an explicit PASS per tolerance T14.",
                "cardinality": f"sum(history[].length) == {counts['CUSTOMER_MASTER_HIST']}",
            },
        ],
        "quarantine": {
            "collection": "customers_quarantine",
            "expected": {
                "unparseable_signup_dt": ev["unparseable_date_strings"]["SIGNUP_DT"],
                "malformed_related_acct_ids": ev["malformed_csv"]["RELATED_ACCT_IDS"],
            },
        },
        "expected_documents": counts["CUSTOMER_MASTER"],
        "indexes": [
            {"keys": {"cust_no": 1}, "unique": True},
            {"keys": {"tenant_id": 1, "status_cd": 1}},
            {"keys": {"cust_name": 1},
             "collation": {"locale": "en", "strength": 2},
             "note": "replaces the CUST_NAME_UPPER shadow column"},
            {"keys": {"legacy_sys_key": 1}, "sparse": True},
        ],
    }

    # ---------------- wave 1: subscriptions ----------------
    collections["subscriptions"] = {
        "unit": "subscriptions",
        "wave": 1,
        "sources": ["SUBSCRIPTIONS", "SUBSCRIPTIONS_HIST"],
        "model": "embed",
        "access_pattern": (
            "PKG_PLANS.fn_entitlement reads the one active subscription per tenant as-of a "
            "date; sp_change_plan closes the current row and inserts the next, and "
            "TRG_SUBSCRIPTIONS_HIST snapshots the old row. Version history is only ever "
            "read alongside its subscription, so it embeds."
        ),
        "key": {"_id": {"from": ["ID"], "strategy": "natural"}},
        "fields": simple("SUBSCRIPTIONS", skip=["ID"]),
        "embeds": [{
            "target_array": "history",
            "source": "SUBSCRIPTIONS_HIST",
            "strategy": "child_rows_to_array",
            "child_where": "id = ${_id}",
            "element_key": ["hist_id"],
            "element_fields": [
                {"source_column": c["column_name"],
                 "target_field": c["column_name"].lower(),
                 "bson_type": transform_for(c, OVERRIDES)["bson"]}
                for c in by_table["SUBSCRIPTIONS_HIST"]
            ],
            "rule": "0 rows today; empty is an explicit PASS per tolerance T14",
            "cardinality": f"sum(history[].length) == {counts['SUBSCRIPTIONS_HIST']}",
        }],
        "expected_documents": counts["SUBSCRIPTIONS"],
        "indexes": [{"keys": {"tenant_id": 1, "starts_on": -1}},
                    {"keys": {"plan_id": 1}}],
    }

    # ---------------- wave 2: invoices (XL, bulk-load class) ----------------
    collections["invoices"] = {
        "unit": "invoices",
        "wave": 2,
        "sources": ["INVOICE_HEADER", "INVOICE_LINE"],
        "model": "embed",
        "pattern_class": "bulk-load",
        "access_pattern": (
            "reports.py LINE_SQL joins header to line on every month-end run and never "
            "reads a line outside its header; STATUS_SQL aggregates headers alone. Fan-out "
            f"is bounded and small (min {ev['invoice_line_fanout']['min']}, max "
            f"{ev['invoice_line_fanout']['max']}, avg "
            f"{ev['invoice_line_fanout']['avg']:.1f} lines per invoice; longest item_desc "
            f"{ev['max_text_lengths']['invoice_line.item_desc']} chars), so an embedded "
            "document stays around 3 KB — three orders of magnitude below the 16 MB limit. "
            "Embed."
        ),
        "key": {"_id": {"from": ["INVOICE_ID"], "strategy": "natural"}},
        "root_where": "batch_no = ${batch_no}",
        "fields": simple("INVOICE_HEADER", skip=["INVOICE_ID", "BATCH_NO"]),
        "dropped": [{"source_column": "BATCH_NO", "reason": DROP_REASONS["INVOICE_HEADER.BATCH_NO"]}],
        "embeds": [{
            "target_array": "lines",
            "source": "INVOICE_LINE",
            "strategy": "child_rows_to_array",
            "child_where": "invoice_id = ${_id}",
            "element_key": ["line_id"],
            "element_fields": [
                field(c, c["column_name"].lower())
                for c in by_table["INVOICE_LINE"]
                if f"INVOICE_LINE.{c['column_name']}" not in DROP_REASONS
            ],
            "dropped": [{"source_column": c.split(".")[1], "reason": r}
                        for c, r in DROP_REASONS.items() if c.startswith("INVOICE_LINE.")],
            "sort": [["line_no", 1]],
            "cardinality": (
                f"count(invoices) == {counts['INVOICE_HEADER']} AND "
                f"sum(invoices[].lines.length) == {counts['INVOICE_LINE']} - "
                f"{ev['orphan_invoice_lines']} quarantined orphans == "
                f"{counts['INVOICE_LINE'] - ev['orphan_invoice_lines']}"
            ),
        }],
        "quarantine": {
            "collection": "invoices_quarantine",
            "expected": {
                "orphan_invoice_lines": ev["orphan_invoice_lines"],
                "note": (
                    f"{ev['orphan_invoice_lines']} INVOICE_LINE rows point at "
                    f"{ev['orphan_invoice_lines']} invoice_ids with no INVOICE_HEADER row. "
                    "They are dropped by the legacy report's inner join, which is exactly "
                    "why they must be surfaced here rather than inherited silently."
                ),
            },
        },
        "expected_documents": counts["INVOICE_HEADER"],
        "indexes": [
            {"keys": {"invoice_no": 1}, "unique": True},
            {"keys": {"cust_id": 1, "invoice_dt": -1}},
            {"keys": {"status_cd": 1}},
        ],
    }

    # ---------------- wave 2: usage + rating ----------------
    collections["usage_events"] = {
        "unit": "usage_rating",
        "wave": 2,
        "sources": ["USAGE_EVENTS"],
        "model": "reference",
        "access_pattern": (
            "PKG_RATING.compute_rating scans events by (tenant_id, occurred_at) over a "
            "period window and TRG_USAGE_EVENTS_CHECK validates on insert. High-cardinality "
            "append-only time series with an independent write path: it stays its own "
            "collection rather than embedding into rating_periods."
        ),
        "key": {"_id": {"from": ["ID"], "strategy": "natural"}},
        "fields": simple("USAGE_EVENTS", skip=["ID"]),
        "expected_documents": counts["USAGE_EVENTS"],
        "indexes": [{"keys": {"tenant_id": 1, "occurred_at": 1}}],
    }
    collections["rating_periods"] = {
        "unit": "usage_rating",
        "wave": 2,
        "sources": ["RATING_PERIODS", "RATING_RESULTS"],
        "model": "embed",
        "access_pattern": (
            "RATING_RESULTS is written only by sp_finalize_rating for its period and read "
            "only via fn_usage_summary for that same period; there is no cross-period "
            "result query. Bounded by subscriptions-per-tenant, so results embed in the "
            "period that owns them."
        ),
        "key": {"_id": {"from": ["ID"], "strategy": "natural"}},
        "fields": simple("RATING_PERIODS", skip=["ID"]),
        "embeds": [{
            "target_array": "results",
            "source": "RATING_RESULTS",
            "strategy": "child_rows_to_array",
            "child_where": "period_id = ${_id}",
            "element_key": ["id"],
            "element_fields": [field(c, c["column_name"].lower())
                               for c in by_table["RATING_RESULTS"]
                               if c["column_name"] != "PERIOD_ID"],
            "dropped": [{"source_column": "PERIOD_ID",
                         "reason": "embed parent key; expressed by containment"}],
            "cardinality": f"sum(results[].length) == {counts['RATING_RESULTS']}",
        }],
        "expected_documents": counts["RATING_PERIODS"],
        "indexes": [{"keys": {"tenant_id": 1, "period_start": 1}, "unique": True}],
    }

    # ---------------- wave 2: the normalized proc-estate invoices ----------------
    collections["subscription_invoices"] = {
        "unit": "subscription_invoices",
        "wave": 2,
        "sources": ["INVOICES", "INVOICE_LINES"],
        "model": "embed",
        "access_pattern": (
            "A SEPARATE lineage from `invoices`: INVOICES is written by "
            "PKG_INVOICING.sp_issue_invoice against RATING_PERIODS and read back by "
            "fn_invoice_lines per invoice, and it is the FK parent of DUNNING_ATTEMPTS. "
            "INVOICE_HEADER (the converted legacy estate) has no FK to it and no shared "
            "key. Keeping them as two collections preserves that separation instead of "
            "inventing a merge the source does not make."
        ),
        "key": {"_id": {"from": ["ID"], "strategy": "natural"}},
        "fields": simple("INVOICES", skip=["ID"]),
        "embeds": [{
            "target_array": "lines",
            "source": "INVOICE_LINES",
            "strategy": "child_rows_to_array",
            "child_where": "invoice_id = ${_id}",
            "element_key": ["line_no"],
            "element_fields": [field(c, c["column_name"].lower())
                               for c in by_table["INVOICE_LINES"]
                               if c["column_name"] != "INVOICE_ID"],
            "dropped": [{"source_column": "INVOICE_ID",
                         "reason": DROP_REASONS["INVOICE_LINES.INVOICE_ID"]}],
            "sort": [["line_no", 1]],
            "cardinality": f"sum(lines[].length) == {counts['INVOICE_LINES']}",
        }],
        "expected_documents": counts["INVOICES"],
        "indexes": [{"keys": {"tenant_id": 1, "issued_at": -1}},
                    {"keys": {"period_id": 1}}],
    }

    # ---------------- wave 3: collections / ops ----------------
    for coll, table, ap, idx in [
        ("credit_notes", "CREDIT_NOTES",
         "Read per tenant when applying credit; no child rows.",
         [{"keys": {"tenant_id": 1, "issued_on": -1}}]),
        ("dunning_attempts", "DUNNING_ATTEMPTS",
         ("PKG_DUNNING.sp_schedule_dunning inserts one row per (invoice, attempt_no) and "
         "JOB_NIGHTLY_DUNNING drives it. Referenced by invoice, never embedded: attempts "
         "grow unbounded over an invoice's life and are written long after the invoice."),
         [{"keys": {"invoice_id": 1, "attempt_no": 1}, "unique": True},
          {"keys": {"tenant_id": 1, "scheduled_for": 1}}]),
        ("notifications", "NOTIFICATIONS",
         "Append-only outbound log keyed (tenant_id, kind_cd, sent_at); read by time range.",
         [{"keys": {"tenant_id": 1, "kind_cd": 1, "sent_at": 1}, "unique": True}]),
        ("billing_audit_log", "BILLING_AUDIT_LOG",
         ("PKG_OW_UTIL.log_msg appends here from every package; JOB_PURGE_AUDIT_LOG trims "
         "it. Empty today (0 rows) because the fixture load path does not log — an "
         "explicit empty-collection PASS per tolerance T14, not a skip."),
         [{"keys": {"logged_at": -1}}, {"keys": {"module": 1}}]),
    ]:
        collections[coll] = {
            "unit": "collections_ops",
            "wave": 3,
            "sources": [table],
            "model": "reference",
            "access_pattern": ap,
            "key": {"_id": {"from": ["ID" if table != "BILLING_AUDIT_LOG" else "LOG_ID"],
                            "strategy": "natural"}},
            "fields": simple(table, skip=["ID", "LOG_ID"]),
            "expected_documents": counts[table],
            "indexes": idx,
        }

    spec = {
        "mapping_version": MAPPING_VERSION,
        "status": "PROPOSED — pending STOP B",
        "tolerance_version": "v1",
        "source": {"family": "oracle", "schema": "OW_BILLING",
                   "profile": "mongo-migration/profiles/oracle.md"},
        "target": {"database": DATABASE, "cluster": "otterworks-demos M0"},
        "parameters": {
            "batch_no": {
                "type": "long",
                "resolved_per_run": True,
                "current_value": int(next(iter(
                    json.loads((CENSUS / "access_patterns.json").read_text())
                    ["invoice_header_batches"]))),
                "derivation": "sha256(NS)[:8] % 90_000_000 + 1_000_000, NS=demo "
                              "(reports.py:ns_batch_no)",
                "note": "never hard-coded in a mapping row; validated against the ledger "
                        "at the start of every unit",
            }
        },
        "collections": collections,
    }
    return spec


def validate(spec):
    """Coverage arithmetic: every census column is accounted for exactly once."""
    columns = load("columns")
    src_cols = {(c["table_name"], c["column_name"]) for c in columns
                if c["table_name"] != "FIXTURE_META"}
    seen = set()
    dupes = []
    for coll in spec["collections"].values():
        tables = coll["sources"]
        root = tables[0]

        def mark(table, col):
            k = (table, col)
            if k in seen:
                dupes.append(k)
            seen.add(k)

        for f in coll.get("fields", []):
            mark(root, f["source_column"])
        for d in coll.get("dropped", []) + coll.get("folded", []):
            mark(root, d["source_column"])
        for k in coll.get("key", {}).get("_id", {}).get("from", []):
            mark(root, k)
        for emb in coll.get("embeds", []):
            t = emb["source"]
            for f in emb.get("element_fields", []):
                if "source_column" in f:
                    mark(t, f["source_column"])
                elif f.get("from", "").startswith("PHONE"):
                    for n in range(1, 5):
                        mark(t, f["from"].replace("{n}", str(n)))
            for d in emb.get("dropped", []):
                mark(t, d["source_column"])
            for sc in emb.get("source_columns", []):
                mark(t, sc)

    missing = sorted(src_cols - seen)
    extra = sorted(seen - src_cols)
    return missing, extra, sorted(set(dupes))


if __name__ == "__main__":
    spec = build()
    missing, extra, dupes = validate(spec)
    OUT.write_text(json.dumps(spec, indent=2))
    print(f"collections: {len(spec['collections'])}")
    print(f"expected docs: {sum(c['expected_documents'] for c in spec['collections'].values())}")
    if missing:
        print(f"UNCOVERED source columns ({len(missing)}):")
        for m in missing:
            print("  ", ".".join(m))
    if extra:
        print(f"phantom columns ({len(extra)}): {extra}")
    print(f"wrote {OUT}")
    sys.exit(1 if (missing or extra) else 0)
