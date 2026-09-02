"""Load the Oracle U2 invoice feed into MongoDB Atlas."""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path
from typing import Any

import oracledb
from bson import Decimal128
from pymongo import ASCENDING, MongoClient

oracledb.defaults.fetch_decimals = True

NS_VALUE = "mongo_205236"
TARGET_DB = "ow_tp_mongodb_205236"
QUARANTINE_DB = "ow_tp_mongodb_205236_quarantine"
TARGET_COLLECTION = "invoices"
QUARANTINE_COLLECTION = "invoice_feed_orphan_lines"
BATCH_SIZE = 1000
LINE_ARRAYSIZE = 5000

HEADER_QUERY = """
SELECT invoice_id, invoice_no, cust_id, tenant_id, invoice_dt, due_dt,
       status_cd, total_amt, batch_no
  FROM invoice_header
 WHERE batch_no = :b
 ORDER BY invoice_id
"""
LINE_QUERY = """
SELECT line_id, invoice_no, invoice_id, cust_id, cust_no, cust_name, tenant_id,
       line_no, line_type_cd, item_desc, qty, unit_price, amount, tax_amt,
       invoice_dt, service_period, posted_yn, gl_acct_csv, batch_no, src_system
  FROM invoice_line
 WHERE batch_no = :b
 ORDER BY invoice_id, line_no, line_id
"""

LINE_FIELDS = (
    "line_id",
    "invoice_no",
    "invoice_id",
    "cust_id",
    "cust_no",
    "cust_name",
    "tenant_id",
    "line_no",
    "line_type_cd",
    "item_desc",
    "qty",
    "unit_price",
    "amount",
    "tax_amt",
    "invoice_dt",
    "service_period",
    "posted_yn",
    "gl_acct_csv",
    "batch_no",
    "src_system",
)


def vc(value: Any) -> str | None:
    if value is None:
        return None
    value = str(value)
    return value if value else None


def ch(value: Any) -> str | None:
    if value is None:
        return None
    value = str(value).rstrip(" ")
    return value if value else None


def i32(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def dec(value: Any, scale: int) -> Decimal128 | None:
    if value is None:
        return None
    quantizer = Decimal(1).scaleb(-scale)
    rounded = Decimal(str(value)).quantize(quantizer, rounding=ROUND_HALF_EVEN)
    return Decimal128(rounded)


def parse_date(value: Any) -> datetime | None:
    value = vc(value)
    if value is None:
        return None
    try:
        return datetime.strptime(value.upper(), "%d-%b-%y").replace(
            tzinfo=timezone.utc
        )
    except (TypeError, ValueError):
        return None


def gl_accounts(value: Any) -> list[str]:
    value = vc(value)
    if value is None:
        return []
    return [item.strip() for item in value.split(",")]


def build_line_elem(row: Mapping[str, Any]) -> dict[str, Any]:
    line = {
        "line_id": vc(row["LINE_ID"]),
        "invoice_no": vc(row["INVOICE_NO"]),
        "invoice_id": vc(row["INVOICE_ID"]),
        "cust_id": vc(row["CUST_ID"]),
        "cust_no": vc(row["CUST_NO"]),
        "cust_name": vc(row["CUST_NAME"]),
        "tenant_id": vc(row["TENANT_ID"]),
        "line_no": i32(row["LINE_NO"]),
        "line_type_cd": i32(row["LINE_TYPE_CD"]),
        "item_desc": vc(row["ITEM_DESC"]),
        "qty": dec(row["QTY"], 3),
        "unit_price": dec(row["UNIT_PRICE"], 4),
        "amount": dec(row["AMOUNT"], 2),
        "tax_amt": dec(row["TAX_AMT"], 2),
        "invoice_dt": vc(row["INVOICE_DT"]),
        "service_period": vc(row["SERVICE_PERIOD"]),
        "posted_yn": ch(row["POSTED_YN"]),
        "gl_acct_csv": vc(row["GL_ACCT_CSV"]),
        "batch_no": i32(row["BATCH_NO"]),
        "src_system": vc(row["SRC_SYSTEM"]),
    }
    line["gl_accounts"] = gl_accounts(row["GL_ACCT_CSV"])
    return line


def build_invoice_doc(
    row: Mapping[str, Any], lines: Iterable[Mapping[str, Any]] = ()
) -> dict[str, Any]:
    invoice_id = vc(row["INVOICE_ID"])
    return {
        "_id": invoice_id,
        "invoice_id": invoice_id,
        "invoice_no": vc(row["INVOICE_NO"]),
        "cust_id": vc(row["CUST_ID"]),
        "tenant_id": vc(row["TENANT_ID"]),
        "invoice_dt": vc(row["INVOICE_DT"]),
        "due_dt": vc(row["DUE_DT"]),
        "status_cd": i32(row["STATUS_CD"]),
        "total_amt": dec(row["TOTAL_AMT"], 2),
        "batch_no": i32(row["BATCH_NO"]),
        "ns": NS_VALUE,
        "invoice_date": parse_date(row["INVOICE_DT"]),
        "due_date": parse_date(row["DUE_DT"]),
        "lines": [build_line_elem(line) for line in lines],
    }


def quarantine_line(row: Mapping[str, Any]) -> dict[str, Any]:
    line = build_line_elem(row)
    line.pop("gl_accounts")
    return {
        "_id": line["line_id"],
        "ns": NS_VALUE,
        "unit": "U2",
        "source_table": "OW_BILLING.INVOICE_LINE",
        "reason_class": "orphan_parent",
        "reason": "invoice_id has no INVOICE_HEADER row in batch",
        "batch_no": line["batch_no"],
        "invoice_id": line["invoice_id"],
        "row": line,
        "quarantined_at": datetime.now(timezone.utc),
    }


def partition_lines(
    rows: Iterable[Mapping[str, Any]], invoice_ids: set[str | None]
) -> tuple[dict[str, list[Mapping[str, Any]]], list[dict[str, Any]], int]:
    embedded: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    quarantined: list[dict[str, Any]] = []
    total = 0
    for row in rows:
        total += 1
        invoice_id = vc(row["INVOICE_ID"])
        if invoice_id in invoice_ids and invoice_id is not None:
            embedded[invoice_id].append(row)
        else:
            quarantined.append(quarantine_line(row))
    for invoice_lines in embedded.values():
        invoice_lines.sort(
            key=lambda line: (
                i32(line["LINE_NO"]) is None,
                i32(line["LINE_NO"]) or 0,
                vc(line["LINE_ID"]) or "",
            )
        )
    return embedded, quarantined, total


def validate_target_db(target_db: str) -> None:
    if target_db != TARGET_DB:
        raise ValueError(f"--target-db must be {TARGET_DB!r}, got {target_db!r}")


def validate_quarantine_db(quarantine_db: str) -> None:
    if quarantine_db != QUARANTINE_DB:
        raise ValueError(
            f"--quarantine-db must be {QUARANTINE_DB!r}, got {quarantine_db!r}"
        )


def secret_value(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"required secret environment variable is missing: {name}")
    return value


def parse_dsn(value: str) -> tuple[str, str, str]:
    try:
        user, password, dsn = value.split("/", 2)
    except ValueError as exc:
        raise ValueError("DSN secret must have the form user/password/dsn") from exc
    if not user or not password or not dsn:
        raise ValueError("DSN secret must have the form user/password/dsn")
    return user, password, dsn


def _rows_from_cursor(cursor: Any) -> Iterable[dict[str, Any]]:
    columns = [description.name for description in cursor.description]
    while True:
        rows = cursor.fetchmany(LINE_ARRAYSIZE)
        if not rows:
            return
        yield from (dict(zip(columns, row)) for row in rows)


def extract_headers(connection: Any, batch_no: int) -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        cursor.arraysize = LINE_ARRAYSIZE
        cursor.execute(HEADER_QUERY, {"b": batch_no})
        return list(_rows_from_cursor(cursor))


def extract_lines(connection: Any, batch_no: int) -> Iterable[dict[str, Any]]:
    cursor = connection.cursor()
    cursor.arraysize = LINE_ARRAYSIZE
    cursor.execute(LINE_QUERY, {"b": batch_no})
    try:
        yield from _rows_from_cursor(cursor)
    finally:
        cursor.close()


def _insert_batches(collection: Any, documents: list[Mapping[str, Any]]) -> int:
    for start in range(0, len(documents), BATCH_SIZE):
        collection.insert_many(documents[start : start + BATCH_SIZE], ordered=False)
    return len(documents)


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-no", type=int, default=85559852)
    parser.add_argument("--dsn-secret", default="OW_BILLING_FIXTURE_DSN")
    parser.add_argument("--uri-secret", default="MONGODB_ATLAS_URI")
    parser.add_argument("--target-db", default=TARGET_DB)
    parser.add_argument("--quarantine-db", default=QUARANTINE_DB)
    parser.add_argument("--report-out", default=".migration/recon/U2/load_report.json")
    args = parser.parse_args(argv)
    try:
        validate_target_db(args.target_db)
        validate_quarantine_db(args.quarantine_db)
    except ValueError as exc:
        parser.error(str(exc))
    return args


def run(args: argparse.Namespace) -> dict[str, Any]:
    started = time.monotonic()
    validate_target_db(args.target_db)
    validate_quarantine_db(args.quarantine_db)
    dsn = secret_value(args.dsn_secret)
    uri = secret_value(args.uri_secret)
    user, password, source_dsn = parse_dsn(dsn)

    with oracledb.connect(user=user, password=password, dsn=source_dsn) as connection:
        headers = extract_headers(connection, args.batch_no)
        header_ids = {vc(row["INVOICE_ID"]) for row in headers}
        line_rows = extract_lines(connection, args.batch_no)
        lines_by_invoice, quarantined, line_count = partition_lines(
            line_rows, header_ids
        )

    documents = [
        build_invoice_doc(row, lines_by_invoice.get(vc(row["INVOICE_ID"]), ()))
        for row in headers
    ]
    embedded_count = sum(len(document["lines"]) for document in documents)
    if not headers:
        raise RuntimeError(
            f"INVOICE_HEADER has no rows for batch_no={args.batch_no}; "
            "refusing to replace the target collections"
        )
    if len(documents) != len(headers) or embedded_count + len(quarantined) != line_count:
        raise RuntimeError("source/load mismatch for invoice headers or lines")

    client = MongoClient(uri)
    try:
        database = client[args.target_db]
        quarantine_database = client[args.quarantine_db]
        database.drop_collection(TARGET_COLLECTION)
        quarantine_database.drop_collection(QUARANTINE_COLLECTION)
        database.create_collection(TARGET_COLLECTION)
        quarantine_database.create_collection(QUARANTINE_COLLECTION)
        inserted = _insert_batches(database[TARGET_COLLECTION], documents)
        quarantine_inserted = _insert_batches(
            quarantine_database[QUARANTINE_COLLECTION], quarantined
        )
        indexes = [
            database[TARGET_COLLECTION].create_index(
                [("batch_no", ASCENDING), ("status_cd", ASCENDING)]
            ),
            database[TARGET_COLLECTION].create_index([("cust_id", ASCENDING)]),
            database[TARGET_COLLECTION].create_index(
                [("lines.line_id", ASCENDING)]
            ),
        ]
    finally:
        client.close()

    report = {
        "unit": "U2",
        "batch_no": args.batch_no,
        "target_db": args.target_db,
        "quarantine_db": args.quarantine_db,
        "collections": {
            TARGET_COLLECTION: {"dropped": True, "inserted": inserted},
            QUARANTINE_COLLECTION: {
                "dropped": True,
                "inserted": quarantine_inserted,
            },
        },
        "source_counts": {
            "invoice_header": len(headers),
            "invoice_line": line_count,
        },
        "embedded_lines": embedded_count,
        "quarantined_lines": len(quarantined),
        "quarantined_line_ids": sorted(item["_id"] for item in quarantined),
        "max_lines_per_invoice": max((len(doc["lines"]) for doc in documents), default=0),
        "indexes": indexes,
        "loaded_at": utc_now(),
        "duration_s": round(time.monotonic() - started, 3),
    }
    report_path = Path(args.report_out)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, default=_json_default) + "\n"
    )
    return report


def main(argv: list[str] | None = None) -> int:
    report = run(parse_args(argv))
    print(
        "U2 load complete: "
        f"target_db={report['target_db']} ns={NS_VALUE} "
        f"invoices={report['collections'][TARGET_COLLECTION]['inserted']} "
        f"embedded_lines={report['embedded_lines']} "
        f"quarantined_lines={report['quarantined_lines']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
