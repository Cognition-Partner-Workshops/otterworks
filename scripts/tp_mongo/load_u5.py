"""Load the Oracle U5 billing collections into MongoDB Atlas."""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path
from typing import Any

import oracledb
from bson import Decimal128, Int64
from pymongo import ASCENDING, DESCENDING, MongoClient

NS_VALUE = "mongo_205236"
TARGET_DB = "ow_tp_mongodb_205236"
UNIT_COLLECTIONS = (
    "subscriptions",
    "subscriptions_history",
    "usage_events",
    "rating_periods",
    "billing_invoices",
    "credit_notes",
    "dunning_attempts",
    "notifications",
    "billing_audit_log",
)

USAGE_EVENTS_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": [
            "_id",
            "id",
            "tenant_id",
            "occurred_at",
            "units",
            "kind_cd",
            "ns",
        ],
        "properties": {
            "units": {
                "bsonType": "long",
                "minimum": 1,
                "description": "units must be > 0 (TRG_USAGE_EVENTS_CHECK)",
            },
            "kind_cd": {"bsonType": "int"},
            "occurred_at": {"bsonType": "date"},
            "tenant_id": {"bsonType": "string"},
            "ns": {"enum": ["mongo_205236"]},
        },
    }
}
TTL_SECONDS = 7776000
STAGING_SUFFIX = "__staging"

QUERIES = {
    "subscriptions": (
        "SELECT ID, TENANT_ID, PLAN_ID, STARTS_ON, ENDS_ON, STATUS_CD, "
        "SUSPENDED_ON FROM SUBSCRIPTIONS ORDER BY ID"
    ),
    "subscriptions_history": (
        "SELECT HIST_ID, HIST_DT, HIST_OP, ID, TENANT_ID, PLAN_ID, STARTS_ON, "
        "ENDS_ON, STATUS_CD, SUSPENDED_ON FROM SUBSCRIPTIONS_HIST ORDER BY HIST_ID"
    ),
    "usage_events": (
        "SELECT ID, TENANT_ID, OCCURRED_AT, UNITS, KIND_CD FROM USAGE_EVENTS "
        "ORDER BY ID"
    ),
    "rating_periods": (
        "SELECT ID, TENANT_ID, PERIOD_START, PERIOD_END FROM RATING_PERIODS "
        "ORDER BY ID"
    ),
    "rating_results": (
        "SELECT ID, PERIOD_ID, SUBSCRIPTION_ID, USED_UNITS, QUOTA_UNITS, "
        "ROLLOVER_UNITS, BILLABLE_UNITS, OVERAGE_AMOUNT, CREATED_AT "
        "FROM RATING_RESULTS ORDER BY ID"
    ),
    "billing_invoices": (
        "SELECT ID, TENANT_ID, PERIOD_ID, ISSUED_AT, SUBTOTAL, TAX, TOTAL, "
        "STATUS_CD FROM INVOICES ORDER BY ID"
    ),
    "invoice_lines": (
        "SELECT ID, INVOICE_ID, LINE_NO, LINE_TYPE, DESCRIPTION, AMOUNT "
        "FROM INVOICE_LINES ORDER BY ID"
    ),
    "credit_notes": (
        "SELECT ID, TENANT_ID, ISSUED_ON, AMOUNT, REMAINING_AMOUNT "
        "FROM CREDIT_NOTES ORDER BY ID"
    ),
    "dunning_attempts": (
        "SELECT ID, TENANT_ID, INVOICE_ID, ATTEMPT_NO, SCHEDULED_FOR, STATUS_CD "
        "FROM DUNNING_ATTEMPTS ORDER BY ID"
    ),
    "notifications": (
        "SELECT ID, TENANT_ID, KIND_CD, SENT_AT FROM NOTIFICATIONS ORDER BY ID"
    ),
    "billing_audit_log": (
        "SELECT LOG_ID, LOGGED_AT, MODULE, MESSAGE FROM BILLING_AUDIT_LOG "
        "ORDER BY LOG_ID"
    ),
}

ROOT_TABLES = {
    "subscriptions": "SUBSCRIPTIONS",
    "subscriptions_history": "SUBSCRIPTIONS_HIST",
    "usage_events": "USAGE_EVENTS",
    "rating_periods": "RATING_PERIODS",
    "billing_invoices": "INVOICES",
    "credit_notes": "CREDIT_NOTES",
    "dunning_attempts": "DUNNING_ATTEMPTS",
    "notifications": "NOTIFICATIONS",
    "billing_audit_log": "BILLING_AUDIT_LOG",
}


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


def lng(value: Any) -> Int64 | None:
    if value is None:
        return None
    return Int64(value)


def dec(value: Any, scale: int) -> Decimal128 | None:
    if value is None:
        return None
    quantizer = Decimal(1).scaleb(-scale)
    rounded = Decimal(str(value)).quantize(quantizer, rounding=ROUND_HALF_EVEN)
    return Decimal128(rounded)


def ts(value: Any) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value.replace(microsecond=value.microsecond - value.microsecond % 1000)


def transform_subscriptions(row: Mapping[str, Any]) -> dict[str, Any]:
    identifier = vc(row["ID"])
    return {
        "_id": identifier,
        "id": identifier,
        "tenant_id": vc(row["TENANT_ID"]),
        "plan_id": vc(row["PLAN_ID"]),
        "starts_on": ts(row["STARTS_ON"]),
        "ends_on": ts(row["ENDS_ON"]),
        "status_cd": i32(row["STATUS_CD"]),
        "suspended_on": ts(row["SUSPENDED_ON"]),
        "ns": NS_VALUE,
    }


def transform_subscriptions_history(row: Mapping[str, Any]) -> dict[str, Any]:
    identifier = lng(row["HIST_ID"])
    return {
        "_id": identifier,
        "hist_id": identifier,
        "hist_dt": vc(row["HIST_DT"]),
        "hist_op": vc(row["HIST_OP"]),
        "id": vc(row["ID"]),
        "tenant_id": vc(row["TENANT_ID"]),
        "plan_id": vc(row["PLAN_ID"]),
        "starts_on": ts(row["STARTS_ON"]),
        "ends_on": ts(row["ENDS_ON"]),
        "status_cd": i32(row["STATUS_CD"]),
        "suspended_on": ts(row["SUSPENDED_ON"]),
        "ns": NS_VALUE,
    }


def transform_usage_events(row: Mapping[str, Any]) -> dict[str, Any]:
    identifier = vc(row["ID"])
    return {
        "_id": identifier,
        "id": identifier,
        "tenant_id": vc(row["TENANT_ID"]),
        "occurred_at": ts(row["OCCURRED_AT"]),
        "units": lng(row["UNITS"]),
        "kind_cd": i32(row["KIND_CD"]),
        "ns": NS_VALUE,
    }


def transform_rating_result(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": vc(row["ID"]),
        "period_id": vc(row["PERIOD_ID"]),
        "subscription_id": vc(row["SUBSCRIPTION_ID"]),
        "used_units": lng(row["USED_UNITS"]),
        "quota_units": lng(row["QUOTA_UNITS"]),
        "rollover_units": lng(row["ROLLOVER_UNITS"]),
        "billable_units": lng(row["BILLABLE_UNITS"]),
        "overage_amount": dec(row["OVERAGE_AMOUNT"], 2),
        "created_at": ts(row["CREATED_AT"]),
    }


def transform_rating_period(
    row: Mapping[str, Any], results: list[Mapping[str, Any]]
) -> dict[str, Any]:
    identifier = vc(row["ID"])
    return {
        "_id": identifier,
        "id": identifier,
        "tenant_id": vc(row["TENANT_ID"]),
        "period_start": ts(row["PERIOD_START"]),
        "period_end": ts(row["PERIOD_END"]),
        "results": [
            transform_rating_result(child)
            for child in sorted(results, key=lambda item: vc(item["ID"]) or "")
        ],
        "ns": NS_VALUE,
    }


def transform_invoice_line(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": vc(row["ID"]),
        "invoice_id": vc(row["INVOICE_ID"]),
        "line_no": i32(row["LINE_NO"]),
        "line_type": vc(row["LINE_TYPE"]),
        "description": vc(row["DESCRIPTION"]),
        "amount": dec(row["AMOUNT"], 2),
    }


def transform_billing_invoice(
    row: Mapping[str, Any], lines: list[Mapping[str, Any]]
) -> dict[str, Any]:
    identifier = vc(row["ID"])
    return {
        "_id": identifier,
        "id": identifier,
        "tenant_id": vc(row["TENANT_ID"]),
        "period_id": vc(row["PERIOD_ID"]),
        "issued_at": ts(row["ISSUED_AT"]),
        "subtotal": dec(row["SUBTOTAL"], 2),
        "tax": dec(row["TAX"], 2),
        "total": dec(row["TOTAL"], 2),
        "status_cd": i32(row["STATUS_CD"]),
        "lines": [
            transform_invoice_line(child)
            for child in sorted(
                lines, key=lambda item: (i32(item["LINE_NO"]), vc(item["ID"]) or "")
            )
        ],
        "ns": NS_VALUE,
    }


def transform_credit_notes(row: Mapping[str, Any]) -> dict[str, Any]:
    identifier = vc(row["ID"])
    return {
        "_id": identifier,
        "id": identifier,
        "tenant_id": vc(row["TENANT_ID"]),
        "issued_on": ts(row["ISSUED_ON"]),
        "amount": dec(row["AMOUNT"], 2),
        "remaining_amount": dec(row["REMAINING_AMOUNT"], 2),
        "ns": NS_VALUE,
    }


def transform_dunning_attempts(row: Mapping[str, Any]) -> dict[str, Any]:
    identifier = vc(row["ID"])
    return {
        "_id": identifier,
        "id": identifier,
        "tenant_id": vc(row["TENANT_ID"]),
        "invoice_id": vc(row["INVOICE_ID"]),
        "attempt_no": i32(row["ATTEMPT_NO"]),
        "scheduled_for": ts(row["SCHEDULED_FOR"]),
        "status_cd": i32(row["STATUS_CD"]),
        "ns": NS_VALUE,
    }


def transform_notifications(row: Mapping[str, Any]) -> dict[str, Any]:
    identifier = vc(row["ID"])
    return {
        "_id": identifier,
        "id": identifier,
        "tenant_id": vc(row["TENANT_ID"]),
        "kind_cd": i32(row["KIND_CD"]),
        "sent_at": ts(row["SENT_AT"]),
        "ns": NS_VALUE,
    }


def transform_billing_audit_log(row: Mapping[str, Any]) -> dict[str, Any]:
    identifier = lng(row["LOG_ID"])
    return {
        "_id": identifier,
        "log_id": identifier,
        "logged_at": ts(row["LOGGED_AT"]),
        "module": vc(row["MODULE"]),
        "message": vc(row["MESSAGE"]),
        "ns": NS_VALUE,
    }


TRANSFORMERS = {
    "subscriptions": transform_subscriptions,
    "subscriptions_history": transform_subscriptions_history,
    "usage_events": transform_usage_events,
    "credit_notes": transform_credit_notes,
    "dunning_attempts": transform_dunning_attempts,
    "notifications": transform_notifications,
    "billing_audit_log": transform_billing_audit_log,
}

INDEXES = {
    "subscriptions": ([("tenant_id", ASCENDING), ("starts_on", DESCENDING)], {}),
    "subscriptions_history": ([], {}),
    "usage_events": ([("tenant_id", ASCENDING), ("occurred_at", ASCENDING)], {}),
    "rating_periods": (
        [("tenant_id", ASCENDING), ("period_start", ASCENDING)],
        {"unique": True},
    ),
    "billing_invoices": (
        [("tenant_id", ASCENDING), ("issued_at", ASCENDING)],
        {},
    ),
    "credit_notes": (
        [
            ("tenant_id", ASCENDING),
            ("issued_on", ASCENDING),
            ("_id", ASCENDING),
        ],
        {},
    ),
    "dunning_attempts": (
        [("invoice_id", ASCENDING), ("attempt_no", ASCENDING)],
        {"unique": True},
    ),
    "notifications": (
        [
            ("tenant_id", ASCENDING),
            ("kind_cd", ASCENDING),
            ("sent_at", ASCENDING),
        ],
        {"unique": True},
    ),
    "billing_audit_log": (
        [("logged_at", ASCENDING)],
        {"expireAfterSeconds": TTL_SECONDS},
    ),
}


def validate_target_db(target_db: str) -> None:
    if target_db != TARGET_DB:
        raise ValueError(f"--target-db must be {TARGET_DB!r}, got {target_db!r}")


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


def extract_rows(connection: Any, collection: str) -> list[dict[str, Any]]:
    cursor = connection.cursor()
    cursor.arraysize = 5000
    cursor.execute(QUERIES[collection])
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def build_rating_periods(
    rows: list[Mapping[str, Any]], result_rows: list[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    by_parent: dict[str | None, list[Mapping[str, Any]]] = defaultdict(list)
    parent_ids = {vc(row["ID"]) for row in rows}
    for child in result_rows:
        parent_id = vc(child["PERIOD_ID"])
        if parent_id not in parent_ids:
            raise RuntimeError(
                f"RATING_RESULTS row {vc(child['ID'])!r} has no RATING_PERIODS parent"
            )
        by_parent[parent_id].append(child)
    return [
        transform_rating_period(row, by_parent.get(vc(row["ID"]), []))
        for row in rows
    ]


def build_billing_invoices(
    rows: list[Mapping[str, Any]], line_rows: list[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    by_parent: dict[str | None, list[Mapping[str, Any]]] = defaultdict(list)
    parent_ids = {vc(row["ID"]) for row in rows}
    for child in line_rows:
        parent_id = vc(child["INVOICE_ID"])
        if parent_id not in parent_ids:
            raise RuntimeError(
                f"INVOICE_LINES row {vc(child['ID'])!r} has no INVOICES parent"
            )
        by_parent[parent_id].append(child)
    return [
        transform_billing_invoice(row, by_parent.get(vc(row["ID"]), []))
        for row in rows
    ]


def _documents(
    collection: str,
    rows: list[Mapping[str, Any]],
    children: list[Mapping[str, Any]] | None,
) -> tuple[list[dict[str, Any]], dict[str, int] | None]:
    if collection == "rating_periods":
        child_rows = children or []
        documents = build_rating_periods(rows, child_rows)
        count = sum(len(document["results"]) for document in documents)
        if count != len(child_rows):
            raise RuntimeError(
                f"rating_periods: embedded results {count} != source rows {len(child_rows)}"
            )
        return documents, {"results": count}
    if collection == "billing_invoices":
        child_rows = children or []
        documents = build_billing_invoices(rows, child_rows)
        count = sum(len(document["lines"]) for document in documents)
        if count != len(child_rows):
            raise RuntimeError(
                f"billing_invoices: embedded lines {count} != source rows {len(child_rows)}"
            )
        return documents, {"lines": count}
    return [TRANSFORMERS[collection](row) for row in rows], None


def load_collection(
    database: Any,
    collection: str,
    rows: list[Mapping[str, Any]],
    children: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    if collection not in UNIT_COLLECTIONS:
        raise ValueError(f"collection is not owned by U5: {collection!r}")
    documents, embedded = _documents(collection, rows, children)
    staging = f"{collection}{STAGING_SUFFIX}"
    assert staging.endswith("__staging")
    options = {"validator": USAGE_EVENTS_VALIDATOR, "validationLevel": "strict",
               "validationAction": "error"} if collection == "usage_events" else {}
    database.drop_collection(staging)
    try:
        database.create_collection(staging, **options)
        if documents:
            database[staging].insert_many(documents, ordered=True)

        index_names: list[str] = []
        keys, index_options = INDEXES[collection]
        if keys:
            index_names.append(
                database[staging].create_index(keys, **index_options)
            )
        if collection == "billing_invoices":
            index_names.append(
                database[staging].create_index(
                    [("status_cd", ASCENDING), ("issued_at", ASCENDING)]
                )
            )

        docs_after = database[staging].count_documents({})
        ns_docs_after = database[staging].count_documents({"ns": NS_VALUE})
        if docs_after != len(rows) or ns_docs_after != len(rows):
            raise RuntimeError(
                f"{collection}: expected {len(rows)} rows, got "
                f"{docs_after} documents and {ns_docs_after} namespaced documents"
            )
        database[staging].rename(collection, dropTarget=True)
        if staging in database.list_collection_names():
            raise RuntimeError(f"{collection}: staging collection remains after rename")
    except Exception:
        database.drop_collection(staging)
        raise
    report = {
        "root_table": ROOT_TABLES[collection],
        "dropped": True,
        "recreated": True,
        "source_rows": len(rows),
        "inserted": len(documents),
        "docs_after": docs_after,
        "ns_docs_after": ns_docs_after,
        "indexes": index_names,
    }
    if embedded is not None:
        report["embedded"] = embedded
    return report


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn-secret", default="OW_BILLING_FIXTURE_DSN")
    parser.add_argument("--uri-secret", default="MONGODB_ATLAS_URI")
    parser.add_argument("--target-db", default=TARGET_DB)
    parser.add_argument("--report", default=".migration/recon/U5/load_report.json")
    args = parser.parse_args(argv)
    try:
        validate_target_db(args.target_db)
    except ValueError as exc:
        parser.error(str(exc))
    return args


def run(args: argparse.Namespace) -> dict[str, Any]:
    started_at = utc_now()
    validate_target_db(args.target_db)
    user, password, dsn = parse_dsn(secret_value(args.dsn_secret))
    uri = secret_value(args.uri_secret)

    with oracledb.connect(user=user, password=password, dsn=dsn) as oracle:
        source = {
            collection: extract_rows(oracle, collection)
            for collection in (
                "subscriptions",
                "subscriptions_history",
                "usage_events",
                "rating_periods",
                "rating_results",
                "billing_invoices",
                "invoice_lines",
                "credit_notes",
                "dunning_attempts",
                "notifications",
                "billing_audit_log",
            )
        }

    client = MongoClient(uri)
    try:
        database = client[args.target_db]
        collections = {}
        for collection in UNIT_COLLECTIONS:
            children = None
            if collection == "rating_periods":
                children = source["rating_results"]
            elif collection == "billing_invoices":
                children = source["invoice_lines"]
            collections[collection] = load_collection(
                database, collection, source[collection], children
            )
    finally:
        client.close()

    report = {
        "unit": "U5",
        "started_at": started_at,
        "finished_at": utc_now(),
        "generated_at": utc_now(),
        "target_db": args.target_db,
        "ns": NS_VALUE,
        "collections": collections,
        "validators": {"usage_events": USAGE_EVENTS_VALIDATOR},
        "ttl_indexes": {"billing_audit_log": {"logged_at": TTL_SECONDS}},
        "secret_names": {"dsn": args.dsn_secret, "uri": args.uri_secret},
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run(args)
    summary = ", ".join(
        f"{collection}={details['inserted']}"
        for collection, details in report["collections"].items()
    )
    print(f"U5 load complete: target_db={TARGET_DB} ns={NS_VALUE} {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
