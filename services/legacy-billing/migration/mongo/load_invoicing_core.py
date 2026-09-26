import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import oracledb
from bson.decimal128 import Decimal128
from bson.int64 import Int64
from pymongo import MongoClient

oracledb.defaults.fetch_decimals = True

UNIT = "u-03-invoicing-core"
TARGET_DB = "ow_billing_migration"
WRITE_TARGETS = ("invoices", "creditNotes", "ratingPeriods", "ratingResults")

REPO_ROOT = Path(__file__).resolve().parents[4]
MAPPING_SPEC = REPO_ROOT / ".migration" / "03_mapping_spec.json"

_URI_LIKE = re.compile(r"^[a-z][a-z0-9+.-]*://")


def _fail(message):
    print(f"{UNIT}: {message}", file=sys.stderr)
    sys.exit(2)


def _secret(name, json_expected=False):
    if _URI_LIKE.match(name):
        _fail("secret NAME expected, got a literal URI")
    value = os.environ.get(name)
    if value is None:
        _fail(f"environment variable {name} is not set")
    if json_expected:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            _fail(f"environment variable {name} is not valid JSON")
    return value


def _check_allowlist(path):
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        _fail(f"cannot read allowed targets file: {exc}")
    if TARGET_DB not in data.get("databases", []):
        _fail(f"{TARGET_DB} is not an allowed target database")


def _utc_ms(value):
    value = value.replace(tzinfo=timezone.utc)
    return value.replace(microsecond=(value.microsecond // 1000) * 1000)


def _convert(value, bson_type):
    if value is None:
        return None
    if bson_type == "string":
        return None if value == "" else str(value)
    if bson_type == "long":
        return Int64(value)
    if bson_type == "decimal":
        return Decimal128(Decimal(str(value)).quantize(Decimal("0.01")))
    if bson_type == "date":
        return _utc_ms(value)
    return value


def _spec_collections():
    spec = json.loads(MAPPING_SPEC.read_text())
    return {
        entry["collection"]: entry
        for entry in spec["collections"]
        if entry["collection"] in WRITE_TARGETS
    }


def _select(connection, table, columns):
    sql = f"SELECT {', '.join(columns)} FROM {table}"
    with connection.cursor() as cursor:
        cursor.execute(sql)
        return cursor.fetchall()


def _load_collection(entry, rows, quarantine):
    fields = entry["fields"]
    documents = []
    ids = set()
    for row in rows:
        source_id = row[0]
        if source_id is None:
            quarantine.append(
                {
                    "collection": entry["collection"],
                    "source_key": None,
                    "reason": "null_key",
                }
            )
            continue
        doc = {"_id": source_id}
        for field, value in zip(fields, row[1:]):
            doc[field["target"]] = _convert(value, field["bson_type"])
        documents.append(doc)
        ids.add(source_id)
    return documents, ids


def _load_invoices(entry, invoice_rows, line_rows, quarantine):
    documents, ids = _load_collection(entry, invoice_rows, quarantine)
    child_fields = entry["embeds"][0]["child_fields"]
    lines_by_invoice = {}
    for row in line_rows:
        line_id, invoice_id = row[0], row[1]
        if line_id is None or invoice_id is None:
            quarantine.append(
                {"collection": "invoices", "source_key": line_id, "reason": "null_key"}
            )
            continue
        if invoice_id not in ids:
            quarantine.append(
                {
                    "collection": "invoices",
                    "source_key": line_id,
                    "reason": "orphan_line",
                }
            )
            continue
        line = {}
        for field, value in zip(child_fields, row):
            line[field["target"]] = _convert(value, field["bson_type"])
        lines_by_invoice.setdefault(invoice_id, []).append(line)
    for doc in documents:
        lines = lines_by_invoice.get(doc["_id"], [])
        lines.sort(key=lambda line: line["lineNo"] or 0)
        doc["lines"] = lines
    return documents


def main():
    parser = argparse.ArgumentParser(prog=UNIT)
    parser.add_argument("--source-dsn-secret", default="OW_BILLING_FIXTURE_DSN")
    parser.add_argument("--target-uri-secret", default="MONGO_LOCAL_URI")
    parser.add_argument(
        "--allowed-targets-file",
        default=str(REPO_ROOT / ".migration" / "allowed_targets.json"),
    )
    parser.add_argument(
        "--report-out",
        default=f"/tmp/recon/{UNIT}/load_report.json",
    )
    args = parser.parse_args()

    dsn = _secret(args.source_dsn_secret, json_expected=True)
    uri = _secret(args.target_uri_secret)
    _check_allowlist(args.allowed_targets_file)

    spec = _spec_collections()

    connection = oracledb.connect(
        user=dsn["user"], password=dsn["password"], dsn=dsn["dsn"]
    )
    try:
        source = {}
        quarantine = []
        documents = {}
        for name in WRITE_TARGETS:
            entry = spec[name]
            if name == "invoices":
                columns = [entry["key"]["source"][0]] + [
                    f["source"] for f in entry["fields"]
                ]
                invoice_rows = _select(connection, entry["root_table"], columns)
                embed = entry["embeds"][0]
                child_columns = [f["source"] for f in embed["child_fields"]]
                line_rows = _select(connection, embed["child_table"], child_columns)
                source["INVOICE_LINES"] = len(line_rows)
                documents[name] = _load_invoices(
                    entry, invoice_rows, line_rows, quarantine
                )
            else:
                columns = [entry["key"]["source"][0]] + [
                    f["source"] for f in entry["fields"]
                ]
                rows = _select(connection, entry["root_table"], columns)
                documents[name], _ = _load_collection(entry, rows, quarantine)
            source[entry["root_table"]] = len(
                invoice_rows if name == "invoices" else rows
            )
    finally:
        connection.close()

    client = MongoClient(uri)
    db = client[TARGET_DB]
    for name in WRITE_TARGETS:
        db.drop_collection(name)
    loaded = {}
    for name in WRITE_TARGETS:
        if documents[name]:
            db[name].insert_many(documents[name], ordered=False)
        loaded[name] = len(documents[name])

    report = {
        "unit": UNIT,
        "run_at": datetime.now(timezone.utc).isoformat(),
        "target_db": TARGET_DB,
        "loaded": loaded,
        "source_counts": source,
        "quarantine": quarantine,
        "quarantine_by_reason": dict(Counter(q["reason"] for q in quarantine)),
    }
    report_path = Path(args.report_out)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, default=str) + "\n")

    quarantine_note = ", ".join(
        f"{k}={v}" for k, v in report["quarantine_by_reason"].items()
    ) or "none"
    print(
        f"{UNIT}: loaded "
        + " ".join(f"{k}={v}" for k, v in loaded.items())
        + f" quarantine={len(quarantine)} ({quarantine_note})"
    )


if __name__ == "__main__":
    main()
