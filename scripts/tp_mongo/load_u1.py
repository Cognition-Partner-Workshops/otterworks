"""Load U1 (CUSTOMER_MASTER + ENTITY_ATTR_VALUE, CUSTOMER_MASTER_HIST, sequences) into Atlas.

Field lists and BSON types are driven by the approved mapping spec
(.migration/03_mapping_spec.json, collections `customers` / `customers_history`) so the
155/158 source columns are carried 1:1 without a hand-maintained column list. Derived,
ungraded twins (D3/D4/D8) and the `counters` seed (D11) are added on top.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import defaultdict
from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path
from typing import Any

import oracledb
from bson import Decimal128, Int64
from pymongo import ASCENDING, MongoClient

NS_VALUE = "mongo_205236"
TARGET_DB = "ow_tp_mongodb_205236"
QUARANTINE_DB = "ow_tp_mongodb_205236_quarantine"
UNIT_COLLECTIONS = ("customers", "customers_history", "counters")
QUARANTINE_COLLECTIONS = ("dirty_signup_dt", "bad_csv_list")
BATCH_NO = 85559852
STAGING_SUFFIX = "__staging"

ROOT = Path(__file__).resolve().parents[2]
MAPPING_PATH = ROOT / ".migration/03_mapping_spec.json"

SEQUENCES = (
    "SEQ_CUSTOMER_MASTER",
    "SEQ_CUSTOMER_MASTER_HIST",
    "SEQ_ENTITY_ATTR_VALUE",
    "SEQ_BILLING_AUDIT_LOG",
    "SEQ_SUBSCRIPTIONS_HIST",
)

DATE_TWINS = {"SIGNUP_DT": "signup_date", "LAST_ACTIVITY_DT": "last_activity_date"}
CSV_TWINS = {
    "RELATED_ACCT_IDS": "related_accounts",
    "CHILD_ACCT_IDS": "child_accounts",
    "PROMO_CODES_CSV": "promo_codes",
}
CSV_TOKEN = re.compile(r"^[A-Za-z0-9_-]+$")
DECIMAL_SCALE = re.compile(r"NUMBER\(\d+,(\d+)\)")


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


def dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value.replace(microsecond=(value.microsecond // 1000) * 1000)


def parse_dd_mon_yy(value: str | None) -> datetime | None:
    """Strict DD-MON-YY parse (Oracle default date picture); None when unparseable."""
    if value is None:
        return None
    try:
        return datetime.strptime(value.strip().upper(), "%d-%b-%y")  # noqa: DTZ007 stored as UTC BSON date
    except ValueError:
        return None


def split_csv(value: str | None) -> tuple[list[str] | None, str | None]:
    """Return (items, problem). problem is None for well-formed lists."""
    if value is None:
        return [], None
    tokens = [token.strip() for token in value.split(",")]
    if any(token == "" for token in tokens):
        return None, "empty_token"
    bad = [token for token in tokens if not CSV_TOKEN.match(token)]
    if bad:
        return None, "invalid_token"
    return tokens, None


def convert(field: Mapping[str, Any], value: Any) -> Any:
    bson_type = field["bson_type"]
    rules = field["rules"]
    if bson_type == "string":
        return ch(value) if "rstrip_spaces" in rules else vc(value)
    if bson_type == "int":
        return i32(value)
    if bson_type == "long":
        return lng(value)
    if bson_type == "decimal":
        match = DECIMAL_SCALE.match(field["source_type"])
        return dec(value, int(match.group(1)) if match else 2)
    if bson_type == "date":
        return dt(value)
    raise ValueError(f"unsupported bson_type {bson_type!r} for {field['source']}")


def load_mapping(path: Path = MAPPING_PATH) -> dict[str, Any]:
    spec = json.loads(path.read_text())
    return {c["collection"]: c for c in spec["collections"] if c.get("unit") == "U1"}


def transform_row(fields: list[Mapping[str, Any]], row: Mapping[str, Any]) -> dict[str, Any]:
    return {field["target"]: convert(field, row.get(field["source"])) for field in fields}


def transform_attribute(fields: list[Mapping[str, Any]], row: Mapping[str, Any]) -> dict[str, Any]:
    return transform_row(fields, row)


def derive(document: dict[str, Any], row: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Add D3/D4/D8 derived twins in place; return quarantine records for this row."""
    quarantine: list[dict[str, Any]] = []
    for source, target in DATE_TWINS.items():
        raw = vc(row.get(source))
        parsed = parse_dd_mon_yy(raw)
        document[target] = parsed
        if source == "SIGNUP_DT" and raw is not None and parsed is None:
            quarantine.append({
                "class": "dirty_signup_dt", "cust_id": row["CUST_ID"],
                "source_column": source, "value": raw,
            })
    for source, target in CSV_TWINS.items():
        raw = vc(row.get(source))
        items, problem = split_csv(raw)
        document[target] = items
        if problem is not None:
            quarantine.append({
                "class": "bad_csv_list", "cust_id": row["CUST_ID"],
                "source_column": source, "value": raw, "reason": problem,
            })
    document["addresses"] = {
        "billing": {
            "lines": [document.get(f"addr_line_{i}") for i in range(1, 7)],
            "city": document.get("city"), "state_cd": document.get("state_cd"),
            "zip": document.get("zip"), "zip4": document.get("zip4"),
            "country_cd": document.get("country_cd"),
        },
        "mailing": {
            "lines": [document.get(f"mail_addr_line_{i}") for i in range(1, 7)],
            "city": document.get("mail_city"), "state_cd": document.get("mail_state_cd"),
            "zip": document.get("mail_zip"), "zip4": document.get("mail_zip4"),
            "country_cd": document.get("mail_country_cd"),
        },
    }
    document["phones"] = [
        {"number": document[f"phone{i}"], "type_cd": document.get(f"phone{i}_type_cd")}
        for i in range(1, 5)
        if document.get(f"phone{i}") is not None
    ]
    return quarantine


def build_customer(mapping: Mapping[str, Any], row: Mapping[str, Any],
                   attributes: list[Mapping[str, Any]],
                   batch_no: int = BATCH_NO) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    document = {"_id": row["CUST_ID"]}
    document.update(transform_row(mapping["fields"], row))
    embed = mapping["embeds"][0]
    document[embed["array_path"]] = [
        transform_attribute(embed["fields"], attribute)
        for attribute in sorted(attributes, key=lambda item: item["EAV_ID"])
    ]
    quarantine = derive(document, row)
    document["ns"] = NS_VALUE
    for record in quarantine:
        record["ns"] = NS_VALUE
        record["batch_no"] = batch_no
    return document, quarantine


def build_history(mapping: Mapping[str, Any], row: Mapping[str, Any]) -> dict[str, Any]:
    document = {"_id": Int64(row["HIST_ID"])}
    document.update(transform_row(mapping["fields"], row))
    document["ns"] = NS_VALUE
    return document


def build_counter(name: str, last_number: int) -> dict[str, Any]:
    return {"_id": name.lower(), "seq": Int64(last_number), "source_sequence": name,
            "ns": NS_VALUE}


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


def fetch(connection: Any, sql: str, params: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    cursor = connection.cursor()
    cursor.arraysize = 5000
    cursor.execute(sql, params or {})
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def where_clause(root_where: str | None) -> str:
    if not root_where:
        return ""
    return " WHERE " + root_where.replace("${batch_no}", ":batch_no")


def extract(connection: Any, mapping: Mapping[str, Mapping[str, Any]], batch_no: int) -> dict[str, Any]:
    customers = mapping["customers"]
    history = mapping["customers_history"]
    embed = customers["embeds"][0]
    root_cols = ", ".join(f["source"] for f in customers["fields"])
    root_where = customers["root_where"].replace("${batch_no}", ":batch_no")
    child_cols = ", ".join(f["source"] for f in embed["fields"])
    hist_cols = ", ".join(f["source"] for f in history["fields"])
    return {
        "customers": fetch(
            connection,
            f"SELECT {root_cols} FROM {customers['root_table']} WHERE {root_where} ORDER BY CUST_ID",
            {"batch_no": batch_no},
        ),
        "attributes": fetch(
            connection,
            f"SELECT {child_cols} FROM {embed['child_table']} WHERE {embed['child_where']} "
            f"AND ENTITY_ID IN (SELECT CUST_ID FROM {customers['root_table']} WHERE {root_where}) "
            "ORDER BY EAV_ID",
            {"batch_no": batch_no},
        ),
        "history": fetch(
            connection,
            f"SELECT {hist_cols} FROM {history['root_table']}"
            f"{where_clause(history.get('root_where'))} ORDER BY HIST_ID",
            {"batch_no": batch_no} if history.get("root_where") else None,
        ),
        "sequences": extract_sequences(connection),
    }


def extract_sequences(connection: Any) -> list[dict[str, Any]]:
    binds = ", ".join(f":s{index}" for index in range(1, len(SEQUENCES) + 1))
    params = {f"s{index}": name for index, name in enumerate(SEQUENCES, 1)}
    return fetch(
        connection,
        "SELECT SEQUENCE_NAME, LAST_NUMBER FROM USER_SEQUENCES "
        f"WHERE SEQUENCE_NAME IN ({binds}) ORDER BY SEQUENCE_NAME",
        params,
    )


def build_counters(sequence_rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    found = {row["SEQUENCE_NAME"]: int(row["LAST_NUMBER"]) for row in sequence_rows}
    missing = sorted(set(SEQUENCES) - set(found))
    if missing:
        raise RuntimeError(f"sequences missing from USER_SEQUENCES: {missing}")
    return [build_counter(name, found[name]) for name in SEQUENCES]


def build_documents(mapping: Mapping[str, Mapping[str, Any]], source: Mapping[str, Any],
                    batch_no: int = BATCH_NO) -> dict[str, Any]:
    if not source["customers"]:
        raise RuntimeError(
            f"CUSTOMER_MASTER has no rows for conversion_batch_no={batch_no}; refusing to replace "
            "the target collections with an empty batch"
        )
    by_parent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for attribute in source["attributes"]:
        by_parent[attribute["ENTITY_ID"]].append(attribute)

    customers: list[dict[str, Any]] = []
    quarantine: dict[str, list[dict[str, Any]]] = {name: [] for name in QUARANTINE_COLLECTIONS}
    embedded = 0
    for row in source["customers"]:
        attributes = by_parent.pop(row["CUST_ID"], [])
        embedded += len(attributes)
        document, records = build_customer(mapping["customers"], row, attributes, batch_no)
        customers.append(document)
        for record in records:
            quarantine[record["class"]].append(record)
    orphan_attributes = [attribute for items in by_parent.values() for attribute in items]
    if orphan_attributes:
        raise RuntimeError(
            f"{len(orphan_attributes)} ENTITY_ATTR_VALUE rows have no CUSTOMER_MASTER parent in the "
            "batch; the approved mapping declares no orphan class for U1"
        )
    history = [build_history(mapping["customers_history"], row) for row in source["history"]]
    return {
        "customers": customers,
        "customers_history": history,
        "counters": build_counters(source["sequences"]),
        "quarantine": quarantine,
        "embedded_attributes": embedded,
    }


def replace_collection(database: Any, name: str, documents: list[dict[str, Any]],
                       indexes: list[list[tuple[str, int]]] | None = None,
                       unique_first: bool = False) -> dict[str, Any]:
    """Build `<name>__staging` fully, verify it, then rename it over `name` (dropTarget).

    The previous good copy of `name` is only removed by the final rename, so a failure while
    inserting or indexing leaves the destination untouched and drops the staging copy.
    """
    staging = f"{name}{STAGING_SUFFIX}"
    database.drop_collection(staging)
    database.create_collection(staging)
    try:
        if documents:
            database[staging].insert_many(documents, ordered=True)
        index_names: list[str] = []
        for position, keys in enumerate(indexes or []):
            index_names.append(
                database[staging].create_index(keys, unique=(unique_first and position == 0))
            )
        docs_after = database[staging].count_documents({})
        ns_docs_after = database[staging].count_documents({"ns": NS_VALUE})
        if docs_after != len(documents) or ns_docs_after != len(documents):
            raise RuntimeError(
                f"{name}: expected {len(documents)} documents, got {docs_after} "
                f"({ns_docs_after} namespaced)"
            )
    except Exception:
        database.drop_collection(staging)
        raise
    database[staging].rename(name, dropTarget=True)
    return {"dropped": True, "recreated": True, "inserted": len(documents),
            "docs_after": docs_after, "ns_docs_after": ns_docs_after, "indexes": index_names}


def load(client: MongoClient, target_db: str, mapping: Mapping[str, Mapping[str, Any]],
         built: Mapping[str, Any]) -> dict[str, Any]:
    database = client[target_db]
    quarantine_db = client[QUARANTINE_DB]
    customer_indexes = [
        [(field, ASCENDING) for field in index["keys"]]
        for index in mapping["customers"]["indexes"]
    ]
    report: dict[str, Any] = {
        "customers": replace_collection(database, "customers", built["customers"],
                                        customer_indexes, unique_first=True),
        "customers_history": replace_collection(
            database, "customers_history", built["customers_history"],
            [[("cust_id", ASCENDING), ("hist_dt", ASCENDING)]]),
        "counters": replace_collection(database, "counters", built["counters"]),
    }
    report["customers"]["root_table"] = "CUSTOMER_MASTER"
    report["customers"]["embedded_attributes"] = built["embedded_attributes"]
    report["customers"]["embedded_attributes_after"] = next(
        database["customers"].aggregate([
            {"$project": {"n": {"$size": "$attributes"}}},
            {"$group": {"_id": None, "total": {"$sum": "$n"}}},
        ]), {"total": 0})["total"]
    report["customers_history"]["root_table"] = "CUSTOMER_MASTER_HIST"
    report["counters"]["root_table"] = "USER_SEQUENCES"
    report["counters"]["seeded"] = {
        doc["_id"]: int(doc["seq"]) for doc in built["counters"]
    }
    report["quarantine"] = {
        name: replace_collection(quarantine_db, name, built["quarantine"][name])
        for name in QUARANTINE_COLLECTIONS
    }
    return report


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn-secret", default="OW_BILLING_FIXTURE_DSN")
    parser.add_argument("--uri-secret", default="MONGODB_ATLAS_URI")
    parser.add_argument("--target-db", default=TARGET_DB)
    parser.add_argument("--batch-no", type=int, default=BATCH_NO)
    parser.add_argument("--report", default=".migration/recon/U1/load_report.json")
    parser.add_argument("--counters-only", action="store_true")
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
        if args.counters_only:
            sequence_rows = extract_sequences(oracle)
            built = {"counters": build_counters(sequence_rows)}
        else:
            mapping = load_mapping()
            source = extract(oracle, mapping, args.batch_no)
            built = build_documents(mapping, source, args.batch_no)

    client = MongoClient(uri)
    try:
        if args.counters_only:
            counter_report = replace_collection(client[args.target_db], "counters", built["counters"])
            counter_report["root_table"] = "USER_SEQUENCES"
            counter_report["seeded"] = {
                doc["_id"]: int(doc["seq"]) for doc in built["counters"]
            }
            collections = {"counters": counter_report}
        else:
            collections = load(client, args.target_db, mapping, built)
    finally:
        client.close()

    report = {
        "unit": "U1",
        "started_at": started_at,
        "finished_at": utc_now(),
        "target_db": args.target_db,
        "quarantine_db": QUARANTINE_DB,
        "ns": NS_VALUE,
        "batch_no": args.batch_no,
        "mode": "counters_only" if args.counters_only else "full",
        "secret_names": {"dsn": args.dsn_secret, "uri": args.uri_secret},
        "source_rows": (
            {"USER_SEQUENCES": len(sequence_rows)}
            if args.counters_only
            else {
                "CUSTOMER_MASTER": len(source["customers"]),
                "ENTITY_ATTR_VALUE": len(source["attributes"]),
                "CUSTOMER_MASTER_HIST": len(source["history"]),
                "USER_SEQUENCES": len(source["sequences"]),
            }
        ),
        "collections": collections,
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run(args)
    c = report["collections"]
    if args.counters_only:
        print(
            f"U1 counters-only load complete: target_db={TARGET_DB} ns={NS_VALUE} "
            f"counters={c['counters']['inserted']}"
        )
    else:
        print(
            f"U1 load complete: target_db={TARGET_DB} ns={NS_VALUE} "
            f"customers={c['customers']['inserted']} attributes={c['customers']['embedded_attributes_after']} "
            f"customers_history={c['customers_history']['inserted']} counters={c['counters']['inserted']} "
            f"Q.dirty_signup_dt={c['quarantine']['dirty_signup_dt']['inserted']} "
            f"Q.bad_csv_list={c['quarantine']['bad_csv_list']['inserted']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
