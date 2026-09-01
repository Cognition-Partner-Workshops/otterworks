"""Generate .migration/03_mapping_spec.json — the machine-readable mapping spec.

The JSON is written to the schema the recon harness loads (`recon.config`), because the
harness verdict is the merge gate: `collections` is a list, each with `root_table`, a
single-valued comparison `key`, `fields` of {source,target,source_type,bson_type,rules},
and `embeds` with `parent_key` + a single-column element `key`. Extra keys (unit, wave,
access_pattern, cardinality, dropped, derived_fields, ...) are carried for the humans and
ignored by the loader.

Two constraints from the harness shape it in ways worth naming, since both were modeling
changes:

1. Value grading inside an array needs a child TABLE and a single-column element key
   (`tiers._grade_embeds`). Repeating groups folded out of the root row — ADDR_LINE_1..3,
   PHONE1/2, EMAIL_1 — have neither, so as arrays they would ship UNGRADED. They become
   dotted subdocuments (`address.line_1`, `phones.primary.number`) which Tier 3 grades as
   ordinary fields. Only real child tables become arrays.
2. The harness compares the RAW source value against the target value under
   canonicalization rules, so a converted field (string date -> date, CSV -> array,
   Y/N -> bool) can never compare equal. Each such column is graded byte-exact at
   `legacy.<column>` and the converted value is an additional derived field, declared in
   `derived_fields` and verified by the unit's transform assertions plus the quarantine
   counts. That keeps the count of harness-unverified source columns at zero.

Run: python3 .migration/tools/build_mapping_spec.py
Exits non-zero if any source column is unaccounted for or accounted for twice.
"""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CENSUS = ROOT / "census"
OUT = ROOT / "03_mapping_spec.json"
UNIT_DIR = ROOT / "mapping"

MAPPING_VERSION = "m1"


def load(name):
    return json.loads((CENSUS / f"{name}.json").read_text())


COLUMNS = load("columns")
COUNTS = load("exact_counts")
CODE_TYPES = load("code_types")
POP = load("access_patterns")["customer_master_population"]

BY_TABLE = {}
for _c in COLUMNS:
    BY_TABLE.setdefault(_c["table_name"], []).append(_c)
COLTYPE = {(c["table_name"], c["column_name"]): c for c in COLUMNS}

ALWAYS_NULL = set(POP["always_null_columns"])
NON_NULL = POP["non_null_by_column"]
TOTAL_CUSTOMERS = POP["total_rows"]


# --------------------------------------------------------------------------- types
def oracle_type(col):
    t = col["data_type"]
    if t == "NUMBER" and col.get("data_precision"):
        return f"NUMBER({col['data_precision']},{col.get('data_scale') or 0})"
    if t in ("VARCHAR2", "CHAR"):
        return f"{t}({col['data_length']})"
    return t


def bson_and_rules(col, has_nulls):
    """Type mapping from the Oracle profile, plus the canonicalization rules that make the
    two sides comparable. Null-semantic rules are only attached where the column actually
    carries nulls: they defer a field's Tier 2 aggregates to the Tier 3 keyed diff, so
    attaching them everywhere would quietly hollow out Tier 2."""
    t = col["data_type"]
    rules = []
    if t == "NUMBER":
        scale = col.get("data_scale")
        if col.get("data_precision") and not scale:
            bson = "long"
        else:
            # Decimal128 arrives from pymongo as bson.Decimal128, which is not a Decimal;
            # decimal_round is what puts both sides on a common Decimal footing.
            bson, rules = "decimal128", ["decimal_round"]
    elif t == "DATE" or t.startswith("TIMESTAMP"):
        bson, rules = "date", ["datetime_utc_truncate_ms"]
    elif t == "CHAR":
        bson, rules = "string", ["rstrip_spaces"]
    else:
        bson = "string"
    if has_nulls:
        if bson == "string":
            rules = rules + ["empty_string_is_null"]
        rules = rules + ["null_missing_equiv"]
    return bson, rules


def has_nulls(table, column):
    if table == "CUSTOMER_MASTER":
        return NON_NULL.get(column, 0) < TOTAL_CUSTOMERS
    return COLTYPE[(table, column)]["nullable"] == "Y"


def fld(table, column, target, **extra):
    col = COLTYPE[(table, column)]
    bson, rules = bson_and_rules(col, has_nulls(table, column))
    return {"source": column, "target": target, "source_type": oracle_type(col),
            "bson_type": bson, "rules": rules, **extra}


def auto_fields(table, rename=None, skip=()):
    """Identity mapping: every column to its lowercased name unless renamed or skipped."""
    rename = rename or {}
    return [fld(table, c["column_name"], rename.get(c["column_name"], c["column_name"].lower()))
            for c in BY_TABLE[table] if c["column_name"] not in skip]


def legacy_pair(table, column, derived_target, transform, on_error="quarantine"):
    """A non-reversible conversion: grade the raw string, derive the typed value."""
    raw = fld(table, column, f"legacy.{column.lower()}",
              note=f"raw source value, graded byte-exact; {derived_target} is derived from it")
    derived = {"source": column, "target": derived_target, "transform": transform,
               "on_error": on_error,
               "verified_by": "unit transform assertions + quarantine counts "
                              "(the harness compares raw values, so it grades "
                              f"legacy.{column.lower()} instead)"}
    return raw, derived


def code_label(source_column, target, code_type):
    if code_type not in CODE_TYPES:
        sys.exit(f"unknown CODE_TYPE '{code_type}' for {source_column}; CODES defines "
                 f"{sorted(CODE_TYPES)}")
    return {"source": source_column, "target": target, "transform": "lookup_code_desc",
            "code_type": code_type,
            "note": "denormalized label beside the retained numeric code; additive, so the "
                    "numeric column is still graded on its own target field",
            "verified_by": "reference unit parity (CODES is loaded and graded in wave 0)"}


# --------------------------------------------------------------------------- drops
DROPPED = {}


def drop(table, columns, reason):
    for c in columns:
        DROPPED.setdefault(table, []).append({"source": c, "reason": reason})


UNUSED_REASON = (
    f"NULL in all {TOTAL_CUSTOMERS:,} rows (census/access_patterns.json"
    "#customer_master_population). Proposed-unused: dropped rather than carried as an "
    "always-absent field. If the production estate populates it, the spec needs that "
    "population census before load."
)

drop("CUSTOMER_MASTER", sorted(ALWAYS_NULL), UNUSED_REASON)
drop("CUSTOMER_MASTER", ["CUST_NAME_UPPER"],
     "shadow column maintained only so the legacy handbook could do a case-insensitive "
     "lookup; replaced by a collation index on `name` (locale en, strength 2)")
drop("CUSTOMER_MASTER", ["CUST_SEQ_NO"],
     "sequence-backed surrogate with no external consumer; `_id` is the natural key and "
     "SEQ_CUSTOMER_MASTER is retired")
drop("CUSTOMER_MASTER_HIST", sorted(ALWAYS_NULL | {"CUST_NAME_UPPER", "CUST_SEQ_NO"}),
     "snapshot mirrors CUSTOMER_MASTER column for column; dropped for the same reason as "
     "the parent column")
drop("ENTITY_ATTR_VALUE", ["ENTITY_TYPE"],
     "constant 'CUSTOMER' across all 8,333 rows; the embed's location in the customer "
     "document carries it")
drop("ENTITY_ATTR_VALUE", ["ENTITY_ID"],
     "join key to the parent row; becomes the containing document (declared as the "
     "embed's parent_key so recon still walks it)")
drop("INVOICE_LINE", ["INVOICE_ID"],
     "join key to the header; becomes containment (declared as the embed's parent_key)")
drop("INVOICE_LINE", ["INVOICE_NO", "CUST_ID", "CUST_NO", "CUST_NAME", "TENANT_ID"],
     "header values denormalized onto every line by the conversion; the embedding parent "
     "already carries them, and duplicating them per line reintroduces the update anomaly")
drop("INVOICE_LINE", ["BATCH_NO"],
     "conversion scoping, carried by the ${batch_no} run parameter and by the parent "
     "document's batch field, not per line")
drop("INVOICE_LINES", ["INVOICE_ID"], "join key to the header; becomes containment")
drop("RATING_RESULTS", ["PERIOD_ID"], "join key to the period; becomes containment")
drop("SUBSCRIPTIONS_HIST", ["ID"], "join key to the subscription; becomes containment")
drop("CUSTOMER_MASTER_HIST", ["CUST_ID"], "join key to the customer; becomes containment")
drop("FIXTURE_META", ["INITIALIZED_AT"],
     "table excluded from scope: estate bookkeeping, no business data")


# --------------------------------------------------------------------------- collections
def build():
    colls = []

    # ---- wave 0: reference ------------------------------------------------
    colls.append({
        "collection": "codes", "unit": "reference", "wave": 0,
        "root_table": "CODES",
        # CODES has no single-column key (32 rows over 10 types, 9 distinct values), and
        # the harness compares a single key value per document. An Oracle expression is
        # reported back under its own text as the column name, so it works as a key column.
        "key": {"source": ["CODE_TYPE||':'||CODE_VAL"], "target": "_id",
                "compose": {"from": ["CODE_TYPE", "CODE_VAL"], "sep": ":"}},
        "access_pattern": "joined twice per month-end report (reports.py STATUS_SQL, "
                          "LINE_SQL) and by PKG_OW_UTIL.f_code_desc in all five packages. "
                          "Kept as a collection AND denormalized as a label beside every "
                          "code value, so no hot read path needs a $lookup on 32 rows.",
        "fields": auto_fields("CODES"),
        "expected_documents": COUNTS["CODES"],
        "indexes": [{"keys": {"code_type": 1, "code_val": 1}, "unique": True}],
    })
    colls.append({
        "collection": "tenants", "unit": "reference", "wave": 0,
        "root_table": "TENANTS", "key": {"source": ["ID"], "target": "_id"},
        "access_pattern": "read by tenant id on every request path in both lineages; the "
                          "only table the converted estate and the application share "
                          "besides CODES.",
        "fields": [fld("TENANTS", "ID", "_id"), fld("TENANTS", "NAME", "name"),
                   fld("TENANTS", "STATUS_CD", "status_cd"),
                   fld("TENANTS", "TAX_EXEMPT_YN", "legacy.tax_exempt_yn")],
        "derived_fields": [
            {"source": "TAX_EXEMPT_YN", "target": "tax_exempt", "transform": "yn_to_bool",
             "verified_by": "unit transform assertions (harness grades the raw CHAR at "
                            "legacy.tax_exempt_yn)"},
            code_label("STATUS_CD", "status", "TENANT_STATUS"),
        ],
        "expected_documents": COUNTS["TENANTS"],
        "indexes": [{"keys": {"status_cd": 1}}],
    })
    colls.append({
        "collection": "plans", "unit": "reference", "wave": 0,
        "root_table": "PLANS", "key": {"source": ["ID"], "target": "_id"},
        "access_pattern": "PKG_PLANS.fn_list_plans returns the active plans on every "
                          "GET /api/plans; fn_entitlement reads one plan by id.",
        "fields": [fld("PLANS", "ID", "_id"), fld("PLANS", "CODE", "code"),
                   fld("PLANS", "TIER_CD", "tier_cd"),
                   fld("PLANS", "MONTHLY_FEE", "monthly_fee"),
                   fld("PLANS", "INCLUDED_UNITS", "included_units"),
                   fld("PLANS", "OVERAGE_RATE", "overage_rate"),
                   fld("PLANS", "ACTIVE_YN", "legacy.active_yn")],
        "derived_fields": [
            {"source": "ACTIVE_YN", "target": "active", "transform": "yn_to_bool",
             "verified_by": "unit transform assertions"},
            code_label("TIER_CD", "tier", "PLAN_TIER"),
        ],
        "expected_documents": COUNTS["PLANS"],
        "indexes": [{"keys": {"code": 1}, "unique": True}, {"keys": {"active": 1}}],
    })

    # ---- wave 1: customers (XL, wide-embed) -------------------------------
    cm_fields = [
        fld("CUSTOMER_MASTER", "CUST_ID", "_id"),
        fld("CUSTOMER_MASTER", "CUST_NO", "cust_no"),
        fld("CUSTOMER_MASTER", "LEGACY_SYS_KEY", "legacy_sys_key"),
        fld("CUSTOMER_MASTER", "MAINFRAME_ACCT_NO", "mainframe_acct_no"),
        fld("CUSTOMER_MASTER", "TENANT_ID", "tenant_id"),
        fld("CUSTOMER_MASTER", "CUST_NAME", "name"),
        fld("CUSTOMER_MASTER", "LEGAL_NAME", "legal_name"),
        fld("CUSTOMER_MASTER", "CUST_TYPE_CD", "type_cd"),
        fld("CUSTOMER_MASTER", "STATUS_CD", "status_cd"),
        fld("CUSTOMER_MASTER", "SUB_STATUS_CD", "sub_status_cd"),
        fld("CUSTOMER_MASTER", "REGION_CD", "region_cd"),
        fld("CUSTOMER_MASTER", "SEGMENT_CD", "segment_cd"),
        # repeating groups -> dotted subdocuments, not arrays: see the module docstring
        fld("CUSTOMER_MASTER", "ADDR_LINE_1", "address.line_1"),
        fld("CUSTOMER_MASTER", "ADDR_LINE_2", "address.line_2"),
        fld("CUSTOMER_MASTER", "ADDR_LINE_3", "address.line_3"),
        fld("CUSTOMER_MASTER", "CITY", "address.city"),
        fld("CUSTOMER_MASTER", "STATE_CD", "address.state_cd"),
        fld("CUSTOMER_MASTER", "ZIP", "address.zip"),
        fld("CUSTOMER_MASTER", "PHONE1", "phones.primary.number"),
        fld("CUSTOMER_MASTER", "PHONE1_TYPE_CD", "phones.primary.type_cd"),
        fld("CUSTOMER_MASTER", "PHONE2", "phones.secondary.number"),
        fld("CUSTOMER_MASTER", "PHONE2_TYPE_CD", "phones.secondary.type_cd"),
        fld("CUSTOMER_MASTER", "EMAIL_1", "email"),
        fld("CUSTOMER_MASTER", "CREDIT_LIMIT_AMT", "credit_limit_amt"),
        fld("CUSTOMER_MASTER", "CUR_BAL_AMT", "cur_bal_amt"),
        fld("CUSTOMER_MASTER", "PAST_DUE_AMT", "past_due_amt"),
        fld("CUSTOMER_MASTER", "YTD_BILLED_AMT", "ytd_billed_amt"),
        fld("CUSTOMER_MASTER", "ROW_VERSION_NO", "row_version_no"),
        fld("CUSTOMER_MASTER", "CONVERSION_BATCH_NO", "conversion_batch_no"),
        fld("CUSTOMER_MASTER", "CREATED_DT", "created_at"),
        fld("CUSTOMER_MASTER", "CREATED_BY", "created_by"),
        fld("CUSTOMER_MASTER", "UPDATED_DT", "updated_at"),
        fld("CUSTOMER_MASTER", "UPDATED_BY", "updated_by"),
    ]
    cm_derived = [code_label("STATUS_CD", "status", "CUST_STATUS"),
                  code_label("CUST_TYPE_CD", "type", "CUST_TYPE"),
                  code_label("PHONE1_TYPE_CD", "phones.primary.type", "PHONE_TYPE"),
                  code_label("PHONE2_TYPE_CD", "phones.secondary.type", "PHONE_TYPE")]
    for column, target, transform in [
        ("SIGNUP_DT", "signup_at", "parse_dd_mon_yy"),
        ("LAST_ACTIVITY_DT", "last_activity_at", "parse_dd_mon_yy"),
        ("PROMO_CODES_CSV", "promo_codes", "csv_to_array"),
        ("RELATED_ACCT_IDS", "related_acct_ids", "csv_to_array"),
        ("CREDIT_HOLD_YN", "credit_hold", "yn_to_bool"),
        ("TAX_EXEMPT_YN", "tax_exempt", "yn_to_bool"),
        ("VIP_YN", "vip", "yn_to_bool"),
    ]:
        raw, derived = legacy_pair("CUSTOMER_MASTER", column, target, transform,
                                   on_error="none" if transform == "yn_to_bool" else "quarantine")
        cm_fields.append(raw)
        cm_derived.append(derived)

    hist_skip = {d["source"] for d in DROPPED["CUSTOMER_MASTER_HIST"]}
    colls.append({
        "collection": "customers", "unit": "customers", "wave": 1,
        "pattern_class": "wide-embed", "size": "XL",
        "root_table": "CUSTOMER_MASTER",
        "root_where": "CONVERSION_BATCH_NO = ${batch_no}",
        "key": {"source": ["CUST_ID"], "target": "_id"},
        "access_pattern": (
            "reports.py BALANCES_SQL aggregates balances across the whole batch; the "
            "handbook's lookups are by cust_id, cust_no and cust_name_upper. Nothing reads "
            "a customer's attributes or version history without the customer, and "
            "ENTITY_ATTR_VALUE has no consumer of its own, so both embed."
        ),
        "fields": cm_fields,
        "derived_fields": cm_derived,
        "dropped": DROPPED["CUSTOMER_MASTER"],
        "embeds": [
            {
                "array_path": "attributes", "child_table": "ENTITY_ATTR_VALUE",
                "child_where": "ENTITY_TYPE = 'CUSTOMER'",
                "parent_key": ["ENTITY_ID"],
                "key": {"source": ["EAV_ID"], "target": "eav_id"},
                "fields": [fld("ENTITY_ATTR_VALUE", "ATTR_NAME", "name"),
                           fld("ENTITY_ATTR_VALUE", "ATTR_VALUE", "value"),
                           fld("ENTITY_ATTR_VALUE", "ATTR_TYPE", "type"),
                           fld("ENTITY_ATTR_VALUE", "CREATED_DT", "legacy.created_dt")],
                "derived_fields": [
                    {"source": "CREATED_DT", "target": "created_at",
                     "transform": "parse_dd_mon_yy", "on_error": "quarantine",
                     "verified_by": "unit transform assertions"}],
                "rule": (
                    "An ARRAY keyed by EAV_ID, not a subdocument keyed by attr_name: 187 "
                    "(entity_id, attr_name) pairs carry more than one row (up to 3) across "
                    "the 8,333 rows / 7,075 customers that have attributes, so a keyed "
                    "subdocument would keep one value per pair and silently drop the rest. "
                    "EAV_ID is also what makes the array value-gradable — the harness "
                    "grades elements by a single-column key."),
                "cardinality": f"sum(len(attributes)) == {COUNTS['ENTITY_ATTR_VALUE']} "
                               "(every EAV row; 0 orphans confirmed)",
                "dropped": DROPPED["ENTITY_ATTR_VALUE"],
            },
            {
                "array_path": "history", "child_table": "CUSTOMER_MASTER_HIST",
                "parent_key": ["CUST_ID"],
                "key": {"source": ["HIST_ID"], "target": "hist_id"},
                "fields": ([fld("CUSTOMER_MASTER_HIST", "HIST_OP", "hist_op"),
                            fld("CUSTOMER_MASTER_HIST", "HIST_DT", "legacy.hist_dt")]
                           + [fld("CUSTOMER_MASTER_HIST", c["column_name"],
                                  c["column_name"].lower())
                              for c in BY_TABLE["CUSTOMER_MASTER_HIST"]
                              if c["column_name"] not in hist_skip
                              | {"HIST_ID", "HIST_OP", "HIST_DT"}]),
                "rule": "0 rows today: TRG_CUSTOMER_MASTER_HIST fires on UPDATE only and "
                        "this estate has no updates against the converted batch. The array "
                        "is absent rather than empty, and the unit records 0 rows -> 0 "
                        "elements as an explicit PASS per tolerance T14.",
                "cardinality": f"sum(len(history)) == {COUNTS['CUSTOMER_MASTER_HIST']}",
                "dropped": DROPPED["CUSTOMER_MASTER_HIST"],
            },
        ],
        "quarantine": {
            "collection": "customers_quarantine",
            "expected": {"unparseable_signup_dt": 50, "malformed_related_acct_ids": 31},
        },
        "expected_documents": COUNTS["CUSTOMER_MASTER"],
        "indexes": [
            {"keys": {"cust_no": 1}, "unique": True},
            {"keys": {"tenant_id": 1, "status_cd": 1}},
            {"keys": {"name": 1}, "collation": {"locale": "en", "strength": 2},
             "note": "replaces the CUST_NAME_UPPER shadow column"},
            {"keys": {"legacy_sys_key": 1}},
        ],
    })

    # ---- wave 1: subscriptions --------------------------------------------
    colls.append({
        "collection": "subscriptions", "unit": "subscriptions", "wave": 1,
        "pattern_class": "small-embed",
        "root_table": "SUBSCRIPTIONS", "key": {"source": ["ID"], "target": "_id"},
        "access_pattern": "PKG_PLANS.fn_entitlement reads the one active subscription per "
                          "tenant as of a date; sp_change_plan closes the current row and "
                          "inserts the next, and TRG_SUBSCRIPTIONS_HIST snapshots the old "
                          "one. Version history is only ever read with its subscription.",
        "fields": auto_fields("SUBSCRIPTIONS", rename={"ID": "_id"}),
        "derived_fields": [code_label("STATUS_CD", "status", "SUB_STATUS")],
        "embeds": [{
            "array_path": "history", "child_table": "SUBSCRIPTIONS_HIST",
            "parent_key": ["ID"], "key": {"source": ["HIST_ID"], "target": "hist_id"},
            "fields": [fld("SUBSCRIPTIONS_HIST", "HIST_OP", "hist_op"),
                       fld("SUBSCRIPTIONS_HIST", "HIST_DT", "legacy.hist_dt"),
                       fld("SUBSCRIPTIONS_HIST", "TENANT_ID", "tenant_id"),
                       fld("SUBSCRIPTIONS_HIST", "PLAN_ID", "plan_id"),
                       fld("SUBSCRIPTIONS_HIST", "STARTS_ON", "starts_on"),
                       fld("SUBSCRIPTIONS_HIST", "ENDS_ON", "ends_on"),
                       fld("SUBSCRIPTIONS_HIST", "STATUS_CD", "status_cd"),
                       fld("SUBSCRIPTIONS_HIST", "SUSPENDED_ON", "suspended_on")],
            "rule": "0 rows today; explicit empty PASS per tolerance T14",
            "cardinality": f"sum(len(history)) == {COUNTS['SUBSCRIPTIONS_HIST']}",
            "dropped": DROPPED["SUBSCRIPTIONS_HIST"],
        }],
        "expected_documents": COUNTS["SUBSCRIPTIONS"],
        "indexes": [{"keys": {"tenant_id": 1, "starts_on": -1}}, {"keys": {"plan_id": 1}}],
    })

    # ---- wave 2: invoices (XL, bulk-load) ---------------------------------
    colls.append({
        "collection": "invoices", "unit": "invoices", "wave": 2,
        "pattern_class": "bulk-load", "size": "XL",
        "root_table": "INVOICE_HEADER",
        "root_where": "BATCH_NO = ${batch_no}",
        "key": {"source": ["INVOICE_ID"], "target": "_id"},
        "access_pattern": (
            "reports.py LINE_SQL joins header to line on every month-end run and no query "
            "reads a line without its header, so lines embed. Fan-out is min 1 / max 23 / "
            "avg 8.0 with a 29-character longest item_desc: an embedded invoice is ~3 KB, "
            "three orders of magnitude under the 16 MB document limit."
        ),
        "fields": [fld("INVOICE_HEADER", "INVOICE_ID", "_id"),
                   fld("INVOICE_HEADER", "INVOICE_NO", "invoice_no"),
                   fld("INVOICE_HEADER", "CUST_ID", "cust_id"),
                   fld("INVOICE_HEADER", "TENANT_ID", "tenant_id"),
                   fld("INVOICE_HEADER", "STATUS_CD", "status_cd"),
                   fld("INVOICE_HEADER", "TOTAL_AMT", "total_amt"),
                   fld("INVOICE_HEADER", "BATCH_NO", "batch_no"),
                   fld("INVOICE_HEADER", "INVOICE_DT", "legacy.invoice_dt"),
                   fld("INVOICE_HEADER", "DUE_DT", "legacy.due_dt")],
        "derived_fields": [
            code_label("STATUS_CD", "status", "INV_STATUS"),
            {"source": "INVOICE_DT", "target": "invoice_at", "transform": "parse_dd_mon_yy",
             "on_error": "quarantine", "verified_by": "unit transform assertions"},
            {"source": "DUE_DT", "target": "due_at", "transform": "parse_dd_mon_yy",
             "on_error": "quarantine", "verified_by": "unit transform assertions"},
        ],
        "embeds": [{
            "array_path": "lines", "child_table": "INVOICE_LINE",
            # Orphans are quarantined, not embedded, so they must be excluded here or Tier 1
            # would compare 150,000 child rows against 149,963 elements and fail by design.
            "child_where": "BATCH_NO = ${batch_no} AND INVOICE_ID IN "
                           "(SELECT INVOICE_ID FROM INVOICE_HEADER)",
            "parent_key": ["INVOICE_ID"],
            "key": {"source": ["LINE_ID"], "target": "line_id"},
            "fields": [fld("INVOICE_LINE", "LINE_NO", "line_no"),
                       fld("INVOICE_LINE", "LINE_TYPE_CD", "line_type_cd"),
                       fld("INVOICE_LINE", "ITEM_DESC", "item_desc"),
                       fld("INVOICE_LINE", "QTY", "qty"),
                       fld("INVOICE_LINE", "UNIT_PRICE", "unit_price"),
                       fld("INVOICE_LINE", "AMOUNT", "amount"),
                       fld("INVOICE_LINE", "TAX_AMT", "tax_amt"),
                       fld("INVOICE_LINE", "SERVICE_PERIOD", "service_period"),
                       fld("INVOICE_LINE", "SRC_SYSTEM", "src_system"),
                       fld("INVOICE_LINE", "INVOICE_DT", "legacy.invoice_dt"),
                       fld("INVOICE_LINE", "POSTED_YN", "legacy.posted_yn"),
                       fld("INVOICE_LINE", "GL_ACCT_CSV", "legacy.gl_acct_csv")],
            "derived_fields": [
                {"source": "POSTED_YN", "target": "posted", "transform": "yn_to_bool",
                 "verified_by": "unit transform assertions"},
                {"source": "GL_ACCT_CSV", "target": "gl_accounts", "transform": "csv_to_array",
                 "on_error": "quarantine", "verified_by": "unit transform assertions"},
            ],
            "cardinality": f"sum(len(lines)) == {COUNTS['INVOICE_LINE']} - 37 == "
                           f"{COUNTS['INVOICE_LINE'] - 37} (37 orphans quarantined)",
            "dropped": DROPPED["INVOICE_LINE"],
        }],
        "quarantine": {"collection": "invoices_quarantine",
                       "expected": {"orphan_invoice_lines": 37}},
        "expected_documents": COUNTS["INVOICE_HEADER"],
        "indexes": [{"keys": {"invoice_no": 1}, "unique": True},
                    {"keys": {"cust_id": 1, "invoice_at": -1}},
                    {"keys": {"batch_no": 1, "status_cd": 1}}],
    })

    # ---- wave 2: usage + rating -------------------------------------------
    colls.append({
        "collection": "usage_events", "unit": "usage_rating", "wave": 2,
        "pattern_class": "small-embed",
        "root_table": "USAGE_EVENTS", "key": {"source": ["ID"], "target": "_id"},
        "access_pattern": "PKG_RATING.compute_rating scans by (tenant_id, occurred_at) for "
                          "a period; the table is append-only with its own write path, so "
                          "it stays referenced rather than embedding into rating periods.",
        "fields": auto_fields("USAGE_EVENTS", rename={"ID": "_id"}),
        "derived_fields": [code_label("KIND_CD", "kind", "USAGE_KIND")],
        "expected_documents": COUNTS["USAGE_EVENTS"],
        "indexes": [{"keys": {"tenant_id": 1, "occurred_at": 1}}],
        "validator": "$jsonSchema replacing TRG_USAGE_EVENTS_CHECK (units > 0)",
    })
    colls.append({
        "collection": "rating_periods", "unit": "usage_rating", "wave": 2,
        "pattern_class": "small-embed",
        "root_table": "RATING_PERIODS", "key": {"source": ["ID"], "target": "_id"},
        "access_pattern": "RATING_RESULTS is written only by sp_finalize_rating for its "
                          "period and read only by fn_usage_summary for that period, so "
                          "results embed.",
        "fields": auto_fields("RATING_PERIODS", rename={"ID": "_id"}),
        "embeds": [{
            "array_path": "results", "child_table": "RATING_RESULTS",
            "parent_key": ["PERIOD_ID"], "key": {"source": ["ID"], "target": "result_id"},
            "fields": [fld("RATING_RESULTS", "SUBSCRIPTION_ID", "subscription_id"),
                       fld("RATING_RESULTS", "USED_UNITS", "used_units"),
                       fld("RATING_RESULTS", "QUOTA_UNITS", "quota_units"),
                       fld("RATING_RESULTS", "ROLLOVER_UNITS", "rollover_units"),
                       fld("RATING_RESULTS", "BILLABLE_UNITS", "billable_units"),
                       fld("RATING_RESULTS", "OVERAGE_AMOUNT", "overage_amount"),
                       fld("RATING_RESULTS", "CREATED_AT", "created_at")],
            "cardinality": f"sum(len(results)) == {COUNTS['RATING_RESULTS']}",
            "dropped": DROPPED["RATING_RESULTS"],
        }],
        "expected_documents": COUNTS["RATING_PERIODS"],
        "indexes": [{"keys": {"tenant_id": 1, "period_start": -1}}],
    })

    # ---- wave 2: the application's own invoices ---------------------------
    colls.append({
        "collection": "subscription_invoices", "unit": "subscription_invoices", "wave": 2,
        "pattern_class": "small-embed",
        "root_table": "INVOICES", "key": {"source": ["ID"], "target": "_id"},
        "access_pattern": (
            "PKG_INVOICING.sp_issue_invoice writes a header and its lines in one "
            "transaction; fn_invoice_lines only ever reads them together. Separate from "
            "`invoices` because INVOICES and INVOICE_HEADER share no key: they are the "
            "application's own invoices and the converted legacy estate's, respectively."
        ),
        "fields": auto_fields("INVOICES", rename={"ID": "_id"}),
        "derived_fields": [code_label("STATUS_CD", "status", "INV_STATUS")],
        "embeds": [{
            "array_path": "lines", "child_table": "INVOICE_LINES",
            "parent_key": ["INVOICE_ID"], "key": {"source": ["ID"], "target": "line_id"},
            "fields": [fld("INVOICE_LINES", "LINE_NO", "line_no"),
                       fld("INVOICE_LINES", "LINE_TYPE", "line_type"),
                       fld("INVOICE_LINES", "DESCRIPTION", "description"),
                       fld("INVOICE_LINES", "AMOUNT", "amount")],
            "cardinality": f"sum(len(lines)) == {COUNTS['INVOICE_LINES']}",
            "dropped": DROPPED["INVOICE_LINES"],
        }],
        "expected_documents": COUNTS["INVOICES"],
        "indexes": [{"keys": {"tenant_id": 1, "issued_at": -1}}, {"keys": {"period_id": 1}}],
    })

    # ---- wave 3: collections ops ------------------------------------------
    for name, table, access, indexes in [
        ("credit_notes", "CREDIT_NOTES",
         "read by tenant when applying credit at invoice issue; no child rows",
         [{"keys": {"tenant_id": 1, "issued_on": -1}}]),
        ("dunning_attempts", "DUNNING_ATTEMPTS",
         ("grows unbounded over an invoice's life and is written by the nightly dunning job "
          "long after issue, so it is referenced rather than embedded into the invoice"),
         [{"keys": {"invoice_id": 1, "attempt_no": 1}}, {"keys": {"scheduled_for": 1}}]),
        ("notifications", "NOTIFICATIONS",
         "append-only outbound log, read by tenant and time window",
         [{"keys": {"tenant_id": 1, "sent_at": -1}}]),
        ("billing_audit_log", "BILLING_AUDIT_LOG",
         ("written by PKG_OW_UTIL.log_msg, purged by JOB_PURGE_AUDIT_LOG; the job is "
          "replaced by a TTL index on logged_at"),
         [{"keys": {"logged_at": 1}, "expireAfterSeconds": 7776000,
           "note": "TTL index replacing JOB_PURGE_AUDIT_LOG (90 days)"}]),
    ]:
        keycol = "LOG_ID" if table == "BILLING_AUDIT_LOG" else "ID"
        colls.append({
            "collection": name, "unit": "collections_ops", "wave": 3,
            "pattern_class": "reference",
            "root_table": table, "key": {"source": [keycol], "target": "_id"},
            "access_pattern": access,
            "fields": auto_fields(table, rename={keycol: "_id"}),
            "expected_documents": COUNTS[table],
            "indexes": indexes,
        })
    for c in colls:
        if c["collection"] == "dunning_attempts":
            c["derived_fields"] = [code_label("STATUS_CD", "status", "DUN_STATUS")]
        if c["collection"] == "notifications":
            c["derived_fields"] = [code_label("KIND_CD", "kind", "NOTIF_KIND")]

    return {
        "version": MAPPING_VERSION,
        "tolerance_version": "v1",
        "source": {"family": "oracle", "schema": "OW_BILLING"},
        "target": {"database": "ow_tp_mongodb_orc1"},
        "parameters": {
            "batch_no": {
                "description": "conversion batch scope. reports.py:ns_batch_no derives it "
                               "from the namespace as sha256(ns)[:8] %% 90e6 + 1e6, so it "
                               "is a run parameter and never a literal in a mapping row.",
                "resolved_by": "recon --param batch_no=<value> / the loader's --batch flag",
            },
        },
        "excluded_tables": [{"table": "FIXTURE_META",
                             "reason": DROPPED["FIXTURE_META"][0]["reason"]}],
        "collections": colls,
    }


# --------------------------------------------------------------------------- validation
def validate(spec):
    """Every source column is accounted for exactly once, and the spec loads under the
    harness's own config loader. Coverage is the whole point of the census, so a gap is a
    build failure rather than a warning."""
    seen = {}
    problems = []

    def account(table, column, how, where):
        key = (table, column)
        if key in seen:
            problems.append(f"DOUBLE-COUNTED {table}.{column}: {seen[key]} and {how} in {where}")
        seen[key] = f"{how} in {where}"

    for c in spec["collections"]:
        root = c["root_table"]
        for f in c["fields"]:
            account(root, f["source"], "mapped", c["collection"])
        for d in c.get("dropped", []):
            account(root, d["source"], "dropped", c["collection"])
        for e in c.get("embeds", []):
            child = e["child_table"]
            for k in e["key"]["source"]:
                account(child, k, "element key", f"{c['collection']}.{e['array_path']}")
            for f in e["fields"]:
                account(child, f["source"], "mapped", f"{c['collection']}.{e['array_path']}")
            for d in e.get("dropped", []):
                account(child, d["source"], "dropped", f"{c['collection']}.{e['array_path']}")
            if len(e["key"]["source"]) != 1 or not e.get("parent_key") or not e.get("fields"):
                problems.append(
                    f"UNGRADABLE EMBED {c['collection']}.{e['array_path']}: the harness "
                    "value-grades an array only with a parent_key, exactly one element key "
                    "column, and declared fields")
    for t in spec["excluded_tables"]:
        for d in DROPPED[t["table"]]:
            account(t["table"], d["source"], "excluded", t["table"])

    uncovered = sorted(f"{c['table_name']}.{c['column_name']}" for c in COLUMNS
                       if (c["table_name"], c["column_name"]) not in seen)
    if uncovered:
        problems.append(f"UNCOVERED source columns ({len(uncovered)}):\n   "
                        + "\n   ".join(uncovered))

    tables = {c["root_table"] for c in spec["collections"]}
    tables |= {e["child_table"] for c in spec["collections"] for e in c.get("embeds", [])}
    tables |= {t["table"] for t in spec["excluded_tables"]}
    missing_tables = sorted(set(COUNTS) - tables)
    if missing_tables:
        problems.append(f"UNBUCKETED tables: {missing_tables}")
    return problems, len(seen)


def write_unit_specs(spec):
    """Per-unit slices of the same spec. `recon run --unit X` grades every collection in the
    mapping file it is handed, so a unit's gate has to be run against that unit's slice --
    otherwise wave 0 fails on collections wave 2 has not loaded yet. Slicing here rather
    than hand-maintaining a file per unit is what keeps the gate and the loader honest
    about grading the same mapping."""
    UNIT_DIR.mkdir(exist_ok=True)
    units = {}
    for c in spec["collections"]:
        units.setdefault(c["unit"], []).append(c)
    for unit, colls in units.items():
        (UNIT_DIR / f"{unit}.json").write_text(json.dumps(
            {**spec, "unit": unit,
             "_sliced_from": "03_mapping_spec.json (generated; do not hand-edit)",
             "collections": colls}, indent=2))
    return units


def main():
    spec = build()
    problems, n_cols = validate(spec)
    OUT.write_text(json.dumps(spec, indent=2))
    units = write_unit_specs(spec)
    print(f"collections: {len(spec['collections'])}  "
          f"root documents: {sum(c['expected_documents'] for c in spec['collections']):,}  "
          f"source columns accounted for: {n_cols}/{len(COLUMNS)}")
    if problems:
        print("\n".join(problems), file=sys.stderr)
        sys.exit(1)
    print(f"wrote {OUT} and {len(units)} unit slices in {UNIT_DIR}/ "
          f"({', '.join(sorted(units))})")


if __name__ == "__main__":
    main()
