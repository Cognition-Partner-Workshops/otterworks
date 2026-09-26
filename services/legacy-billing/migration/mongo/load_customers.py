"""u-02-customers loader: Oracle CUSTOMER_MASTER(+ENTITY_ATTR_VALUE) -> MongoDB.

Offline fixture run (target_class=local). Drops and recreates exactly the two
collections this unit owns (ow_billing_migration.customerMaster,
ow_billing_migration.customerMasterHist), streams the Oracle source through the
spec's canonicalization rules, and quarantines non-conforming field values on
the document (`_quarantine`) per .migration/05_decisions.

Credentials are read only from the named environment variables; nothing in this
module prints, logs, or persists secret values.
"""

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import oracledb
from bson.decimal128 import Decimal128
from pymongo import MongoClient

ALLOWED_TARGETS_FILE = ".migration/allowed_targets.json"
TARGET_DB = "ow_billing_migration"
WRITE_TARGETS = ("customerMaster", "customerMasterHist")
SPEC_PATH = (
    Path(__file__).resolve().parents[4]
    / "services/legacy-billing/migration/mongo/specs/u-02-customers.mapping.json"
)
REPO_ROOT = Path(__file__).resolve().parents[4]

ARRAY_SIZE = 5000
BATCH_SIZE = 2000

_INDEXES = {
    "customerMaster": [("tenantId", 1), ("custSeqNo", 1)],
    "customerMasterHist": [("custId", 1), ("histDt", 1)],
}

OMIT = object()  # sentinel: field omitted from the document


def _rule_names(field):
    return {r.split(":", 1)[0] for r in field.get("rules", [])}


def convert_value(raw, field):
    """Convert one source value per the field's spec rules.

    Returns (value, quarantine_reason): value is OMIT when the field is left
    off the document, in which case quarantine_reason is None for a plain
    null/empty or a reason code for a rejected non-null value.
    """
    if raw is None:
        return OMIT, None
    rules = _rule_names(field)
    bson_type = field.get("bson_type")
    value = raw
    if isinstance(value, str):
        stripped = value.rstrip(" ")
        if stripped == "":
            return OMIT, None
        if "rstrip_spaces" in rules:
            value = stripped

    if bson_type == "long" or "int_to_long" in rules:
        return int(value), None

    if bson_type == "decimal" or "decimal_round" in rules:
        return Decimal128(Decimal(value)), None

    if bson_type == "bool" and "yn_to_bool" in rules:
        flag = value.strip() if isinstance(value, str) else value
        if flag in ("Y", "N"):
            return flag == "Y", None
        return OMIT, "bad_flag"

    if bson_type == "date":
        if "datetime_utc_truncate_ms" in rules:
            # Oracle DATE arrives as a naive datetime; pymongo stores it as
            # UTC and millisecond truncation is a no-op for DATE.
            return value, None
        if "date_string_to_date" in rules:
            try:
                return datetime.strptime(
                    value.strip(), field["date_format"]
                ), None
            except (ValueError, TypeError):
                return OMIT, "bad_date"

    if bson_type == "array" and "csv_to_array" in rules:
        text = value if isinstance(value, str) else str(value)
        tokens = [token.strip() for token in text.split(",")]
        if ";" in text or any(
            token in ("NULL", "NONE") for token in tokens if token
        ):
            return OMIT, "malformed_csv"
        return [token for token in tokens if token], None

    return value, None


def derive_customer_defaults(doc, next_seq):
    """Defaults for app-written customerMaster documents (contract
    u-02-customers, "Trigger-derived columns"): the trigger columns MongoDB has
    no trigger for. Pure function; returns a new doc."""
    out = dict(doc)
    if out.get("custSeqNo") is None:
        out["custSeqNo"] = next_seq
    if out.get("custName") is not None:
        out["custNameUpper"] = str(out["custName"]).upper()
    if out.get("rowVersionNo") is None:
        out["rowVersionNo"] = 1
    return out


def _number_as_decimal(number_type):
    """Fetch non-integer NUMBER as Decimal; the driver default is float, which
    loses digits past 15. Mirrors the recon harness OracleSourceAdapter."""

    def handler(cursor, metadata):
        if metadata.type_code is number_type and not (
            metadata.scale == 0 and metadata.precision
        ):
            return cursor.var(Decimal, arraysize=cursor.arraysize)

    return handler


def _check_allowed_targets(repo_root):
    allowed_file = repo_root / ALLOWED_TARGETS_FILE
    allowed = json.loads(allowed_file.read_text())
    databases = set(allowed.get("databases", [])) | set(
        allowed.get("catalogs", [])
    )
    if TARGET_DB not in databases:
        raise SystemExit(
            f"target database {TARGET_DB!r} not in {ALLOWED_TARGETS_FILE}"
        )
    declared = set(allowed.get("collections", [])) | set(
        allowed.get("targets", [])
    )
    for coll in WRITE_TARGETS:
        if declared and f"{TARGET_DB}.{coll}" not in declared:
            raise SystemExit(
                f"target {TARGET_DB}.{coll} not in {ALLOWED_TARGETS_FILE}"
            )


def _select_columns(collection_spec):
    columns = list(collection_spec["key"]["source"])
    for field in collection_spec["fields"]:
        if field["source"] not in columns:
            columns.append(field["source"])
    return columns


def _build_document(collection_spec, names, row, counters):
    by_source = dict(zip(names, row))
    doc = {}
    key_sources = collection_spec["key"]["source"]
    key_fields = {
        kf["source"]: kf for kf in collection_spec["decision"].get("key_fields", [])
    }
    if len(key_sources) == 1:
        source = key_sources[0]
        key_field = key_fields.get(source, {"bson_type": "string"})
        value, _reason = convert_value(by_source[source], key_field)
        doc["_id"] = int(value) if key_field.get("bson_type") == "long" else value
    else:
        doc["_id"] = tuple(by_source[source] for source in key_sources)
    quarantine = []
    for field in collection_spec["fields"]:
        value, reason = convert_value(by_source[field["source"]], field)
        if value is OMIT:
            if reason:
                quarantine.append(
                    {
                        "field": field["target"],
                        "reason": reason,
                        "raw": str(by_source[field["source"]]),
                    }
                )
                counters["reasons"][reason] += 1
                counters["by_field"][
                    f"{collection_spec['collection']}.{field['target']}.{reason}"
                ] += 1
            continue
        doc[field["target"]] = value
    if quarantine:
        doc["_quarantine"] = quarantine
    return doc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", default=str(SPEC_PATH))
    parser.add_argument(
        "--source-dsn-secret", default="OW_BILLING_FIXTURE_DSN"
    )
    parser.add_argument("--target-uri-secret", default="MONGO_LOCAL_URI")
    parser.add_argument(
        "--report", default="/tmp/recon/u-02-customers/load_report.json"
    )
    args = parser.parse_args(argv)

    _check_allowed_targets(REPO_ROOT)

    dsn = json.loads(os.environ[args.source_dsn_secret])
    spec = json.loads(Path(args.spec).read_text())
    collections = {c["collection"]: c for c in spec["collections"]}

    client = MongoClient(os.environ[args.target_uri_secret])
    db = client[TARGET_DB]
    for coll_name in WRITE_TARGETS:
        db[coll_name].drop()
        db[coll_name].create_index(_INDEXES[coll_name])

    conn = oracledb.connect(
        user=dsn["user"], password=dsn["password"], dsn=dsn["dsn"]
    )
    conn.outputtypehandler = _number_as_decimal(oracledb.DB_TYPE_NUMBER)

    counters = {"reasons": Counter(), "by_field": Counter()}

    # EAV embed source: load once, group by entity_id.
    eav_spec = collections["customerMaster"]["embeds"][0]
    child_fields = eav_spec["child_fields"]
    child_key = eav_spec["key"]["source"][0]
    eav_cursor = conn.cursor()
    eav_cursor.arraysize = ARRAY_SIZE
    eav_cursor.execute(
        """SELECT eav_id, entity_type, entity_id, attr_name, attr_value,
                  attr_type, created_dt
             FROM entity_attr_value
            ORDER BY entity_id, eav_id"""
    )
    eav_names = [d[0].lower() for d in eav_cursor.description]
    eav_rows = {}
    eav_total = 0
    for raw in eav_cursor:
        eav_total += 1
        row = dict(zip(eav_names, raw))
        if row["entity_type"] != "CUSTOMER":
            counters["reasons"]["eav_unexpected_entity_type"] += 1
            continue
        element = {}
        element_quarantine = []
        for field in child_fields:
            source = field["source"].lower()
            value, reason = convert_value(row[source], field)
            if value is OMIT:
                if reason:
                    element_quarantine.append(
                        {
                            "field": field["target"],
                            "reason": reason,
                            "raw": str(row[source]),
                        }
                    )
                    counters["reasons"][reason] += 1
                    counters["by_field"][
                        f"customerMaster.attributes.{field['target']}.{reason}"
                    ] += 1
                continue
            if field["source"] == child_key:
                value = int(value)
            element[field["target"]] = value
        if element_quarantine:
            element["_quarantine"] = element_quarantine
        eav_rows.setdefault(row["entity_id"], []).append(element)
    eav_cursor.close()

    report = {
        "unit": "u-02-customers",
        "collections": {},
        "embedded": {"attributes": {"rows": eav_total, "embedded": 0}},
    }
    eav_orphans = 0
    eav_embedded = 0
    cust_ids = set()

    for coll_name in WRITE_TARGETS:
        collection_spec = collections[coll_name]
        columns = _select_columns(collection_spec)
        key_cols = collection_spec["key"]["source"]
        cursor = conn.cursor()
        cursor.arraysize = ARRAY_SIZE
        cursor.execute(
            f"SELECT {', '.join(columns)}"
            f" FROM {collection_spec['root_table']}"
            f" ORDER BY {', '.join(key_cols)}"
        )
        names = [d[0] for d in cursor.description]
        coll = db[coll_name]
        batch = []
        source_rows = 0
        docs_written = 0
        for row in cursor:
            source_rows += 1
            doc = _build_document(collection_spec, names, row, counters)
            if coll_name == "customerMaster":
                cust_ids.add(doc["_id"])
                attrs = eav_rows.get(doc["_id"], [])
                doc["attributes"] = sorted(
                    attrs, key=lambda e: e.get("eavId", 0)
                )
            batch.append(doc)
            if len(batch) >= BATCH_SIZE:
                coll.insert_many(batch, ordered=False)
                docs_written += len(batch)
                batch = []
        if batch:
            coll.insert_many(batch, ordered=False)
            docs_written += len(batch)
        cursor.close()
        report["collections"][coll_name] = {
            "source_rows": source_rows,
            "docs_written": docs_written,
        }

    for entity_id, elements in eav_rows.items():
        if entity_id in cust_ids:
            eav_embedded += len(elements)
        else:
            eav_orphans += len(elements)
    counters["reasons"]["eav_orphan"] += eav_orphans
    report["embedded"]["attributes"]["embedded"] = eav_embedded
    report["quarantine"] = dict(counters["reasons"])
    report["quarantine_by_field"] = dict(counters["by_field"])
    report["run_at"] = datetime.now(timezone.utc).isoformat()

    conn.close()
    client.close()

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, default=str) + "\n")

    print(f"unit: {report['unit']}  target: {TARGET_DB}")
    for coll_name, counts in report["collections"].items():
        print(
            f"  {coll_name}: source_rows={counts['source_rows']}"
            f" docs_written={counts['docs_written']}"
        )
    print(
        f"  attributes: rows={eav_total} embedded={eav_embedded}"
        f" orphans={eav_orphans}"
    )
    if report["quarantine"]:
        print("  quarantine:", json.dumps(report["quarantine"], sort_keys=True))
    print(f"  report: {report_path}")

    exit_code = 0
    if counters["reasons"].get("eav_unexpected_entity_type"):
        print(
            "  FAIL: eav_unexpected_entity_type > 0 (plan gap)",
            file=sys.stderr,
        )
        exit_code = 1
    if eav_orphans:
        print("  FAIL: eav_orphan > 0", file=sys.stderr)
        exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
