#!/usr/bin/env python3
"""Migrate OW_BILLING.CUSTOMER_MASTER + ENTITY_ATTR_VALUE into a document model.

Source (Oracle, schema OW_BILLING):
  CUSTOMER_MASTER     155 columns, one row per customer, scoped by
                      CONVERSION_BATCH_NO.
  ENTITY_ATTR_VALUE   attribute sprawl; rows with ENTITY_TYPE='CUSTOMER'
                      belong on their customer.

Target (MongoDB, database ow_tp_<ns>):
  customers             one document per customer row, _id = CUST_ID.
  customers_quarantine  row-level and field-level quarantine records.

Design rules enforced here:

* Sparse columns are optional fields. A NULL source column produces no key at
  all -- the target never carries the 100+ always-empty UDF_*/FLAG_* columns.
* Repeating groups (ADDR_LINE_1..6 + MAIL_ADDR_*, PHONE1..4, EMAIL_1..3) are
  reshaped into arrays of subdocuments losslessly: address lines keep their
  source ordinal, so a populated line 3 with an empty line 2 does not shift.
* Delimited ID lists become real arrays. A list that does not parse cleanly is
  never guessed at: the field is omitted and a field-level quarantine record
  keeps the raw value (reason MALFORMED_CSV).
* 'DD-MON-YY' string dates become BSON dates. A string that is not a real
  calendar date is quarantined field-level (reason INVALID_DATE) with the raw
  value kept; the row still migrates without that field.
* A row without its required key is quarantined whole (reason
  MISSING_REQUIRED_KEY) -- never defaulted, never silently dropped.
* An EAV row whose ENTITY_ID matches no in-scope customer is quarantined
  (reason EAV_NO_CUSTOMER); a non-string EAV value type is quarantined
  (reason EAV_UNSUPPORTED_TYPE).

Every write is an upsert keyed on a deterministic _id derived from source keys,
and each run reconciles the target back to the source, so a rerun converges
instead of accumulating.
"""

from __future__ import annotations

import argparse
import datetime as dt
import decimal
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict

import bson
import oracledb
from bson.decimal128 import Decimal128
from pymongo import MongoClient, ReplaceOne

SOURCE_TABLE = "OW_BILLING.CUSTOMER_MASTER"
EAV_TABLE = "OW_BILLING.ENTITY_ATTR_VALUE"
CUSTOMERS = "customers"
QUARANTINE = "customers_quarantine"
BATCH_SIZE = 1000

MONTHS = {m: i + 1 for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
     "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}
DATE_RE = re.compile(r"^(\d{2})-([A-Z]{3})-(\d{2})$")

# Legacy 'DD-MON-YY' string columns that carry a real calendar date.
DATE_STRING_COLUMNS = {
    "signup_dt", "last_activity_dt", "last_invoice_dt", "last_payment_dt",
    "terminate_dt", *(f"udf_dt_{i:02d}" for i in range(1, 11)),
}

# Delimited lists. ID lists hold account identifiers; code lists hold promo
# codes. Each has its own token alphabet -- see token_ok().
CSV_ID_COLUMNS = {"related_acct_ids": "related_acct_ids",
                  "child_acct_ids": "child_acct_ids"}
CSV_CODE_COLUMNS = {"promo_codes_csv": "promo_codes"}

# "Malformed" is defined explicitly, and a malformed list is quarantined whole
# rather than partially salvaged:
#   * an empty or whitespace-only token (dangling, leading, trailing or
#     doubled delimiter) -- note an entirely empty column value is simply an
#     absent list, not a malformed one;
#   * a token outside the field's alphabet: ID tokens are 4-10 digits, code
#     tokens are upper-case alphanumerics with '_' or '-';
#   * any embedded whitespace inside a token.
ID_TOKEN_RE = re.compile(r"^[0-9]{4,10}$")
CODE_TOKEN_RE = re.compile(r"^[A-Z0-9][A-Z0-9_-]*$")

ADDRESS_GROUPS = [
    ("physical", "addr_line_", "city", "state_cd", "zip", "zip4", "country_cd"),
    ("mailing", "mail_addr_line_", "mail_city", "mail_state_cd", "mail_zip",
     None, None),
]
PHONE_COUNT = 4
EMAIL_COUNT = 3

# Columns consumed by a reshaped group; they must not also appear at top level.
GROUPED_COLUMNS = (
    {f"addr_line_{i}" for i in range(1, 7)}
    | {f"mail_addr_line_{i}" for i in range(1, 7)}
    | {"city", "state_cd", "zip", "zip4", "country_cd",
       "mail_city", "mail_state_cd", "mail_zip"}
    | {f"phone{i}" for i in range(1, PHONE_COUNT + 1)}
    | {f"phone{i}_type_cd" for i in range(1, PHONE_COUNT + 1)}
    | {f"email_{i}" for i in range(1, EMAIL_COUNT + 1)}
    | set(CSV_ID_COLUMNS) | set(CSV_CODE_COLUMNS)
    | {"cust_id", "conversion_batch_no"}
)


# --------------------------------------------------------------------------
# value conversion
# --------------------------------------------------------------------------

def is_null(value) -> bool:
    """A source column counts as absent when NULL or blank-only."""
    return value is None or (isinstance(value, str) and value.strip() == "")


def parse_legacy_date(raw: str) -> dt.datetime:
    """Parse 'DD-MON-YY'. Raises ValueError on anything that is not a date."""
    match = DATE_RE.match(raw)
    if not match:
        raise ValueError(f"not DD-MON-YY: {raw!r}")
    day, mon, year = match.groups()
    if mon not in MONTHS:
        raise ValueError(f"unknown month: {raw!r}")
    yy = int(year)
    century = 2000 if yy <= 49 else 1900
    return dt.datetime(century + yy, MONTHS[mon], int(day))


def token_ok(token: str, kind: str) -> bool:
    pattern = ID_TOKEN_RE if kind == "id" else CODE_TOKEN_RE
    return bool(pattern.match(token))


def parse_delimited(raw: str, kind: str) -> list[str] | None:
    """Split a delimited list. Returns None when the list is malformed."""
    tokens = raw.split(",")
    if not all(token_ok(token, kind) for token in tokens):
        return None
    return tokens


def convert_scalar(column: str, value):
    """Map a non-NULL scalar column onto its BSON type."""
    if isinstance(value, decimal.Decimal):
        if column.endswith("_amt"):
            return Decimal128(value)
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, float):
        return value
    if isinstance(value, dt.datetime):
        return value
    if isinstance(value, dt.date):
        return dt.datetime(value.year, value.month, value.day)
    if isinstance(value, str):
        return value.strip() if value.strip() != value else value
    return value


# --------------------------------------------------------------------------
# document construction
# --------------------------------------------------------------------------

def field_quarantine(cust_id: str, field: str, raw, reason: str,
                     ns: str, batch_no: int) -> dict:
    return {
        "_id": f"field::{cust_id}::{field}::{reason}",
        "scope": "field",
        "reason": reason,
        "cust_id": cust_id,
        "field": field,
        "raw_value": raw,
        "source_table": SOURCE_TABLE,
        "namespace": ns,
        "conversion_batch_no": batch_no,
    }


def row_quarantine(row: dict, reason: str, ns: str, batch_no: int) -> dict:
    present = {k: (str(v) if v is not None else None)
               for k, v in row.items() if not is_null(v)}
    digest = hashlib.sha1(
        json.dumps(present, sort_keys=True).encode()).hexdigest()
    return {
        "_id": f"row::{reason}::{digest}",
        "scope": "row",
        "reason": reason,
        "source_table": SOURCE_TABLE,
        "namespace": ns,
        "conversion_batch_no": batch_no,
        "raw_row": present,
    }


def build_addresses(row: dict) -> list[dict]:
    addresses = []
    for kind, line_prefix, city, state, zipc, zip4, country in ADDRESS_GROUPS:
        # Address lines keep their source ordinal so a gap does not shift them.
        lines = {f"line_{i}": row[f"{line_prefix}{i}"]
                 for i in range(1, 7)
                 if f"{line_prefix}{i}" in row and not is_null(row[f"{line_prefix}{i}"])}
        entry: dict = {"kind": kind}
        if lines:
            entry["lines"] = lines
        for target, column in (("city", city), ("state_cd", state),
                               ("zip", zipc), ("zip4", zip4),
                               ("country_cd", country)):
            if column and column in row and not is_null(row[column]):
                entry[target] = convert_scalar(column, row[column])
        if len(entry) > 1:
            addresses.append(entry)
    return addresses


def build_phones(row: dict) -> list[dict]:
    phones = []
    for i in range(1, PHONE_COUNT + 1):
        number, type_cd = row.get(f"phone{i}"), row.get(f"phone{i}_type_cd")
        entry: dict = {"seq": i}
        if not is_null(number):
            entry["number"] = convert_scalar(f"phone{i}", number)
        if not is_null(type_cd):
            entry["type_cd"] = convert_scalar(f"phone{i}_type_cd", type_cd)
        if len(entry) > 1:
            phones.append(entry)
    return phones


def build_emails(row: dict) -> list[dict]:
    emails = []
    for i in range(1, EMAIL_COUNT + 1):
        value = row.get(f"email_{i}")
        if not is_null(value):
            emails.append({"seq": i,
                           "address": convert_scalar(f"email_{i}", value)})
    return emails


def build_document(row: dict, ns: str, batch_no: int
                   ) -> tuple[dict | None, list[dict]]:
    """Transform one CUSTOMER_MASTER row. Returns (document, quarantine)."""
    cust_id = row.get("cust_id")
    if is_null(cust_id):
        return None, [row_quarantine(row, "MISSING_REQUIRED_KEY", ns, batch_no)]

    quarantine: list[dict] = []
    doc: dict = {"_id": cust_id}

    for column, value in row.items():
        if column in GROUPED_COLUMNS or is_null(value):
            continue
        if column in DATE_STRING_COLUMNS:
            try:
                doc[column] = parse_legacy_date(value)
            except ValueError:
                quarantine.append(field_quarantine(
                    cust_id, column, value, "INVALID_DATE", ns, batch_no))
            continue
        doc[column] = convert_scalar(column, value)

    for column, target in {**CSV_ID_COLUMNS, **CSV_CODE_COLUMNS}.items():
        raw = row.get(column)
        if is_null(raw):
            continue
        kind = "id" if column in CSV_ID_COLUMNS else "code"
        tokens = parse_delimited(raw, kind)
        if tokens is None:
            quarantine.append(field_quarantine(
                cust_id, column, raw, "MALFORMED_CSV", ns, batch_no))
            continue
        doc[target] = tokens

    for key, builder in (("addresses", build_addresses),
                         ("phones", build_phones),
                         ("emails", build_emails)):
        built = builder(row)
        if built:
            doc[key] = built

    doc["_migration"] = {
        "source_table": SOURCE_TABLE,
        "namespace": ns,
        "conversion_batch_no": batch_no,
    }
    return doc, quarantine


# --------------------------------------------------------------------------
# source reads
# --------------------------------------------------------------------------

def oracle_connect(args) -> oracledb.Connection:
    return oracledb.connect(user=args.oracle_user, password=args.oracle_password,
                            host=args.oracle_host, port=args.oracle_port,
                            service_name=args.oracle_service)


def number_type_handler(cursor, name, default_type, size, precision, scale):
    """Read Oracle NUMBER as Decimal so money keeps its exact scale."""
    if default_type == oracledb.DB_TYPE_NUMBER:
        return cursor.var(decimal.Decimal, arraysize=cursor.arraysize)
    return None


def read_eav(conn, batch_no: int, ns: str
             ) -> tuple[dict[str, dict], list[dict], dict[str, int]]:
    """Fold ENTITY_ATTR_VALUE onto customers.

    Ownership of an EAV row is established by its ENTITY_ID resolving to a
    CUSTOMER_MASTER row in this conversion batch. A row that resolves to a
    customer in another batch is out of scope for this unit; a row that
    resolves to no customer at all is quarantined.
    """
    cur = conn.cursor()
    cur.arraysize = 5000
    cur.execute(
        """SELECT e.eav_id, e.entity_id, e.attr_name, e.attr_value,
                  e.attr_type, c.conversion_batch_no
             FROM entity_attr_value e
             LEFT JOIN customer_master c ON c.cust_id = e.entity_id
            WHERE e.entity_type = 'CUSTOMER'""")

    attributes: dict[str, dict] = defaultdict(dict)
    quarantine: list[dict] = []
    stats = Counter()
    for eav_id, entity_id, attr_name, attr_value, attr_type, row_batch in cur:
        stats["scanned"] += 1
        batch = int(row_batch) if row_batch is not None else None
        if batch is not None and batch != batch_no:
            stats["out_of_scope_other_batch"] += 1
            continue
        stats["in_scope"] += 1
        if batch is None:
            stats["quarantined_no_customer"] += 1
            quarantine.append({
                "_id": f"eav::{int(eav_id)}::EAV_NO_CUSTOMER",
                "scope": "row",
                "reason": "EAV_NO_CUSTOMER",
                "source_table": EAV_TABLE,
                "namespace": ns,
                "conversion_batch_no": batch_no,
                "eav_id": int(eav_id),
                "entity_id": entity_id,
                "attr_name": attr_name,
                "raw_value": attr_value,
            })
            continue
        if attr_type is not None and attr_type != "STR":
            stats["quarantined_unsupported_type"] += 1
            quarantine.append({
                "_id": f"eav::{int(eav_id)}::EAV_UNSUPPORTED_TYPE",
                "scope": "row",
                "reason": "EAV_UNSUPPORTED_TYPE",
                "source_table": EAV_TABLE,
                "namespace": ns,
                "conversion_batch_no": batch_no,
                "eav_id": int(eav_id),
                "entity_id": entity_id,
                "attr_name": attr_name,
                "attr_type": attr_type,
                "raw_value": attr_value,
            })
            continue
        # Values are untyped legacy strings and are preserved as-is. A repeated
        # (entity_id, attr_name) keeps every value rather than losing one.
        bucket = attributes[entity_id]
        if attr_name in bucket:
            existing = bucket[attr_name]
            if isinstance(existing, list):
                existing.append(attr_value)
            else:
                bucket[attr_name] = [existing, attr_value]
            stats["duplicate_attr_values"] += 1
        else:
            bucket[attr_name] = attr_value
        stats["folded"] += 1
    cur.close()
    return attributes, quarantine, dict(stats)


def iter_customer_rows(conn, batch_no: int):
    cur = conn.cursor()
    cur.arraysize = 500
    cur.prefetchrows = 501
    cur.outputtypehandler = number_type_handler
    cur.execute("SELECT * FROM customer_master WHERE conversion_batch_no = :1",
                [batch_no])
    columns = [d[0].lower() for d in cur.description]
    for row in cur:
        yield dict(zip(columns, row))
    cur.close()


# --------------------------------------------------------------------------
# target writes
# --------------------------------------------------------------------------

def flush(collection, ops: list[ReplaceOne]) -> None:
    if ops:
        collection.bulk_write(ops, ordered=False)


def prune_stale(collection, batch_no: int, keep: set[str], label: str) -> int:
    """Drop documents this unit wrote for this batch that no longer exist.

    Scoped to this unit's collections and this conversion batch, so a
    concurrent namespace's data is never touched, and a rerun that legitimately
    produces fewer records converges instead of leaving orphans behind.
    """
    existing = {d["_id"] for d in collection.find(
        {"conversion_batch_no": batch_no}
        if label == QUARANTINE
        else {"_migration.conversion_batch_no": batch_no}, {"_id": 1})}
    stale = existing - keep
    if stale:
        collection.delete_many({"_id": {"$in": sorted(stale)}})
    return len(stale)


def migrate(args) -> dict:
    ns, batch_no = args.ns, args.batch_no
    client = MongoClient(mongo_uri(), appname="ow_tp_customers_migration")
    db = client[f"ow_tp_{ns}"]
    customers, quarantine_col = db[CUSTOMERS], db[QUARANTINE]

    conn = oracle_connect(args)
    attributes, eav_quarantine, eav_stats = read_eav(conn, batch_no, ns)

    stats = Counter()
    cust_ops: list[ReplaceOne] = []
    quar_ops: list[ReplaceOne] = []
    cust_ids: set[str] = set()
    quar_ids: set[str] = set()
    quar_reasons = Counter()
    attributes_written = 0
    attribute_values_written = 0

    def stage_quarantine(record: dict) -> None:
        nonlocal quar_ops
        quar_ids.add(record["_id"])
        quar_reasons[record["reason"]] += 1
        quar_ops.append(ReplaceOne({"_id": record["_id"]}, record, upsert=True))
        if len(quar_ops) >= BATCH_SIZE:
            flush(quarantine_col, quar_ops)
            quar_ops = []

    for record in eav_quarantine:
        stage_quarantine(record)

    for row in iter_customer_rows(conn, batch_no):
        stats["source_rows"] += 1
        doc, row_quarantines = build_document(row, ns, batch_no)
        for record in row_quarantines:
            stage_quarantine(record)
        if doc is None:
            stats["rows_quarantined"] += 1
            continue
        attrs = attributes.get(doc["_id"])
        if attrs:
            doc["attributes"] = attrs
            attributes_written += 1
            attribute_values_written += sum(
                len(v) if isinstance(v, list) else 1 for v in attrs.values())
        cust_ids.add(doc["_id"])
        cust_ops.append(ReplaceOne({"_id": doc["_id"]}, doc, upsert=True))
        stats["documents_written"] += 1
        if len(cust_ops) >= BATCH_SIZE:
            flush(customers, cust_ops)
            cust_ops = []

    flush(customers, cust_ops)
    flush(quarantine_col, quar_ops)

    stale_customers = prune_stale(customers, batch_no, cust_ids, CUSTOMERS)
    stale_quarantine = prune_stale(quarantine_col, batch_no, quar_ids, QUARANTINE)
    conn.close()
    client.close()

    result = {
        "namespace": ns,
        "conversion_batch_no": batch_no,
        "source_rows": stats["source_rows"],
        "documents_written": stats["documents_written"],
        "rows_quarantined": stats["rows_quarantined"],
        "documents_with_attributes": attributes_written,
        "attribute_values_written": attribute_values_written,
        "quarantine_by_reason": dict(quar_reasons),
        "eav": eav_stats,
        "stale_pruned": {"customers": stale_customers,
                         "customers_quarantine": stale_quarantine},
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


# --------------------------------------------------------------------------
# target-side reconciliation
# --------------------------------------------------------------------------

def mongo_uri() -> str:
    uri = os.environ.get("MONGODB_ATLAS_URI")
    if not uri:
        print("MONGODB_ATLAS_URI is not set", file=sys.stderr)
        raise SystemExit(2)
    return uri


def fingerprint(args) -> str:
    """Content fingerprint of the target, recomputed from the database.

    Hashes every document's canonical BSON, so a rerun that duplicated an
    attribute, re-appended an array element, or rewrote any field would change
    the digest.
    """
    client = MongoClient(mongo_uri(), appname="ow_tp_customers_fingerprint")
    db = client[f"ow_tp_{args.ns}"]
    digest = hashlib.sha256()
    counts = {}
    for name in (CUSTOMERS, QUARANTINE):
        scope = ({"_migration.conversion_batch_no": args.batch_no}
                 if name == CUSTOMERS else
                 {"conversion_batch_no": args.batch_no})
        total = 0
        for doc in db[name].find(scope).sort("_id", 1):
            digest.update(bson.encode(doc))
            total += 1
        counts[name] = total
    client.close()
    value = digest.hexdigest()
    print(json.dumps({"fingerprint": value, "counts": counts}, sort_keys=True))
    return value


def target_measurements(db, batch_no: int) -> dict:
    customers = db[CUSTOMERS]
    quarantine = db[QUARANTINE]
    scope = {"_migration.conversion_batch_no": batch_no}
    quar_scope = {"conversion_batch_no": batch_no}

    folded = list(customers.aggregate([
        {"$match": {**scope, "attributes": {"$exists": True}}},
        {"$project": {"n": {"$sum": {"$map": {
            "input": {"$objectToArray": "$attributes"}, "as": "a",
            "in": {"$cond": [{"$isArray": "$$a.v"}, {"$size": "$$a.v"}, 1]}}}}}},
        {"$group": {"_id": None, "values": {"$sum": "$n"},
                    "docs": {"$sum": 1}}},
    ]))
    folded_values = folded[0]["values"] if folded else 0
    folded_docs = folded[0]["docs"] if folded else 0

    reasons = {r["_id"]: r["n"] for r in quarantine.aggregate([
        {"$match": quar_scope},
        {"$group": {"_id": "$reason", "n": {"$sum": 1}}},
    ])}

    keys = sorted(k["_id"] for k in customers.aggregate([
        {"$match": scope},
        {"$project": {"kv": {"$objectToArray": "$$ROOT"}}},
        {"$unwind": "$kv"},
        {"$group": {"_id": "$kv.k"}},
    ]))

    null_fields = list(customers.aggregate([
        {"$match": scope},
        {"$project": {"nulls": {"$size": {"$filter": {
            "input": {"$objectToArray": "$$ROOT"}, "as": "kv",
            "cond": {"$eq": [{"$type": "$$kv.v"}, "null"]}}}}}},
        {"$match": {"nulls": {"$gt": 0}}},
        {"$count": "docs"},
    ]))

    return {
        "documents": customers.count_documents(scope),
        "documents_with_attributes": folded_docs,
        "attribute_values": folded_values,
        "quarantine_total": quarantine.count_documents(quar_scope),
        "quarantine_by_reason": reasons,
        "top_level_keys": keys,
        "docs_with_null_valued_fields": (
            null_fields[0]["docs"] if null_fields else 0),
        "docs_missing_signup_dt": customers.count_documents(
            {**scope, "signup_dt": {"$exists": False}}),
        "docs_with_related_acct_ids": customers.count_documents(
            {**scope, "related_acct_ids": {"$exists": True}}),
        "docs_with_promo_codes": customers.count_documents(
            {**scope, "promo_codes": {"$exists": True}}),
    }


def recon(args) -> int:
    manifest = json.loads(open(args.manifest).read())
    anomalies = {a["kind"]: a["count"] for a in manifest["planted_anomalies"]}
    expected_customers = manifest["targets"][f"oracle.{SOURCE_TABLE}"]["rows"]
    expected_eav = manifest["targets"][f"oracle.{EAV_TABLE}"]["rows"]
    expected_dates = anomalies["dirty_dates"]
    expected_csv = anomalies["malformed_csv_lists"]

    client = MongoClient(mongo_uri(), appname="ow_tp_customers_recon")
    measured = target_measurements(client[f"ow_tp_{args.ns}"], args.batch_no)
    client.close()

    reasons = measured["quarantine_by_reason"]
    invalid_dates = reasons.get("INVALID_DATE", 0)
    malformed_csv = reasons.get("MALFORMED_CSV", 0)
    missing_key = reasons.get("MISSING_REQUIRED_KEY", 0)
    eav_no_customer = reasons.get("EAV_NO_CUSTOMER", 0)
    eav_bad_type = reasons.get("EAV_UNSUPPORTED_TYPE", 0)
    eav_accounted = (measured["attribute_values"] + eav_no_customer
                     + eav_bad_type)
    udf_keys = [k for k in measured["top_level_keys"]
                if k.startswith(("udf_", "flag_"))]

    checks = [
        ("customer-documents", expected_customers - missing_key,
         measured["documents"], f"mongodb ow_tp_{args.ns}.customers"),
        ("eav-rows-accounted", expected_eav, eav_accounted,
         f"mongodb ow_tp_{args.ns}.customers.attributes + quarantine"),
        ("invalid-date-quarantine", expected_dates, invalid_dates,
         f"mongodb ow_tp_{args.ns}.customers_quarantine"),
        ("malformed-csv-quarantine", expected_csv, malformed_csv,
         f"mongodb ow_tp_{args.ns}.customers_quarantine"),
        ("missing-required-key-rows", 0, missing_key,
         f"mongodb ow_tp_{args.ns}.customers_quarantine"),
        ("documents-missing-signup-dt", invalid_dates,
         measured["docs_missing_signup_dt"],
         f"mongodb ow_tp_{args.ns}.customers"),
        ("no-null-valued-fields", 0, measured["docs_with_null_valued_fields"],
         f"mongodb ow_tp_{args.ns}.customers"),
        ("no-always-empty-udf-or-flag-keys", [], udf_keys,
         f"mongodb ow_tp_{args.ns}.customers key universe"),
    ]

    report = {
        "kind": "recon-report",
        "unit": "mongodb-customer-master",
        "namespace": args.ns,
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(
            microsecond=0).isoformat().replace("+00:00", "Z"),
        "run_mode": args.run_mode,
        "checks": [
            {"id": cid, "expected": exp, "actual": act,
             "source_of_truth": src,
             "result": "pass" if exp == act else "fail"}
            for cid, exp, act, src in checks
        ],
        "values_recomputed_from_target": True,
        "idempotency_rerun": {
            "performed": True,
            "result": "pass" if args.fingerprint_before == args.fingerprint_after
                      else "fail",
            "evidence": (
                "migration run twice against the same source batch; "
                "sha256 over canonical BSON of every customers + "
                f"customers_quarantine document: before={args.fingerprint_before} "
                f"after={args.fingerprint_after}"),
        },
        "planted_anomaly_detections": {
            "expected_set": [f"dirty_dates:{expected_dates}",
                             f"malformed_csv_lists:{expected_csv}"],
            "actual_set": [f"dirty_dates:{invalid_dates}",
                           f"malformed_csv_lists:{malformed_csv}"],
            "missing": ([f"dirty_dates:{expected_dates - invalid_dates}"]
                        if invalid_dates < expected_dates else [])
                       + ([f"malformed_csv_lists:{expected_csv - malformed_csv}"]
                          if malformed_csv < expected_csv else []),
            "unexpected": ([f"dirty_dates:{invalid_dates - expected_dates}"]
                           if invalid_dates > expected_dates else [])
                          + ([f"malformed_csv_lists:{malformed_csv - expected_csv}"]
                             if malformed_csv > expected_csv else []),
        },
        "unverified_paths": [
            "MISSING_REQUIRED_KEY row-level quarantine: rule implemented and "
            "reported, but the source batch holds no row without CUST_ID, so "
            "the path is unexercised on live data.",
            "EAV_NO_CUSTOMER quarantine: rule implemented and reported, but "
            "every in-scope ENTITY_ATTR_VALUE row resolves to a customer in "
            "this batch, so the orphan branch is unexercised on live data.",
            "EAV_UNSUPPORTED_TYPE quarantine: every in-scope ENTITY_ATTR_VALUE "
            "row carries ATTR_TYPE='STR', so the non-string branch is "
            "unexercised on live data.",
            "UDF_01..40 / UDF_AMT_01..10 / UDF_DT_01..10 / FLAG_01..20 and the "
            "mailing-address, PHONE3/PHONE4, EMAIL_2/EMAIL_3, DBA_NAME, "
            "CONTACT_NOTES and TERMINATE_DT columns are NULL for every row in "
            "this batch: their optional-field and date-parsing branches are "
            "implemented but unexercised on live data.",
            "ENTITY_ATTR_VALUE.CREATED_DT (a legacy row-audit string) and "
            "ATTR_TYPE are not carried onto the customer document; only the "
            "attribute name and raw value are folded.",
            "Only ENTITY_TYPE='CUSTOMER' EAV rows are in scope for this unit; "
            "other entity types are out of scope and untouched.",
        ],
        "measured": measured,
    }

    out = args.out
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    failed = [c["id"] for c in report["checks"] if c["result"] == "fail"]
    if failed:
        print(f"RECON FAIL: {', '.join(failed)}", file=sys.stderr)
        return 1
    if report["idempotency_rerun"]["result"] == "fail":
        print("RECON FAIL: idempotency", file=sys.stderr)
        return 1
    print(f"recon written: {out}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["migrate", "fingerprint", "recon"])
    parser.add_argument("--ns", required=True)
    parser.add_argument("--batch-no", type=int, required=True)
    parser.add_argument("--oracle-host", default=os.environ.get("DB_HOST", "localhost"))
    parser.add_argument("--oracle-port", type=int,
                        default=int(os.environ.get("DB_PORT", "52521")))
    parser.add_argument("--oracle-user", default=os.environ.get("DB_USER", "ow_billing"))
    parser.add_argument("--oracle-password",
                        default=os.environ.get("DB_PASSWORD", "ow_billing"))
    parser.add_argument("--oracle-service",
                        default=os.environ.get("DB_SERVICE", "FREEPDB1"))
    parser.add_argument("--manifest")
    parser.add_argument("--out")
    parser.add_argument("--run-mode", choices=["fixture", "live"], default="live")
    parser.add_argument("--fingerprint-before")
    parser.add_argument("--fingerprint-after")
    args = parser.parse_args()

    if args.command == "migrate":
        migrate(args)
        return 0
    if args.command == "fingerprint":
        fingerprint(args)
        return 0
    for required in ("manifest", "out", "fingerprint_before", "fingerprint_after"):
        if not getattr(args, required):
            parser.error(f"recon requires --{required.replace('_', '-')}")
    return recon(args)


if __name__ == "__main__":
    sys.exit(main())
