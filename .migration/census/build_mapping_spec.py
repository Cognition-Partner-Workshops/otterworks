"""Build the machine-readable mapping spec twin (.migration/03_mapping_spec.json) from the
Oracle census plus the explicitly declared Postgres / DynamoDB collections.

Read-only: consumes .migration/census/oracle_census.json, writes JSON. Type mapping follows
the Oracle profile: NUMBER(p,0) p<=9 -> int, p<=18 -> long, else/scale>0 -> decimal (Decimal128,
half-even); DATE/TIMESTAMP -> date (UTC, ms); CHAR -> string (rstrip); VARCHAR2 -> string.
Target field names are the lower-cased source column names so every mapping row is auditable
by eye; derived convenience fields (parsed dates, CSV arrays) are declared separately as
UNGRADED derivations and are NOT compared by the recon harness.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CENSUS = ROOT / ".migration" / "census" / "oracle_census.json"
OUT = ROOT / ".migration" / "03_mapping_spec.json"

VERSION = "v1.0.1"
NS = "mongo_205236"


def bson_type(col: dict) -> tuple[str, list[str]]:
    dt = col["data_type"]
    if dt == "NUMBER":
        p, s = col["data_precision"], col["data_scale"]
        if s not in (None, 0) or p is None:
            return "decimal", ["decimal_round"]
        if p <= 9:
            return "int", []
        if p <= 18:
            return "long", []
        return "decimal", ["decimal_round"]
    if dt == "DATE" or dt.startswith("TIMESTAMP"):
        return "date", ["datetime_utc_truncate_ms"]
    if dt == "CHAR":
        return "string", ["rstrip_spaces", "empty_string_is_null"]
    if dt in ("VARCHAR2", "NVARCHAR2", "CLOB"):
        return "string", ["empty_string_is_null"]
    raise ValueError(f"unmapped Oracle type {dt} on {col['table_name']}.{col['column_name']}")


def fields_for(census: dict, table: str, exclude: set[str] = frozenset()) -> list[dict]:
    out = []
    for c in census["columns"]:
        if c["table_name"] != table or c["column_name"] in exclude:
            continue
        bt, rules = bson_type(c)
        src_type = c["data_type"]
        if src_type == "NUMBER" and c["data_precision"] is not None:
            src_type = f"NUMBER({c['data_precision']},{c['data_scale'] or 0})"
        out.append({"source": c["column_name"], "target": c["column_name"].lower(),
                    "source_type": src_type, "bson_type": bt, "rules": rules})
    if not out:
        raise ValueError(f"no columns for {table}")
    return out


def oracle_collection(census, collection, table, key_cols, *, root_where=None, embeds=(),
                      unit, wave, derived=(), indexes=(), notes="", key_target=None):
    return {
        "collection": collection, "root_table": table, "family": "oracle",
        "unit": unit, "wave": wave,
        "key": {"source": key_cols, "target": key_target or ("_id" if len(key_cols) == 1 else "_key")},
        "root_where": root_where,
        "fields": fields_for(census, table),
        "embeds": list(embeds),
        "derived_ungraded": list(derived),
        "indexes": list(indexes),
        "namespace_field": {"target": "ns", "value": NS},
        "notes": notes,
    }


def embed(census, array_path, child_table, parent_key, key_source, key_target,
          child_where=None, exclude=frozenset()):
    return {"array_path": array_path, "child_table": child_table, "child_where": child_where,
            "parent_key": parent_key, "key": {"source": key_source, "target": key_target},
            "fields": fields_for(census, child_table, exclude)}


def main() -> None:
    census = json.loads(CENSUS.read_text())
    cols = []

    # ---- wave 0: reference data (unit U0) -------------------------------------------
    # composite key graded as ONE source expression vs the loader-composed scalar `_key`
    # (Oracle reports the unaliased expression name with spaces stripped — keep it space-free)
    cols.append(oracle_collection(census, "codes", "CODES", ["CODE_TYPE||':'||CODE_VAL"], key_target="_key",
                                  unit="U0", wave=0,
                                  indexes=[{"keys": {"code_type": 1, "code_val": 1}, "unique": True}],
                                  notes="Lookup used by PKG_OW_UTL.F_CODE_DESC and RPT-114; _key = 'CODE_TYPE:CODE_VAL'."))
    cols.append(oracle_collection(census, "tenants", "TENANTS", ["ID"], unit="U0", wave=0))
    cols.append(oracle_collection(census, "plans", "PLANS", ["ID"], unit="U0", wave=0,
                                  derived=[{"target": "tier", "from": "TIER_CD",
                                            "rule": "DECODE(1 starter,2 growth,3 scale, else UNKNOWN) — computed at read time by fn_list_plans, not stored"}]))

    # ---- wave 1: bulk data estate ----------------------------------------------------
    cols.append(oracle_collection(
        census, "customers", "CUSTOMER_MASTER", ["CUST_ID"], unit="U1", wave=1,
        root_where="conversion_batch_no = ${batch_no}",
        embeds=[embed(census, "attributes", "ENTITY_ATTR_VALUE", ["ENTITY_ID"], ["EAV_ID"], "eav_id",
                      child_where="entity_type = 'CUSTOMER'")],
        derived=[
            {"target": "signup_date", "from": "SIGNUP_DT", "rule": "parse DD-MON-YY -> date; unparseable -> quarantine class dirty_signup_dt (row still migrates with signup_dt verbatim)"},
            {"target": "last_activity_date", "from": "LAST_ACTIVITY_DT", "rule": "parse DD-MON-YY -> date or null"},
            {"target": "related_accounts", "from": "RELATED_ACCT_IDS", "rule": "split ','; strip; drop empties; malformed -> quarantine class bad_csv_list (verbatim column kept)"},
            {"target": "child_accounts", "from": "CHILD_ACCT_IDS", "rule": "split ',' as above"},
            {"target": "promo_codes", "from": "PROMO_CODES_CSV", "rule": "split ',' as above"},
            {"target": "addresses", "from": "ADDR_LINE_1..6/CITY/STATE_CD/ZIP/ZIP4/COUNTRY_CD + MAIL_*", "rule": "two subdocuments {billing, mailing}; source columns retained verbatim for grading"},
            {"target": "phones", "from": "PHONE1..4 + PHONE*_TYPE_CD", "rule": "array of {number,type_cd}; source columns retained verbatim"},
        ],
        indexes=[{"keys": {"tenant_id": 1, "cust_no": 1}}, {"keys": {"cust_name_upper": 1}},
                 {"keys": {"conversion_batch_no": 1}}],
        notes="155 columns carried 1:1 (explicit BSON null for NULL/empty per tolerance v1). EAV rows fold into attributes[] keyed by eav_id. TRG_CUSTOMER_MASTER_SEQ/HIST semantics move to the application write path (cust_seq_no from counters collection, cust_name_upper computed, history document appended to customers_history)."))
    cols.append(oracle_collection(census, "customers_history", "CUSTOMER_MASTER_HIST", ["HIST_ID"], unit="U1", wave=1,
                                  notes="0 rows at census; collection created + registered so the rewritten write path has a target. Row-copy history preserved as-is."))
    cols.append(oracle_collection(
        census, "invoices", "INVOICE_HEADER", ["INVOICE_ID"], unit="U2", wave=1,
        root_where="batch_no = ${batch_no}",
        embeds=[embed(census, "lines", "INVOICE_LINE", ["INVOICE_ID"], ["LINE_ID"], "line_id",
                      child_where="batch_no = ${batch_no} AND invoice_id IN (SELECT invoice_id FROM invoice_header WHERE batch_no = ${batch_no})")],
        derived=[
            {"target": "invoice_date", "from": "INVOICE_DT", "rule": "parse DD-MON-YY -> date or null"},
            {"target": "due_date", "from": "DUE_DT", "rule": "parse DD-MON-YY -> date or null"},
            {"target": "lines[].gl_accounts", "from": "GL_ACCT_CSV", "rule": "split ','"},
            {"target": "status_desc", "from": "STATUS_CD via codes(INV_STATUS)", "rule": "$lookup at read time in RPT-114 aggregation; not stored"},
        ],
        indexes=[{"keys": {"batch_no": 1, "status_cd": 1}}, {"keys": {"cust_id": 1}}, {"keys": {"lines.line_id": 1}}],
        notes="Bounded embed (~8 lines/invoice, max observed 25). INVOICE_LINE rows whose invoice_id has no INVOICE_HEADER row -> quarantine.invoice_feed_orphan_lines (37 expected)."))

    # ---- Postgres (unit U3) and DynamoDB (unit U4): declared explicitly ---------------
    cols.append({
        "collection": "documents", "root_table": "otterworks_demo.documents", "family": "postgres",
        "unit": "U3", "wave": 1, "key": {"source": ["id"], "target": "_id"}, "root_where": None,
        "fields": [
            {"source": "id", "target": "_id", "source_type": "uuid", "bson_type": "string", "rules": ["uuid_normalize"]},
            {"source": "title", "target": "title", "source_type": "varchar", "bson_type": "string", "rules": []},
            {"source": "content", "target": "content", "source_type": "text", "bson_type": "string", "rules": []},
            {"source": "content_type", "target": "content_type", "source_type": "varchar", "bson_type": "string", "rules": []},
            {"source": "owner_id", "target": "owner_id", "source_type": "uuid", "bson_type": "string", "rules": ["uuid_normalize"]},
            {"source": "folder_id", "target": "folder_id", "source_type": "uuid", "bson_type": "string", "rules": ["uuid_normalize", "null_missing_equiv"]},
            {"source": "is_deleted", "target": "is_deleted", "source_type": "boolean", "bson_type": "bool", "rules": []},
            {"source": "is_template", "target": "is_template", "source_type": "boolean", "bson_type": "bool", "rules": []},
            {"source": "word_count", "target": "word_count", "source_type": "integer", "bson_type": "int", "rules": []},
            {"source": "version", "target": "version", "source_type": "integer", "bson_type": "int", "rules": []},
            {"source": "created_at", "target": "created_at", "source_type": "timestamptz", "bson_type": "date", "rules": ["datetime_utc_truncate_ms"]},
            {"source": "updated_at", "target": "updated_at", "source_type": "timestamptz", "bson_type": "date", "rules": ["datetime_utc_truncate_ms"]},
        ],
        "embeds": [{
            "array_path": "versions", "child_table": "otterworks_demo.document_versions", "child_where": None,
            "parent_key": ["document_id"], "key": {"source": ["id"], "target": "id"},
            "fields": [
                {"source": "id", "target": "id", "source_type": "uuid", "bson_type": "string", "rules": ["uuid_normalize"]},
                {"source": "version_number", "target": "version_number", "source_type": "integer", "bson_type": "int", "rules": []},
                {"source": "title", "target": "title", "source_type": "varchar", "bson_type": "string", "rules": []},
                {"source": "content", "target": "content", "source_type": "text", "bson_type": "string", "rules": []},
                {"source": "created_by", "target": "created_by", "source_type": "uuid", "bson_type": "string", "rules": ["uuid_normalize"]},
                {"source": "created_at", "target": "created_at", "source_type": "timestamptz", "bson_type": "date", "rules": ["datetime_utc_truncate_ms"]},
            ],
        }],
        "derived_ungraded": [{"target": "version_gaps", "from": "versions[].version_number", "rule": "list of missing version numbers between 1..max; reported (10 expected), never repaired"}],
        "indexes": [{"keys": {"owner_id": 1}}, {"keys": {"folder_id": 1}}, {"keys": {"versions.id": 1}}],
        "namespace_field": {"target": "ns", "value": NS},
        "notes": "Versions embedded (avg 7, max 12 per document — bounded). Snapshots are a separate referenced collection (state_b64 payloads can be large).",
    })
    cols.append({
        "collection": "document_snapshots", "root_table": "otterworks_demo.document_snapshots", "family": "postgres",
        "unit": "U3", "wave": 1, "key": {"source": ["id"], "target": "_id"},
        "root_where": "document_id IN (SELECT id FROM otterworks_demo.documents)",
        "fields": [
            {"source": "id", "target": "_id", "source_type": "uuid", "bson_type": "string", "rules": ["uuid_normalize"]},
            {"source": "document_id", "target": "document_id", "source_type": "uuid", "bson_type": "string", "rules": ["uuid_normalize"]},
            {"source": "state_b64", "target": "state_b64", "source_type": "text", "bson_type": "string", "rules": []},
            {"source": "label", "target": "label", "source_type": "varchar", "bson_type": "string", "rules": ["null_missing_equiv"]},
            {"source": "created_by", "target": "created_by", "source_type": "uuid", "bson_type": "string", "rules": ["uuid_normalize"]},
            {"source": "created_at", "target": "created_at", "source_type": "timestamptz", "bson_type": "date", "rules": ["datetime_utc_truncate_ms"]},
        ],
        "embeds": [], "derived_ungraded": [],
        "indexes": [{"keys": {"document_id": 1, "created_at": -1}}],
        "namespace_field": {"target": "ns", "value": NS},
        "notes": "state_b64 carried byte-transparent as the original base64 string (no decode). Snapshots whose document_id has no documents row -> quarantine.orphan_document_snapshots (6 expected).",
    })
    cols.append({
        "collection": "files", "root_table": "otterworks-file-metadata", "family": "dynamodb",
        "unit": "U4", "wave": 1, "key": {"source": ["id"], "target": "_id"},
        "root_where": "ns = '${source_ns}'",
        "fields": [
            {"source": "id", "target": "_id", "source_type": "S", "bson_type": "string", "rules": []},
            {"source": "name", "target": "name", "source_type": "S", "bson_type": "string", "rules": []},
            {"source": "mime_type", "target": "mime_type", "source_type": "S", "bson_type": "string", "rules": []},
            {"source": "size_bytes", "target": "size_bytes", "source_type": "N", "bson_type": "long", "rules": []},
            {"source": "s3_key", "target": "s3_key", "source_type": "S", "bson_type": "string", "rules": []},
            {"source": "owner_id", "target": "owner_id", "source_type": "S", "bson_type": "string", "rules": []},
            {"source": "folder_id", "target": "folder_id", "source_type": "S", "bson_type": "string", "rules": ["null_missing_equiv"]},
            {"source": "is_trashed", "target": "is_trashed", "source_type": "BOOL", "bson_type": "bool", "rules": []},
            {"source": "version", "target": "version", "source_type": "N", "bson_type": "int", "rules": []},
            {"source": "created_at", "target": "created_at", "source_type": "S(iso8601)", "bson_type": "date", "rules": ["datetime_utc_truncate_ms"]},
            {"source": "updated_at", "target": "updated_at", "source_type": "S(iso8601)", "bson_type": "date", "rules": ["datetime_utc_truncate_ms"]},
            {"source": "ns", "target": "source_ns", "source_type": "S", "bson_type": "string", "rules": []},
        ],
        "embeds": [],
        "derived_ungraded": [{"target": "orphaned_metadata", "from": "s3_key presence", "rule": "marker when the S3 object is absent (40 expected); reported, item still migrates"}],
        "indexes": [{"keys": {"owner_id": 1, "is_trashed": 1}}, {"keys": {"folder_id": 1}}],
        "namespace_field": {"target": "ns", "value": NS},
        "notes": "Item-per-document 1:1. DynamoDB ns attribute is the tenant partition and is carried as source_ns; migration namespace is ns.",
    })

    # ---- wave 2: transactional billing core used by the PL/SQL packages (unit U5) -----
    cols.append(oracle_collection(census, "subscriptions", "SUBSCRIPTIONS", ["ID"], unit="U5", wave=2,
                                  indexes=[{"keys": {"tenant_id": 1, "starts_on": -1}}],
                                  notes="TRG_SUB_NO_UNCANCEL (status 30 may not revert) and TRG_SUBSCRIPTIONS_HIST move to the application write path (U6)."))
    cols.append(oracle_collection(census, "subscriptions_history", "SUBSCRIPTIONS_HIST", ["HIST_ID"], unit="U5", wave=2,
                                  notes="0 rows at census; created + registered as the history target for the rewritten write path."))
    cols.append(oracle_collection(census, "usage_events", "USAGE_EVENTS", ["ID"], unit="U5", wave=2,
                                  indexes=[{"keys": {"tenant_id": 1, "occurred_at": 1}}],
                                  notes="TRG_USAGE_EVENTS_CHECK (units >= 0) becomes a $jsonSchema validator on the collection."))
    cols.append(oracle_collection(
        census, "rating_periods", "RATING_PERIODS", ["ID"], unit="U5", wave=2,
        embeds=[embed(census, "results", "RATING_RESULTS", ["PERIOD_ID"], ["ID"], "id")],
        indexes=[{"keys": {"tenant_id": 1, "period_start": 1}, "unique": True}],
        notes="RATING_RESULTS 1:1 with its period in practice (3/3); embedded as results[] to keep the DUP_VAL_ON_INDEX upsert a single-document operation."))
    cols.append(oracle_collection(
        census, "billing_invoices", "INVOICES", ["ID"], unit="U5", wave=2,
        embeds=[embed(census, "lines", "INVOICE_LINES", ["INVOICE_ID"], ["ID"], "id")],
        indexes=[{"keys": {"tenant_id": 1, "issued_at": 1}}, {"keys": {"status_cd": 1, "issued_at": 1}}],
        notes="Package-owned transactional invoices (distinct from the bulk INVOICE_HEADER feed → invoices). Lines rebuilt from scratch on every issue → single replaceOne."))
    cols.append(oracle_collection(census, "credit_notes", "CREDIT_NOTES", ["ID"], unit="U5", wave=2,
                                  indexes=[{"keys": {"tenant_id": 1, "issued_on": 1, "_id": 1}}]))
    cols.append(oracle_collection(census, "dunning_attempts", "DUNNING_ATTEMPTS", ["ID"], unit="U5", wave=2,
                                  indexes=[{"keys": {"invoice_id": 1, "attempt_no": 1}, "unique": True}],
                                  notes="UQ_DUNNING_ATTEMPTS preserved as a unique index; the swallowed WHEN OTHERS insert becomes an explicit duplicate-key no-op."))
    cols.append(oracle_collection(census, "notifications", "NOTIFICATIONS", ["ID"], unit="U5", wave=2,
                                  indexes=[{"keys": {"tenant_id": 1, "kind_cd": 1, "sent_at": 1}, "unique": True}]))
    cols.append(oracle_collection(census, "billing_audit_log", "BILLING_AUDIT_LOG", ["LOG_ID"], unit="U5", wave=2,
                                  indexes=[{"keys": {"logged_at": 1}, "expireAfterSeconds": 90 * 86400}],
                                  notes="0 rows at census. JOB_PURGE_AUDIT_LOG (90-day delete, disabled) becomes a TTL index; log_id from counters collection."))

    spec = {
        "version": VERSION,
        "namespace": NS,
        "target_database": "ow_tp_mongodb_205236",
        "quarantine_database": "ow_tp_mongodb_205236_quarantine",
        "params": {"batch_no": "Oracle conversion/batch number for the namespace (85559852 for NS=demo)",
                   "source_ns": "DynamoDB ns partition value (demo)"},
        "excluded_objects": [
            {"object": "FIXTURE_META", "reason": "fixture bookkeeping (INITIALIZED_AT, non-deterministic); no application reader"},
        ],
        "collections": cols,
    }
    OUT.write_text(json.dumps(spec, indent=1) + "\n")
    n_fields = sum(len(c["fields"]) for c in cols)
    n_embed_fields = sum(len(e["fields"]) for c in cols for e in c["embeds"])
    print(f"mapping spec written: {OUT}\n  collections: {len(cols)}  root fields: {n_fields}  "
          f"embedded fields: {n_embed_fields}  embeds: {sum(len(c['embeds']) for c in cols)}")


if __name__ == "__main__":
    main()
