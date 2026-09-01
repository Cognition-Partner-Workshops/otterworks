"""Load the Oracle U0 reference tables into MongoDB Atlas."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
from typing import Any, Mapping

import oracledb
from bson import Decimal128, Int64
from pymongo import ASCENDING, MongoClient


NS_VALUE = "mongo_205236"
TARGET_DB = "ow_tp_mongodb_205236"
UNIT_COLLECTIONS = ("codes", "tenants", "plans")

QUERIES = {
    "codes": (
        "SELECT CODE_TYPE, CODE_VAL, CODE_DESC FROM CODES "
        "ORDER BY CODE_TYPE, CODE_VAL"
    ),
    "tenants": (
        "SELECT ID, NAME, TAX_EXEMPT_YN, STATUS_CD FROM TENANTS "
        "ORDER BY ID"
    ),
    "plans": (
        "SELECT ID, CODE, TIER_CD, MONTHLY_FEE, INCLUDED_UNITS, "
        "OVERAGE_RATE, ACTIVE_YN FROM PLANS ORDER BY ID"
    ),
}

ROOT_TABLES = {
    "codes": "CODES",
    "tenants": "TENANTS",
    "plans": "PLANS",
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


def transform_codes(row: Mapping[str, Any]) -> dict[str, Any]:
    code_type = vc(row["CODE_TYPE"])
    code_val = i32(row["CODE_VAL"])
    return {
        "_key": f"{code_type}:{code_val}",
        "code_type": code_type,
        "code_val": code_val,
        "code_desc": vc(row["CODE_DESC"]),
        "ns": NS_VALUE,
    }


def transform_tenants(row: Mapping[str, Any]) -> dict[str, Any]:
    identifier = vc(row["ID"])
    return {
        "_id": identifier,
        "id": identifier,
        "name": vc(row["NAME"]),
        "tax_exempt_yn": ch(row["TAX_EXEMPT_YN"]),
        "status_cd": i32(row["STATUS_CD"]),
        "ns": NS_VALUE,
    }


def transform_plans(row: Mapping[str, Any]) -> dict[str, Any]:
    identifier = vc(row["ID"])
    return {
        "_id": identifier,
        "id": identifier,
        "code": vc(row["CODE"]),
        "tier_cd": i32(row["TIER_CD"]),
        "monthly_fee": dec(row["MONTHLY_FEE"], 2),
        "included_units": lng(row["INCLUDED_UNITS"]),
        "overage_rate": dec(row["OVERAGE_RATE"], 6),
        "active_yn": ch(row["ACTIVE_YN"]),
        "ns": NS_VALUE,
    }


TRANSFORMERS = {
    "codes": transform_codes,
    "tenants": transform_tenants,
    "plans": transform_plans,
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
    cursor.execute(QUERIES[collection])
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def load_collection(database: Any, collection: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    database.drop_collection(collection)
    database.create_collection(collection)
    documents = [TRANSFORMERS[collection](row) for row in rows]
    if documents:
        database[collection].insert_many(documents, ordered=True)

    index_names: list[str] = []
    if collection == "codes":
        index_names.append(
            database[collection].create_index(
                [("code_type", ASCENDING), ("code_val", ASCENDING)],
                unique=True,
            )
        )
        index_names.append(
            database[collection].create_index([("_key", ASCENDING)], unique=True)
        )

    docs_after = database[collection].count_documents({})
    ns_docs_after = database[collection].count_documents({"ns": NS_VALUE})
    if docs_after != len(rows) or ns_docs_after != len(rows):
        raise RuntimeError(
            f"{collection}: expected {len(rows)} rows, got "
            f"{docs_after} documents and {ns_docs_after} namespaced documents"
        )
    return {
        "root_table": ROOT_TABLES[collection],
        "dropped": True,
        "recreated": True,
        "source_rows": len(rows),
        "inserted": len(documents),
        "docs_after": docs_after,
        "ns_docs_after": ns_docs_after,
        "indexes": index_names,
    }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn-secret", default="OW_BILLING_FIXTURE_DSN")
    parser.add_argument("--uri-secret", default="MONGODB_ATLAS_URI")
    parser.add_argument("--target-db", default=TARGET_DB)
    parser.add_argument("--report", default=".migration/recon/U0/load_report.json")
    args = parser.parse_args(argv)
    try:
        validate_target_db(args.target_db)
    except ValueError as exc:
        parser.error(str(exc))
    return args


def run(args: argparse.Namespace) -> dict[str, Any]:
    started_at = utc_now()
    validate_target_db(args.target_db)
    dsn_value = secret_value(args.dsn_secret)
    uri = secret_value(args.uri_secret)
    user, password, dsn = parse_dsn(dsn_value)

    with oracledb.connect(user=user, password=password, dsn=dsn) as oracle:
        source_rows = {
            collection: extract_rows(oracle, collection)
            for collection in UNIT_COLLECTIONS
        }

    client = MongoClient(uri)
    try:
        database = client[args.target_db]
        collections = {
            collection: load_collection(database, collection, source_rows[collection])
            for collection in UNIT_COLLECTIONS
        }
    finally:
        client.close()

    report = {
        "started_at": started_at,
        "finished_at": utc_now(),
        "target_db": args.target_db,
        "ns": NS_VALUE,
        "secret_names": {
            "dsn": args.dsn_secret,
            "uri": args.uri_secret,
        },
        "collections": collections,
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
    print(f"U0 load complete: target_db={TARGET_DB} ns={NS_VALUE} {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
