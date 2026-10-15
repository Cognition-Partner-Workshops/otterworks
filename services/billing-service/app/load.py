"""Load the billing_migration collections from the legacy PostgreSQL. Secrets are passed
by environment variable NAME only; `--collections` restricts the run to a batch's write
targets (every collection by default, for the disposable parity stack's reset).

    python -m app.load --source-dsn-secret POSTGRESQL_RO_DSN --target-uri-secret MONGODB_ATLAS_URI \
        --collections usageEvents,ratingPeriods
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from typing import Any

from pymongo import MongoClient
from pymongo.database import Database

from app.documents import (
    COLLECTIONS,
    INDEXES,
    VALIDATORS,
    plan_document,
    rating_period_document,
    subscription_document,
    tenant_document,
    usage_event_document,
)

SOURCE_TABLES: dict[str, tuple[str, ...]] = {
    "plans": ("plans",),
    "tenants": ("tenants", "credit_notes"),
    "subscriptions": ("subscriptions",),
    "usageEvents": ("usage_events",),
    "ratingPeriods": ("rating_periods", "rating_results"),
}
STAGING_SUFFIX = "__staging"


def read_source(
    dsn_json: str, tables_wanted: tuple[str, ...] | None = None
) -> dict[str, list[dict[str, Any]]]:
    import psycopg
    from psycopg import sql
    from psycopg.rows import dict_row

    params = json.loads(dsn_json)
    schema = params.pop("schema", "billing")
    params["dbname"] = params.pop("database")
    tables: dict[str, list[dict[str, Any]]] = {}
    with psycopg.connect(**params, row_factory=dict_row) as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        for table in tables_wanted or tuple(dict.fromkeys(sum(SOURCE_TABLES.values(), ()))):
            query = sql.SQL("SELECT * FROM {} ORDER BY id").format(sql.Identifier(schema, table))
            tables[table] = connection.execute(query).fetchall()
    return tables


def build_documents(tables: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    """Documents for every collection whose source tables are present in `tables`."""
    documents: dict[str, list[dict[str, Any]]] = {}
    if "plans" in tables:
        documents["plans"] = [plan_document(row) for row in tables["plans"]]
    if "tenants" in tables:
        notes_by_tenant: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        for note in tables["credit_notes"]:
            notes_by_tenant[note["tenant_id"]].append(note)
        documents["tenants"] = [
            tenant_document(row, notes_by_tenant[row["id"]]) for row in tables["tenants"]
        ]
    if "subscriptions" in tables:
        documents["subscriptions"] = [subscription_document(row) for row in tables["subscriptions"]]
    if "usage_events" in tables:
        documents["usageEvents"] = [usage_event_document(row) for row in tables["usage_events"]]
    if "rating_periods" in tables:
        result_by_period = {row["period_id"]: row for row in tables["rating_results"]}
        documents["ratingPeriods"] = [
            rating_period_document(row, result_by_period.get(row["id"]))
            for row in tables["rating_periods"]
        ]
    return documents


def load(
    dsn_json: str, database: Database, collections: tuple[str, ...] = COLLECTIONS
) -> dict[str, int]:
    """Build each selected collection in a staging namespace, then swap it into place.

    A failure while staging leaves the live collections untouched; the swap itself is
    one atomic rename per collection. Only `collections` are read and written.
    """
    unknown = sorted(set(collections) - set(COLLECTIONS))
    if unknown:
        raise ValueError(f"unknown collections {unknown}")
    tables = tuple(dict.fromkeys(table for name in collections for table in SOURCE_TABLES[name]))
    documents = build_documents(read_source(dsn_json, tables))
    staged: list[str] = []
    for name in collections:
        staging = f"{name}{STAGING_SUFFIX}"
        database.drop_collection(staging)
        collection = database.create_collection(staging, validator=VALIDATORS[name])
        collection.create_indexes(INDEXES[name])
        if documents[name]:
            collection.insert_many(documents[name], ordered=True)
        staged.append(staging)
    for name, staging in zip(collections, staged, strict=True):
        database[staging].rename(name, dropTarget=True)
    return {name: database[name].count_documents({}) for name in collections}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dsn-secret", default="POSTGRESQL_RO_DSN")
    parser.add_argument("--target-uri-secret", default="MONGODB_ATLAS_URI")
    parser.add_argument("--database", default="billing_migration")
    parser.add_argument(
        "--collections",
        default=",".join(COLLECTIONS),
        help="comma-separated subset of the collections to load (the batch's write targets)",
    )
    args = parser.parse_args(argv)
    collections = tuple(name for name in args.collections.split(",") if name)
    try:
        dsn, uri = os.environ[args.source_dsn_secret], os.environ[args.target_uri_secret]
    except KeyError as missing:
        print(f"secret {missing} is not set in the environment", file=sys.stderr)
        return 2
    database = MongoClient(uri, uuidRepresentation="standard")[args.database]
    counts = load(dsn, database, collections)
    for name, count in counts.items():
        indexes = sorted(database[name].index_information())
        print(f"{args.database}.{name}: {count} documents, indexes {indexes}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
