"""Load the Postgres U3 document data into MongoDB Atlas."""

from __future__ import annotations

import argparse
import json
import os
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import psycopg
from pymongo import ASCENDING, DESCENDING, MongoClient


NS_VALUE = "mongo_205236"
TARGET_DB = "ow_tp_mongodb_205236"
QUARANTINE_DB = "ow_tp_mongodb_205236_quarantine"
UNIT_COLLECTIONS = ("documents", "document_snapshots")
QUARANTINE_COLLECTIONS = ("orphan_document_snapshots",)
BATCH_SIZE = 500

DOCUMENTS_QUERY = """
    SELECT id, title, content, content_type, owner_id, folder_id,
           is_deleted, is_template, word_count, version, created_at, updated_at
    FROM otterworks_demo.documents
    ORDER BY id
"""
VERSIONS_QUERY = """
    SELECT id, document_id, version_number, title, content, created_by, created_at
    FROM otterworks_demo.document_versions
    ORDER BY document_id, version_number, id
"""
SNAPSHOTS_QUERY = """
    SELECT id, document_id, state_b64, label, created_by, created_at
    FROM otterworks_demo.document_snapshots
    ORDER BY id
"""


def _uuid_string(value: Any) -> str:
    return str(value).lower()


def _utc_millisecond(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    value = value.astimezone(timezone.utc)
    return value.replace(microsecond=(value.microsecond // 1000) * 1000)


def _version_document(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": _uuid_string(row["id"]),
        "version_number": int(row["version_number"]),
        "title": str(row["title"]),
        "content": str(row["content"]),
        "created_by": _uuid_string(row["created_by"]),
        "created_at": _utc_millisecond(row["created_at"]),
    }


def transform_document(
    row: Mapping[str, Any], versions: Sequence[Mapping[str, Any]] = ()
) -> dict[str, Any]:
    transformed_versions = sorted(
        (_version_document(version) for version in versions),
        key=lambda version: (version["version_number"], version["id"]),
    )
    version_numbers = {
        version["version_number"] for version in transformed_versions
    }
    max_version = max(int(row["version"]), max(version_numbers, default=0))
    document = {
        "_id": _uuid_string(row["id"]),
        "title": str(row["title"]),
        "content": str(row["content"]),
        "content_type": str(row["content_type"]),
        "owner_id": _uuid_string(row["owner_id"]),
        "is_deleted": bool(row["is_deleted"]),
        "is_template": bool(row["is_template"]),
        "word_count": int(row["word_count"]),
        "version": int(row["version"]),
        "created_at": _utc_millisecond(row["created_at"]),
        "updated_at": _utc_millisecond(row["updated_at"]),
        "versions": transformed_versions,
        "version_gaps": sorted(set(range(1, max_version + 1)) - version_numbers),
        "ns": NS_VALUE,
    }
    if row["folder_id"] is not None:
        document["folder_id"] = _uuid_string(row["folder_id"])
    return document


def transform_snapshot(row: Mapping[str, Any]) -> dict[str, Any]:
    snapshot = {
        "_id": _uuid_string(row["id"]),
        "document_id": _uuid_string(row["document_id"]),
        "state_b64": str(row["state_b64"]),
        "created_by": _uuid_string(row["created_by"]),
        "created_at": _utc_millisecond(row["created_at"]),
        "ns": NS_VALUE,
    }
    if row["label"] is not None:
        snapshot["label"] = str(row["label"])
    return snapshot


def quarantine_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    row = {key: value for key, value in snapshot.items() if key != "ns"}
    return {
        "_id": snapshot["_id"],
        "unit": "U3",
        "source_table": "otterworks_demo.document_snapshots",
        "source_key": {"id": snapshot["_id"]},
        "reason_class": "orphan_parent",
        "reason": "document_id has no otterworks_demo.documents row",
        "document_id": snapshot["document_id"],
        "source_watermark": snapshot["created_at"],
        "quarantined_at": datetime.now(timezone.utc),
        "ns": NS_VALUE,
        "row": row,
    }


def validate_target_db(target_db: str) -> None:
    if target_db != TARGET_DB:
        raise ValueError(f"--target-db must be {TARGET_DB!r}, got {target_db!r}")


def secret_value(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"required secret environment variable is missing: {name}")
    return value


def extract_rows(connection: Any, query: str) -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        cursor.execute(query)
        columns = [description.name for description in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _insert_batches(collection: Any, documents: Sequence[Mapping[str, Any]]) -> int:
    for start in range(0, len(documents), BATCH_SIZE):
        collection.insert_many(
            list(documents[start : start + BATCH_SIZE]), ordered=False
        )
    return len(documents)


def _load_collection(
    database: Any,
    collection_name: str,
    documents: Sequence[Mapping[str, Any]],
    source_rows: int,
    index_specs: Sequence[Sequence[tuple[str, int]]],
    root_table: str,
) -> dict[str, Any]:
    database.drop_collection(collection_name)
    database.create_collection(collection_name)
    collection = database[collection_name]
    inserted = _insert_batches(collection, documents)
    indexes = [collection.create_index(list(index_keys)) for index_keys in index_specs]
    docs_after = collection.count_documents({})
    ns_docs_after = collection.count_documents({"ns": NS_VALUE})
    if docs_after != len(documents) or ns_docs_after != len(documents):
        raise RuntimeError(
            f"{collection_name}: expected {len(documents)} documents, got "
            f"{docs_after} documents and {ns_docs_after} namespaced documents"
        )
    return {
        "root_table": root_table,
        "dropped": True,
        "recreated": True,
        "source_rows": source_rows,
        "inserted": inserted,
        "docs_after": docs_after,
        "ns_docs_after": ns_docs_after,
        "indexes": indexes,
    }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn-secret", default="OW_PG_DSN")
    parser.add_argument("--uri-secret", default="MONGODB_ATLAS_URI")
    parser.add_argument("--target-db", default=TARGET_DB)
    parser.add_argument("--quarantine-db", default=QUARANTINE_DB)
    parser.add_argument("--report", default=".migration/recon/U3/load_report.json")
    args = parser.parse_args(argv)
    try:
        validate_target_db(args.target_db)
    except ValueError as exc:
        parser.error(str(exc))
    return args


def run(args: argparse.Namespace) -> dict[str, Any]:
    started_at = utc_now()
    validate_target_db(args.target_db)
    dsn = secret_value(args.dsn_secret)
    uri = secret_value(args.uri_secret)

    with psycopg.connect(dsn, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET default_transaction_read_only = on")
            cursor.execute("SET TIME ZONE 'UTC'")
        document_rows = extract_rows(connection, DOCUMENTS_QUERY)
        version_rows = extract_rows(connection, VERSIONS_QUERY)
        snapshot_rows = extract_rows(connection, SNAPSHOTS_QUERY)

    document_ids = {_uuid_string(row["id"]) for row in document_rows}
    versions_by_document: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    orphan_versions = 0
    for version in version_rows:
        document_id = _uuid_string(version["document_id"])
        if document_id in document_ids:
            versions_by_document[document_id].append(version)
        else:
            orphan_versions += 1

    documents = [
        transform_document(row, versions_by_document[_uuid_string(row["id"])])
        for row in document_rows
    ]
    snapshots = [transform_snapshot(row) for row in snapshot_rows]
    loaded_snapshots = [
        snapshot for snapshot in snapshots if snapshot["document_id"] in document_ids
    ]
    quarantined_snapshots = [
        quarantine_snapshot(snapshot)
        for snapshot in snapshots
        if snapshot["document_id"] not in document_ids
    ]
    gap_detail = [
        {
            "document_id": document["_id"],
            "max_version": max(
                int(document["version"]),
                max(
                    (version["version_number"] for version in document["versions"]),
                    default=0,
                ),
            ),
            "missing": document["version_gaps"],
        }
        for document in documents
        if document["version_gaps"]
    ]

    client = MongoClient(uri)
    try:
        target_database = client[args.target_db]
        quarantine_database = client[args.quarantine_db]
        collections = {
            "documents": _load_collection(
                target_database,
                "documents",
                documents,
                len(document_rows),
                (
                    (("owner_id", ASCENDING),),
                    (("folder_id", ASCENDING),),
                ),
                "otterworks_demo.documents",
            ),
            "document_snapshots": _load_collection(
                target_database,
                "document_snapshots",
                loaded_snapshots,
                len(loaded_snapshots),
                ((("document_id", ASCENDING), ("created_at", DESCENDING)),),
                "otterworks_demo.document_snapshots",
            ),
            "orphan_document_snapshots": _load_collection(
                quarantine_database,
                "orphan_document_snapshots",
                quarantined_snapshots,
                len(quarantined_snapshots),
                ((("document_id", ASCENDING),),),
                "otterworks_demo.document_snapshots",
            ),
        }
        # Multikey indexes are created after the regular collection load.
        versions_index = target_database["documents"].create_index(
            [("versions.id", ASCENDING)]
        )
        collections["documents"]["indexes"].append(versions_index)
    finally:
        client.close()

    embedded_versions = sum(len(document["versions"]) for document in documents)
    if len(documents) != len(document_rows) or embedded_versions != len(version_rows) - orphan_versions:
        raise RuntimeError(
            "source/load mismatch for documents or embedded document_versions"
        )
    report = {
        "started_at": started_at,
        "finished_at": utc_now(),
        "target_db": args.target_db,
        "quarantine_db": args.quarantine_db,
        "ns": NS_VALUE,
        "secret_names": {"dsn": args.dsn_secret, "uri": args.uri_secret},
        "collections": collections,
        "embedded_versions": embedded_versions,
        "orphan_versions": orphan_versions,
        "quarantined_snapshots": len(quarantined_snapshots),
        "quarantined_snapshot_ids": [
            snapshot["_id"] for snapshot in quarantined_snapshots
        ],
        "documents_declared_version_mismatch": sum(
            document["version"] != len(document["versions"]) for document in documents
        ),
        "version_gaps": {
            "definition": (
                "missing version numbers in 1..max(documents.version, "
                "max(versions.version_number)); reported only, never repaired (D7)"
            ),
            "documents_with_gaps": len(gap_detail),
            "total_missing_numbers": sum(len(item["missing"]) for item in gap_detail),
            "detail": gap_detail,
        },
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, default=_json_default) + "\n")
    return report


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run(args)
    print(
        "U3 load complete: "
        f"target_db={report['target_db']} ns={NS_VALUE} "
        f"documents={report['collections']['documents']['inserted']} "
        f"document_snapshots={report['collections']['document_snapshots']['inserted']} "
        f"orphan_document_snapshots="
        f"{report['collections']['orphan_document_snapshots']['inserted']} "
        f"embedded_versions={report['embedded_versions']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
