"""Incremental (delta) sync of the billing_migration collections from the legacy PostgreSQL.

Re-runnable after every production cycle without a full reload. The legacy schema has no
`updated_at` or sequence column on any table (`rating_results.created_at` is set once and not
touched by the `ON CONFLICT ... DO UPDATE` in `sp_finalize_rating`), so every collection falls
back to a keyed diff: the source rows are read once (one connection, REPEATABLE READ READ ONLY)
and mapped through the same `build_documents` the full load uses, then compared document by
document with the target by `_id` on their canonical BSON encoding. Changed or new documents
are upserted with `ReplaceOne(upsert=True)`, documents whose key left the source are deleted.
Running the sync twice in a row is a no-op the second time. A collection whose source reads back
empty while the target still holds documents is left untouched and reported (exit 1) unless
`--allow-empty-source` is given; the other collections still sync. `--database` must be listed in
the committed `.migration/allowed_targets.json`.

    python -m app.delta --source-dsn-secret POSTGRESQL_RO_DSN \
        --target-uri-secret MONGODB_ATLAS_URI --log .migration/recon/parallel-run/cycle-1/delta.json

The log carries counts and salted-or-not hashes of the changed keys only, never values or
secrets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bson import encode
from bson.binary import UuidRepresentation
from bson.codec_options import CodecOptions
from pymongo import MongoClient, ReplaceOne
from pymongo.database import Database

from app.documents import COLLECTIONS
from app.load import SOURCE_TABLES, build_documents, read_source

CODEC = CodecOptions(uuid_representation=UuidRepresentation.STANDARD, tz_aware=True)
WATERMARK: dict[str, str | None] = dict.fromkeys(COLLECTIONS)


def diff_documents(
    source: list[dict[str, Any]], target: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[Any], int]:
    """(documents to upsert, keys to delete, unchanged count) for one collection."""
    current = {document["_id"]: encode(document, codec_options=CODEC) for document in target}
    upserts: list[dict[str, Any]] = []
    unchanged = 0
    for document in source:
        encoded = encode(document, codec_options=CODEC)
        if current.pop(document["_id"], None) == encoded:
            unchanged += 1
        else:
            upserts.append(document)
    return upserts, list(current), unchanged


def _key_hash(key: Any, salt: str) -> str:
    return hashlib.sha256(f"{salt}{key}".encode()).hexdigest()[:12]


def allowed_databases(allowed_targets_file: str | None = None) -> set[str]:
    """Databases from the committed `.migration/allowed_targets.json` (the write fence)."""
    if allowed_targets_file is None:
        for parent in (Path.cwd(), *Path.cwd().parents):
            candidate = parent / ".migration" / "allowed_targets.json"
            if candidate.is_file():
                allowed_targets_file = str(candidate)
                break
        else:
            raise FileNotFoundError(".migration/allowed_targets.json not found above the cwd")
    with open(allowed_targets_file) as handle:
        return set(json.load(handle)["databases"])


def sync(
    dsn_json: str,
    database: Database,
    collections: tuple[str, ...] = COLLECTIONS,
    salt: str = "",
    allow_empty_source: bool = False,
) -> dict[str, Any]:
    unknown = sorted(set(collections) - set(COLLECTIONS))
    if unknown:
        raise ValueError(f"unknown collections {unknown}")
    started = time.monotonic()
    tables = tuple(dict.fromkeys(table for name in collections for table in SOURCE_TABLES[name]))
    rows = read_source(dsn_json, tables)
    documents = build_documents(rows)
    report: dict[str, Any] = {}
    for name in collections:
        target = list(database[name].find({}))
        upserts, deletes, unchanged = diff_documents(documents[name], target)
        before = len(target)
        blocked = bool(target) and not documents[name] and not allow_empty_source
        if blocked:
            upserts, deletes, unchanged = [], [], 0
        elif upserts:
            database[name].bulk_write(
                [ReplaceOne({"_id": doc["_id"]}, doc, upsert=True) for doc in upserts],
                ordered=True,
            )
        if deletes:
            database[name].delete_many({"_id": {"$in": deletes}})
        report[name] = {
            "watermark": WATERMARK[name],
            "method": "keyed_diff",
            "blocked_empty_source": blocked,
            "source_rows": {table: len(rows[table]) for table in SOURCE_TABLES[name]},
            "target_before": before,
            "unchanged": unchanged,
            "upserted": len(upserts),
            "deleted": len(deletes),
            "target_after": database[name].count_documents({}),
            "changed_keys": sorted(_key_hash(doc["_id"], salt) for doc in upserts)
            + sorted(_key_hash(key, salt) for key in deletes),
        }
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "duration_s": round(time.monotonic() - started, 3),
        "collections": report,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dsn-secret", default="POSTGRESQL_RO_DSN")
    parser.add_argument("--target-uri-secret", default="MONGODB_ATLAS_URI")
    parser.add_argument("--database", default="billing_migration")
    parser.add_argument("--collections", default=",".join(COLLECTIONS))
    parser.add_argument("--log", help="write the redacted sync log (JSON) here")
    parser.add_argument(
        "--allowed-targets-file",
        help="write fence (default: nearest .migration/allowed_targets.json above the cwd)",
    )
    parser.add_argument(
        "--allow-empty-source",
        action="store_true",
        help="let a collection whose source read back empty delete its target documents"
        " (default: that collection is left untouched and reported, others still sync)",
    )
    args = parser.parse_args(argv)
    collections = tuple(name for name in args.collections.split(",") if name)
    allowed = allowed_databases(args.allowed_targets_file)
    if args.database not in allowed:
        print(
            f"database {args.database!r} is not in the write fence {sorted(allowed)}",
            file=sys.stderr,
        )
        return 2
    try:
        dsn, uri = os.environ[args.source_dsn_secret], os.environ[args.target_uri_secret]
    except KeyError as missing:
        print(f"secret {missing} is not set in the environment", file=sys.stderr)
        return 2
    salt = os.environ.get("RECON_REDACT_SALT", "")
    database = MongoClient(uri, uuidRepresentation="standard", tz_aware=True)[args.database]
    result = sync(dsn, database, collections, salt, args.allow_empty_source)
    result.update(
        {
            "source_dsn_secret": args.source_dsn_secret,
            "target_uri_secret": args.target_uri_secret,
            "target_db": args.database,
            "redaction_salted": bool(salt),
        }
    )
    blocked = [
        name for name, entry in result["collections"].items() if entry["blocked_empty_source"]
    ]
    for name, entry in result["collections"].items():
        line = (
            f"{args.database}.{name}: {entry['upserted']} upserted, {entry['deleted']} deleted,"
            f" {entry['unchanged']} unchanged ({entry['method']})"
        )
        if name in blocked:
            line += " BLOCKED: source empty while target holds documents (--allow-empty-source)"
        print(line)
    if args.log:
        os.makedirs(os.path.dirname(args.log) or ".", exist_ok=True)
        with open(args.log, "w") as handle:
            json.dump(result, handle, indent=2)
            handle.write("\n")
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
