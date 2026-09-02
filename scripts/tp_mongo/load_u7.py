"""Build the U7 Tier-4 replay clone: `replay_u7_*` copies of the merged U5 billing set
plus the U0 `plans`/`tenants` references, inside ow_tp_mongodb_205236.

The rating module (services/legacy-billing/app/ow_billing/rating.py) is replayed
against this clone so the shared U5/U0 collections are never mutated. Each clone
collection is dropped and recreated from its source collection on every run
(`$out`), then re-indexed like the source; only `replay_u7_*` names are written.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import oracledb
from bson import Int64
from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parent))
from load_u5 import (
    NS_VALUE,
    TARGET_DB,
    fetch,
    parse_dsn,
    secret_value,
    validate_target_db,
)

PREFIX = "replay_u7_"
SOURCE_COLLECTIONS = (
    "subscriptions",
    "subscriptions_history",
    "usage_events",
    "rating_periods",
    "billing_invoices",
    "credit_notes",
    "dunning_attempts",
    "notifications",
    "billing_audit_log",
    "plans",
    "tenants",
)
COUNTERS = f"{PREFIX}counters"
AUDIT_SEQUENCE = "seq_billing_audit_log"
SOURCE_AUDIT_SEQUENCE = "SEQ_BILLING_AUDIT_LOG"
HISTORY_SEQUENCE = "seq_subscriptions_hist"
SOURCE_HISTORY_SEQUENCE = "SEQ_SUBSCRIPTIONS_HIST"
UNIT_COLLECTIONS = tuple(f"{PREFIX}{name}" for name in SOURCE_COLLECTIONS) + (COUNTERS,)


def clone_name(source: str) -> str:
    return f"{PREFIX}{source}"


def assert_owned(name: str) -> None:
    if not name.startswith(PREFIX):
        raise ValueError(f"refusing to write a collection U7 does not own: {name!r}")


def _index_specs(collection: Any) -> list[dict[str, Any]]:
    specs = []
    for index in collection.list_indexes():
        if index["name"] == "_id_":
            continue
        options = {
            key: value
            for key, value in index.items()
            if key in ("unique", "expireAfterSeconds", "sparse", "partialFilterExpression")
        }
        specs.append({"keys": list(index["key"].items()), "options": options})
    return specs


def clone_collection(database: Any, source: str) -> dict[str, Any]:
    target = clone_name(source)
    assert_owned(target)
    if source not in database.list_collection_names():
        raise RuntimeError(f"source collection {source!r} is missing; U7 depends on U5/U0")
    source_docs = database[source].count_documents({})
    database.drop_collection(target)
    database[source].aggregate([{"$match": {}}, {"$out": target}])
    source_options = next(
        (c.get("options", {}) for c in database.list_collections(filter={"name": source})), {}
    )
    validator = source_options.get("validator")
    if validator:
        database.command(
            "collMod",
            target,
            validator=validator,
            validationLevel=source_options.get("validationLevel", "strict"),
            validationAction=source_options.get("validationAction", "error"),
        )
    index_names = [
        database[target].create_index(spec["keys"], **spec["options"])
        for spec in _index_specs(database[source])
    ]
    docs_after = database[target].count_documents({})
    ns_docs_after = database[target].count_documents({"ns": NS_VALUE})
    if docs_after != source_docs or ns_docs_after != source_docs:
        raise RuntimeError(
            f"{target}: expected {source_docs} documents, got {docs_after} "
            f"({ns_docs_after} namespaced)"
        )
    report = {
        "cloned_from": source,
        "dropped": True,
        "recreated": True,
        "source_rows": source_docs,
        "inserted": docs_after,
        "docs_after": docs_after,
        "ns_docs_after": ns_docs_after,
        "indexes": sorted(index_names),
    }
    if source == "rating_periods":
        report["embedded"] = {"results": _embedded(database[target], "results")}
    if source == "billing_invoices":
        report["embedded"] = {"lines": _embedded(database[target], "lines")}
    return report


def _embedded(collection: Any, field: str) -> int:
    row = next(
        collection.aggregate(
            [
                {"$project": {"n": {"$size": f"${field}"}}},
                {"$group": {"_id": None, "total": {"$sum": "$n"}}},
            ]
        ),
        {"total": 0},
    )
    return row["total"]


def seed_counters(database: Any, oracle_last_numbers: dict[str, int]) -> dict[str, Any]:
    """Seed audit and history counters after the Oracle and clone maxima."""
    assert_owned(COUNTERS)
    database.drop_collection(COUNTERS)
    starts = {
        AUDIT_SEQUENCE: max(
            oracle_last_numbers[SOURCE_AUDIT_SEQUENCE],
            int(
                (
                    database[clone_name("billing_audit_log")].find_one(
                        sort=[("log_id", -1)]
                    )
                    or {}
                ).get("log_id", 0)
            ),
        ),
        HISTORY_SEQUENCE: max(
            oracle_last_numbers[SOURCE_HISTORY_SEQUENCE],
            int(
                (
                    database[clone_name("subscriptions_history")].find_one(
                        sort=[("hist_id", -1)]
                    )
                    or {}
                ).get("hist_id", 0)
            ),
        ),
    }
    seeds = {
        AUDIT_SEQUENCE: {
            "_id": AUDIT_SEQUENCE,
            "seq": Int64(starts[AUDIT_SEQUENCE]),
            "source_sequence": SOURCE_AUDIT_SEQUENCE,
            "ns": NS_VALUE,
        },
        HISTORY_SEQUENCE: {
            "_id": HISTORY_SEQUENCE,
            "seq": Int64(starts[HISTORY_SEQUENCE]),
            "source_sequence": SOURCE_HISTORY_SEQUENCE,
            "ns": NS_VALUE,
        },
    }
    database[COUNTERS].insert_many(list(seeds.values()), ordered=True)
    return {
        "dropped": True,
        "recreated": True,
        "source_rows": len(seeds),
        "inserted": len(seeds),
        "docs_after": len(seeds),
        "ns_docs_after": len(seeds),
        "indexes": [],
        "sequence_start": starts[AUDIT_SEQUENCE],
        "oracle_last_number": oracle_last_numbers[SOURCE_AUDIT_SEQUENCE],
        "history_sequence_start": starts[HISTORY_SEQUENCE],
        "history_oracle_last_number": oracle_last_numbers[SOURCE_HISTORY_SEQUENCE],
    }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn-secret", default="OW_BILLING_FIXTURE_DSN")
    parser.add_argument("--uri-secret", default="MONGODB_ATLAS_URI")
    parser.add_argument("--target-db", default=TARGET_DB)
    parser.add_argument("--report", default=".migration/recon/U7/load_report.json")
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
    with oracledb.connect(user=user, password=password, dsn=dsn) as oracle:
        rows = fetch(
            oracle,
            "SELECT SEQUENCE_NAME, LAST_NUMBER FROM USER_SEQUENCES "
            "WHERE SEQUENCE_NAME IN (:audit_sequence, :history_sequence)",
            {
                "audit_sequence": SOURCE_AUDIT_SEQUENCE,
                "history_sequence": SOURCE_HISTORY_SEQUENCE,
            },
        )
    oracle_last_numbers = {row["SEQUENCE_NAME"]: int(row["LAST_NUMBER"]) for row in rows}
    missing = {
        SOURCE_AUDIT_SEQUENCE,
        SOURCE_HISTORY_SEQUENCE,
    } - set(oracle_last_numbers)
    if missing:
        raise LookupError(f"Oracle sequences {sorted(missing)!r} were not found")
    client = MongoClient(secret_value(args.uri_secret))
    try:
        database = client[args.target_db]
        collections = {clone_name(s): clone_collection(database, s) for s in SOURCE_COLLECTIONS}
        collections[COUNTERS] = seed_counters(database, oracle_last_numbers)
    finally:
        client.close()
    report = {
        "unit": "U7",
        "started_at": started_at,
        "finished_at": utc_now(),
        "generated_at": utc_now(),
        "target_db": args.target_db,
        "ns": NS_VALUE,
        "collections": collections,
        "secret_names": {"dsn": args.dsn_secret, "uri": args.uri_secret},
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
