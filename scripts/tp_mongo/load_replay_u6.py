"""Load the U6 replay clone into prefixed MongoDB collections."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import oracledb
from bson import Int64
from pymongo import ASCENDING, MongoClient

import load_u0
import load_u5

NS_VALUE = load_u0.NS_VALUE
TARGET_DB = load_u0.TARGET_DB
PREFIX = "replay_u6_"
STAGING_SUFFIX = load_u5.STAGING_SUFFIX
U0_COLLECTIONS = load_u0.UNIT_COLLECTIONS
U5_COLLECTIONS = load_u5.UNIT_COLLECTIONS
UNIT_COLLECTIONS = U0_COLLECTIONS + U5_COLLECTIONS
SEQUENCE_QUERY = (
    "SELECT sequence_name, last_number "
    "FROM user_sequences "
    "WHERE sequence_name IN ('SEQ_BILLING_AUDIT_LOG','SEQ_SUBSCRIPTIONS_HIST')"
)


def validate_target_db(target_db: str) -> None:
    if target_db != TARGET_DB:
        raise ValueError(f"--target-db must be {TARGET_DB!r}, got {target_db!r}")


def collection_name(name: str, staging: bool = False) -> str:
    value = f"{PREFIX}{name}"
    return f"{value}{STAGING_SUFFIX}" if staging else value


def _assert_owned(name: str) -> None:
    if not name.startswith(PREFIX):
        raise AssertionError(f"U6 replay loader attempted unprefixed collection: {name}")


def _u0_documents(collection: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [load_u0.TRANSFORMERS[collection](row) for row in rows]


def _documents(
    collection: str,
    rows: list[dict[str, Any]],
    source: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, int] | None]:
    if collection in U0_COLLECTIONS:
        return _u0_documents(collection, rows), None
    children = None
    if collection == "rating_periods":
        children = source["rating_results"]
    elif collection == "billing_invoices":
        children = source["invoice_lines"]
    return load_u5._documents(collection, rows, children)


def _create_index(database: Any, collection: str) -> list[str]:
    index_names: list[str] = []
    if collection == "codes":
        index_names.append(
            database[collection].create_index(
                [("code_type", ASCENDING), ("code_val", ASCENDING)],
                unique=True,
            )
        )
    elif collection in load_u5.INDEXES:
        keys, options = load_u5.INDEXES[collection]
        if keys:
            index_names.append(database[collection].create_index(keys, **options))
        if collection == "billing_invoices":
            index_names.append(
                database[collection].create_index(
                    [("status_cd", ASCENDING), ("issued_at", ASCENDING)]
                )
            )
    return index_names


def load_collection(
    database: Any,
    collection: str,
    rows: list[dict[str, Any]],
    source: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    if collection not in UNIT_COLLECTIONS:
        raise ValueError(f"collection is not owned by U6: {collection!r}")
    target = collection_name(collection)
    staging = collection_name(collection, staging=True)
    _assert_owned(target)
    _assert_owned(staging)
    documents, embedded = _documents(collection, rows, source)
    options = (
        {
            "validator": load_u5.USAGE_EVENTS_VALIDATOR,
            "validationLevel": "strict",
            "validationAction": "error",
        }
        if collection == "usage_events"
        else {}
    )
    database.drop_collection(staging)
    try:
        database.create_collection(staging, **options)
        if documents:
            database[staging].insert_many(documents, ordered=True)
        index_names = _create_index(database, staging)
        docs_after = database[staging].count_documents({})
        ns_docs_after = database[staging].count_documents({"ns": NS_VALUE})
        if docs_after != len(rows) or ns_docs_after != len(rows):
            raise RuntimeError(
                f"{collection}: expected {len(rows)} rows, got "
                f"{docs_after} documents and {ns_docs_after} namespaced documents"
            )
        database[staging].rename(target, dropTarget=True)
        if staging in database.list_collection_names():
            raise RuntimeError(f"{collection}: staging collection remains after rename")
    except Exception:
        database.drop_collection(staging)
        raise
    report = {
        "root_table": (
            load_u0.ROOT_TABLES[collection]
            if collection in U0_COLLECTIONS
            else load_u5.ROOT_TABLES[collection]
        ),
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


def _extract_sequences(connection: Any) -> dict[str, Int64]:
    cursor = connection.cursor()
    cursor.execute(SEQUENCE_QUERY)
    columns = [description[0].lower() for description in cursor.description]
    return {
        row[columns.index("sequence_name")].lower(): Int64(
            row[columns.index("last_number")]
        )
        for row in cursor.fetchall()
    }


def seed_counters(database: Any, sequences: dict[str, Int64]) -> dict[str, Any]:
    name = collection_name("counters")
    _assert_owned(name)
    database.drop_collection(name)
    database.create_collection(name)
    seeds = {}
    for sequence in ("seq_billing_audit_log", "seq_subscriptions_hist"):
        if sequence not in sequences:
            raise LookupError(f"Oracle sequence {sequence!r} was not found")
        seeds[sequence] = {
            "_id": sequence,
            "seq": Int64(sequences[sequence] - 1),
        }
    database[name].insert_many(list(seeds.values()), ordered=True)
    return seeds


def utc_now() -> str:
    return load_u5.utc_now()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn-secret", default="OW_BILLING_FIXTURE_DSN")
    parser.add_argument("--uri-secret", default="MONGODB_ATLAS_URI")
    parser.add_argument("--target-db", default=TARGET_DB)
    parser.add_argument("--report", default=".migration/recon/U6/load_report.json")
    args = parser.parse_args(argv)
    try:
        validate_target_db(args.target_db)
    except ValueError as exc:
        parser.error(str(exc))
    return args


def run(args: argparse.Namespace) -> dict[str, Any]:
    started_at = utc_now()
    validate_target_db(args.target_db)
    user, password, dsn = load_u5.parse_dsn(load_u5.secret_value(args.dsn_secret))
    uri = load_u5.secret_value(args.uri_secret)
    with oracledb.connect(user=user, password=password, dsn=dsn) as oracle:
        source = {
            collection: load_u0.extract_rows(oracle, collection)
            for collection in U0_COLLECTIONS
        }
        source.update(
            {
                collection: load_u5.extract_rows(oracle, collection)
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
        )
        sequences = _extract_sequences(oracle)

    client = MongoClient(uri)
    try:
        database = client[args.target_db]
        collections = {
            collection: load_collection(
                database, collection, source[collection], source
            )
            for collection in UNIT_COLLECTIONS
        }
        counters = seed_counters(database, sequences)
    finally:
        client.close()

    report = {
        "unit": "U6",
        "started_at": started_at,
        "finished_at": utc_now(),
        "generated_at": utc_now(),
        "target_db": args.target_db,
        "ns": NS_VALUE,
        "prefix": PREFIX,
        "collections": {
            collection_name(collection): details
            for collection, details in collections.items()
        },
        "counter_seeds": counters,
        "secret_names": {"dsn": args.dsn_secret, "uri": args.uri_secret},
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, default=str) + "\n")
    return report


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run(args)
    summary = ", ".join(
        f"{collection}={details['inserted']}"
        for collection, details in report["collections"].items()
    )
    print(f"U6 replay load complete: target_db={TARGET_DB} prefix={PREFIX}{summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
