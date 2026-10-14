"""Load plans, tenants (+creditNotes) and subscriptions from the legacy PostgreSQL
into billing_migration. Secrets are passed by environment variable NAME only.

    python -m app.load --source-dsn-secret POSTGRESQL_RO_DSN --target-uri-secret MONGODB_ATLAS_URI
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
    subscription_document,
    tenant_document,
)

SOURCE_TABLES = ("plans", "tenants", "credit_notes", "subscriptions")
STAGING_SUFFIX = "__staging"


def read_source(dsn_json: str) -> dict[str, list[dict[str, Any]]]:
    import psycopg
    from psycopg import sql
    from psycopg.rows import dict_row

    params = json.loads(dsn_json)
    schema = params.pop("schema", "billing")
    params["dbname"] = params.pop("database")
    tables: dict[str, list[dict[str, Any]]] = {}
    with psycopg.connect(**params, row_factory=dict_row) as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        for table in SOURCE_TABLES:
            query = sql.SQL("SELECT * FROM {} ORDER BY id").format(sql.Identifier(schema, table))
            tables[table] = connection.execute(query).fetchall()
    return tables


def build_documents(tables: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    notes_by_tenant: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for note in tables["credit_notes"]:
        notes_by_tenant[note["tenant_id"]].append(note)
    return {
        "plans": [plan_document(row) for row in tables["plans"]],
        "tenants": [tenant_document(row, notes_by_tenant[row["id"]]) for row in tables["tenants"]],
        "subscriptions": [subscription_document(row) for row in tables["subscriptions"]],
    }


def load(dsn_json: str, database: Database) -> dict[str, int]:
    """Build every collection in a staging namespace, then swap each into place.

    A failure while staging leaves the live collections untouched; the swap itself is
    one atomic rename per collection.
    """
    documents = build_documents(read_source(dsn_json))
    staged: list[str] = []
    for name in COLLECTIONS:
        staging = f"{name}{STAGING_SUFFIX}"
        database.drop_collection(staging)
        collection = database.create_collection(staging, validator=VALIDATORS[name])
        collection.create_indexes(INDEXES[name])
        if documents[name]:
            collection.insert_many(documents[name], ordered=True)
        staged.append(staging)
    for name, staging in zip(COLLECTIONS, staged, strict=True):
        database[staging].rename(name, dropTarget=True)
    return {name: database[name].count_documents({}) for name in COLLECTIONS}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dsn-secret", default="POSTGRESQL_RO_DSN")
    parser.add_argument("--target-uri-secret", default="MONGODB_ATLAS_URI")
    parser.add_argument("--database", default="billing_migration")
    args = parser.parse_args(argv)
    try:
        dsn, uri = os.environ[args.source_dsn_secret], os.environ[args.target_uri_secret]
    except KeyError as missing:
        print(f"secret {missing} is not set in the environment", file=sys.stderr)
        return 2
    database = MongoClient(uri, uuidRepresentation="standard")[args.database]
    counts = load(dsn, database)
    for name, count in counts.items():
        indexes = sorted(database[name].index_information())
        print(f"{args.database}.{name}: {count} documents, indexes {indexes}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
