"""Build the U9 dunning replay clone in Atlas."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bson import Int64
from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parent))
from load_u5 import NS_VALUE, TARGET_DB, secret_value, validate_target_db

PREFIX = "replay_u9_"
SOURCE_COLLECTIONS = (
    "billing_invoices",
    "tenants",
    "subscriptions",
    "subscriptions_history",
    "dunning_attempts",
    "notifications",
    "billing_audit_log",
)
COUNTERS = f"{PREFIX}counters"
UNIT_COLLECTIONS = tuple(f"{PREFIX}{name}" for name in SOURCE_COLLECTIONS) + (COUNTERS,)


def clone_name(source: str) -> str:
    return f"{PREFIX}{source}"


def assert_owned(name: str) -> None:
    if not name.startswith(PREFIX):
        raise ValueError(f"refusing to write collection U9 does not own: {name!r}")


def _index_specs(collection: Any) -> list[dict[str, Any]]:
    return [
        {
            "keys": list(index["key"].items()),
            "options": {
                key: value
                for key, value in index.items()
                if key in ("unique", "expireAfterSeconds", "sparse", "partialFilterExpression")
            },
        }
        for index in collection.list_indexes()
        if index["name"] != "_id_"
    ]


def _embedded(collection: Any, field: str) -> int:
    row = next(
        collection.aggregate(
            [
                {"$project": {"n": {"$size": {"$ifNull": [f"${field}", []]}}}},
                {"$group": {"_id": None, "total": {"$sum": "$n"}}},
            ]
        ),
        {"total": 0},
    )
    return row["total"]


def clone_collection(database: Any, source: str) -> dict[str, Any]:
    target = clone_name(source)
    assert_owned(target)
    if source not in database.list_collection_names():
        raise RuntimeError(f"source collection {source!r} is missing")
    source_collection = database[source]
    source_rows = source_collection.count_documents({})
    database.drop_collection(target)
    source_collection.aggregate([{"$match": {}}, {"$out": target}])
    source_options = next(
        (c.get("options", {}) for c in database.list_collections(filter={"name": source})),
        {},
    )
    if source_options.get("validator"):
        database.command(
            "collMod",
            target,
            validator=source_options["validator"],
            validationLevel=source_options.get("validationLevel", "strict"),
            validationAction=source_options.get("validationAction", "error"),
        )
    indexes = [
        database[target].create_index(spec["keys"], **spec["options"])
        for spec in _index_specs(source_collection)
    ]
    docs_after = database[target].count_documents({})
    ns_docs_after = database[target].count_documents({"ns": NS_VALUE})
    if docs_after != source_rows or ns_docs_after != source_rows:
        raise RuntimeError(
            f"{target}: expected {source_rows} documents, got "
            f"{docs_after} ({ns_docs_after} namespaced)"
        )
    report = {
        "cloned_from": source,
        "dropped": True,
        "recreated": True,
        "source_rows": source_rows,
        "inserted": docs_after,
        "docs_after": docs_after,
        "ns_docs_after": ns_docs_after,
        "indexes": sorted(indexes),
    }
    if source == "billing_invoices":
        report["embedded"] = {"lines": _embedded(database[target], "lines")}
    return report


def seed_counters(database: Any) -> dict[str, Any]:
    assert_owned(COUNTERS)
    database.drop_collection(COUNTERS)
    audit = database[clone_name("billing_audit_log")].find_one(sort=[("log_id", -1)])
    history = database[clone_name("subscriptions_history")].find_one(
        sort=[("hist_id", -1)]
    )
    audit_start = Int64(audit["log_id"]) if audit else Int64(0)
    history_start = Int64(history["hist_id"]) if history else Int64(0)
    database[COUNTERS].insert_one(
        {"_id": "seq_billing_audit_log", "seq": audit_start, "ns": NS_VALUE}
    )
    database[COUNTERS].insert_one(
        {
            "_id": "seq_subscriptions_hist",
            "seq": history_start,
            "ns": NS_VALUE,
        }
    )
    return {
        "dropped": True,
        "recreated": True,
        "source_rows": 2,
        "inserted": 2,
        "docs_after": 2,
        "ns_docs_after": 2,
        "indexes": [],
        "sequence_starts": {
            "seq_billing_audit_log": int(audit_start),
            "seq_subscriptions_hist": int(history_start),
        },
    }


def reset_collections(database: Any, names: tuple[str, ...] | list[str]) -> None:
    for name in names:
        if name == "counters":
            seed_counters(database)
        elif name in SOURCE_COLLECTIONS:
            clone_collection(database, name)
        elif name.startswith(PREFIX):
            clone_collection(database, name.removeprefix(PREFIX))
        else:
            raise ValueError(f"unsupported U9 reset collection: {name!r}")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri-secret", default="MONGODB_ATLAS_URI")
    parser.add_argument("--target-db", default=TARGET_DB)
    parser.add_argument("--report", default=".migration/recon/U9/load_report.json")
    args = parser.parse_args(argv)
    try:
        validate_target_db(args.target_db)
    except ValueError as exc:
        parser.error(str(exc))
    return args


def run(args: argparse.Namespace) -> dict[str, Any]:
    started_at = utc_now()
    validate_target_db(args.target_db)
    client = MongoClient(secret_value(args.uri_secret))
    try:
        database = client[args.target_db]
        collections = {
            clone_name(source): clone_collection(database, source)
            for source in SOURCE_COLLECTIONS
        }
        collections[COUNTERS] = seed_counters(database)
    finally:
        client.close()
    report = {
        "unit": "U9",
        "started_at": started_at,
        "finished_at": utc_now(),
        "generated_at": utc_now(),
        "target_db": args.target_db,
        "ns": NS_VALUE,
        "prefix": PREFIX,
        "collections": collections,
        "secret_names": {"uri": args.uri_secret},
    }
    path = Path(args.report)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n")
    return report


def main(argv: list[str] | None = None) -> int:
    report = run(parse_args(argv))
    for name, info in report["collections"].items():
        print(f"{name}: {info['docs_after']} docs, indexes={info['indexes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
