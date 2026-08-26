#!/usr/bin/env python3
"""MongoDB platform showcase for the migrated OtterWorks estate.

    scripts/tp_mongo/showcase.py --ns demo status
    scripts/tp_mongo/showcase.py --ns demo validate-demo
    scripts/tp_mongo/showcase.py --ns demo report
    scripts/tp_mongo/showcase.py --ns demo baseline --legacy-url http://localhost:8096
    scripts/tp_mongo/showcase.py --ns demo recon
    scripts/tp_mongo/showcase.py --ns demo run-job --run-url <url>
    scripts/tp_mongo/showcase.py --ns rehearsal drift --kind corrupt

Five demo beats, one entrypoint:

`validate-demo` proves the collections' `$jsonSchema` validators live: a
conforming insert is accepted, a legacy `DD-MON-YY` string date and a 156th
ad-hoc column are both rejected by the server with error 121, and nothing is
left behind.

`report` runs the legacy RPT-114 finance report as one aggregation pipeline
(see migrations/mongodb/finance_report.py) and diffs it against the golden
legacy report captured by `baseline`.

`recon` recomputes every baseline number from the target — counts, the estate's
line-format checksums, quarantine membership, the report — and exits non-zero
with named failing check ids. `run-job` wraps it and POSTs the failure to the
Devin remediation automation. `drift` stages real damage in a rehearsal
namespace so that failure path can be demonstrated on genuinely broken data.

Every command is namespace-scoped: nothing touches a database outside
`ow_tp_mongodb_<ns>` (+ `_quarantine`), and `drift` refuses persistent
namespaces outright.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MIGRATIONS = os.path.join(REPO_ROOT, "migrations", "mongodb")
sys.path.insert(0, MIGRATIONS)
sys.path.insert(0, os.path.join(MIGRATIONS, "mongo_files"))
sys.path.insert(0, os.path.join(MIGRATIONS, "mongo_customers"))
# the report is the billing service's own module: recon reconciles exactly the
# pipeline the app serves, rather than a second copy of it
sys.path.insert(0, os.path.join(REPO_ROOT, "services", "billing-service"))

import collection_setup as files_setup
import migrate as customers_migrate
import migrate_documents
import mongo_common as common
from app import reports as fr
from bson.decimal128 import Decimal128
from mongo_invoices import common as invoices_common
from pymongo import MongoClient
from pymongo.errors import WriteError

UNIT = "mongo_showcase"
DOCUMENT_VALIDATION_FAILURE = 121

CUSTOMERS = "customers"
INVOICES = "invoices"
DOCUMENTS = "documents"
SNAPSHOTS = "document_snapshots"
FILES = "files"
CORE_COLLECTIONS = (CUSTOMERS, INVOICES, DOCUMENTS, SNAPSHOTS, FILES)
CUSTOMERS_QUARANTINE = "customers_quarantine"
LINES_QUARANTINE = "invoice_lines_quarantine"
# each unit kept its source estate's own name for the tenant namespace field
NS_FIELD = {
    CUSTOMERS: "namespace",
    INVOICES: "ns",
    DOCUMENTS: "ns",
    SNAPSHOTS: "ns",
    FILES: "tenant",
    CUSTOMERS_QUARANTINE: "namespace",
    LINES_QUARANTINE: "ns",
}
DRIFT_JOURNAL = "tp_showcase_drift_journal"

# Namespaces the demo keeps green and browsable: never drifted, never torn down.
PERSISTENT_NAMESPACES = frozenset(
    filter(None, os.getenv("TP_MONGO_PERSISTENT_NS", "demo").split(","))
)

BASELINE_DIR = os.path.join(REPO_ROOT, "docs", "tech-partnerships", "recon", "baseline")
RECON_DIR = os.path.join(REPO_ROOT, "docs", "tech-partnerships", "recon")
MANIFEST_DIR = os.path.join(REPO_ROOT, "testdata", "legacy", "manifests")

WEBHOOK_SECRET_ENV = "OW_TP_MONGO_RECON_WEBHOOK_SECRET"
WEBHOOK_URL_ENV = "OW_TP_MONGO_RECON_WEBHOOK_URL"


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def money(value) -> str | None:
    return fr.money(value)


def decimal_of(value) -> Decimal:
    if isinstance(value, Decimal128):
        return value.to_decimal()
    return Decimal(str(value))


def client(args) -> MongoClient:
    return MongoClient(
        common.mongo_uri(args.run_mode),
        uuidRepresentation="standard",
        serverSelectionTimeoutMS=30000,
    )


def databases(cli, ns: str):
    return cli[common.database_name(ns)], cli[common.quarantine_database_name(ns)]


def _fixture_id(ns: str, kind: str, number: int) -> uuid.UUID:
    return uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"https://otterworks.internal/tp/mongodb/showcase/{ns}/{kind}/{number}",
    )


def _fixture_datetime(number: int) -> datetime:
    return datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(days=number)


def _seed_fixture_units(cli, ns: str):
    """Create the namespace's collections with the migration units' own
    validators and indexes, so seeded fixture documents are held to exactly the
    contract the migrated estate enforces."""
    db = cli[common.database_name(ns)]
    quarantine_db = cli[common.quarantine_database_name(ns)]
    customers_migrate.ensure_collection(
        db,
        customers_migrate.CUSTOMERS_COLLECTION,
        customers_migrate.customers_validator(),
        customers_migrate.CUSTOMER_INDEXES,
    )
    customers_migrate.ensure_collection(
        quarantine_db,
        customers_migrate.QUARANTINE_COLLECTION,
        customers_migrate.quarantine_validator(),
        customers_migrate.QUARANTINE_INDEXES,
    )
    invoices_common.ensure_collection(
        db,
        invoices_common.COLLECTION,
        invoices_common.INVOICE_VALIDATOR,
        invoices_common.INVOICE_INDEXES,
    )
    invoices_common.ensure_collection(
        quarantine_db,
        invoices_common.QUARANTINE_COLLECTION,
        invoices_common.QUARANTINE_VALIDATOR,
        invoices_common.QUARANTINE_INDEXES,
    )
    migrate_documents.prepare_target(cli, ns)
    files_setup.setup(db, quarantine_db)
    return db, quarantine_db


def _fixture_customer(ns: str, number: int, batch: int) -> dict:
    current = Decimal(f"{(number + 1) * 17}.00")
    past_due = Decimal(f"{number % 7 * 3}.00")
    return {
        "_id": _fixture_id(ns, "customer", number),
        "customer_id": f"{ns}-customer-{number:03d}",
        "namespace": ns,
        "customer_no": f"{ns.upper()}-CUST-{number:03d}",
        "customer_name": f"Fixture Customer {number:03d}",
        "signup_dt": _fixture_datetime(number),
        "related_acct_ids": [f"{number + 10000}"],
        "promo_codes": [],
        "balances": {
            "current_amount": Decimal128(current),
            "past_due_amount": Decimal128(past_due),
        },
        "source": {"table": "OW_BILLING.CUSTOMER_MASTER", "batch_no": batch},
    }


def _fixture_invoice(ns: str, number: int, batch: int, rng: random.Random) -> dict:
    line_types = (1, 2, 3, 9)
    status_codes = (10, 20, 30, 40)
    lines = []
    for line_number in range(4):
        qty = Decimal(str((line_number % 3) + 1))
        unit_price = Decimal(str(10 + rng.randrange(1, 90))) + Decimal("0.25")
        amount = qty * unit_price
        tax = (amount * Decimal("0.083")).quantize(Decimal("0.01"))
        line_id = f"{ns}-line-{number:03d}-{line_number + 1}"
        lines.append({
            "line_id": line_id,
            "line_no": line_number + 1,
            "line_type_code": line_types[(number + line_number) % len(line_types)],
            "item_desc": f"Fixture line {line_number + 1}",
            "qty": Decimal128(qty),
            "unit_price": Decimal128(unit_price),
            "amount": Decimal128(amount),
            "tax_amt": Decimal128(tax),
            "line_date": _fixture_datetime(number),
            "service_period": "2024-01",
            "posted": "Y",
            "gl_accounts": [4000 + line_number],
            "source": {
                "cust_id": f"{ns}-customer-{number % 40:03d}",
                "cust_no": f"{ns.upper()}-CUST-{number % 40:03d}",
                "cust_name": f"Fixture Customer {number % 40:03d}",
                "tenant_id": ns,
                "src_system": "fixture",
            },
        })
    total = sum((line["amount"].to_decimal() for line in lines), Decimal("0.00"))
    tax_total = sum((line["tax_amt"].to_decimal() for line in lines), Decimal("0.00"))
    invoice_id = f"{ns}-invoice-{number:03d}"
    return {
        "_id": _fixture_id(ns, "invoice", number),
        "ns": ns,
        "invoice_no": f"{ns.upper()}-INV-{number:03d}",
        "issue_date": _fixture_datetime(number),
        "due_date": _fixture_datetime(number + 30),
        "status_code": status_codes[number % len(status_codes)],
        "header_total": Decimal128(total),
        "lines_total": Decimal128(total),
        "lines_tax_total": Decimal128(tax_total),
        "lines_count": len(lines),
        "header_total_matches_lines": True,
        "customer": {
            "cust_id": f"{ns}-customer-{number % 40:03d}",
            "tenant_id": ns,
        },
        "source": {
            "system": "oracle",
            "schema": "OW_BILLING",
            "table": "INVOICE_HEADER",
            "invoice_id": invoice_id,
            "invoice_no": f"{ns.upper()}-INV-{number:03d}",
            "batch_no": batch,
        },
        "lines": lines,
        "migration": {"unit": "mongo_invoices", "model_version": 1},
    }


def _fixture_document(ns: str, number: int) -> dict:
    timestamp = _fixture_datetime(number)
    legacy_id = f"{ns}-document-{number:03d}"
    return {
        "_id": legacy_id,
        "ns": ns,
        "legacy_id": legacy_id,
        "title": f"Fixture document {number:03d}",
        "content": "fixture content",
        "content_type": "text/plain",
        "owner_id": f"{ns}-owner-{number:03d}",
        "folder_id": None,
        "is_deleted": False,
        "is_template": False,
        "word_count": 2,
        "version": 1,
        "created_at": timestamp,
        "updated_at": timestamp,
        "versions": [{
            "version": 1,
            "legacy_id": f"{legacy_id}:v1",
        }],
        "version_count": 1,
        "version_gaps": [],
        "source": {"store": "postgres", "schema": f"otterworks_{ns}",
                   "table": "documents"},
    }


def _fixture_snapshot(ns: str, number: int) -> dict:
    legacy_id = f"{ns}-snapshot-{number:03d}"
    document_id = f"{ns}-document-{number % 10:03d}"
    return {
        "_id": legacy_id,
        "ns": ns,
        "legacy_id": legacy_id,
        "legacy_document_id": document_id,
        "document_id": document_id,
        "created_at": _fixture_datetime(number),
        "orphaned": False,
        "state": b"fixture-state",
        "state_encoding": "base64-decoded-source-bytes",
        "label": f"Fixture snapshot {number:03d}",
        "created_by": f"{ns}-owner-{number % 10:03d}",
    }


def _fixture_file(ns: str, number: int) -> dict:
    timestamp = _fixture_datetime(number)
    return {
        "_id": f"{ns}-file-{number:03d}",
        "legacy_id": f"{ns}-file-{number:03d}",
        "tenant": ns,
        "storage_key": f"{ns}/fixture/{number:03d}.txt",
        "modified_at": timestamp,
        "created_at": timestamp,
        "name": f"fixture-{number:03d}.txt",
        "mime_type": "text/plain",
        "size_bytes": 15,
        "version": 1,
        "is_trashed": False,
        "folder_id": f"{ns}-folder",
        "owner_id": f"{ns}-owner-{number % 10:03d}",
    }


def cmd_seed_fixture(args, cli) -> int:
    if args.run_mode != "fixture":
        raise SystemExit("seed-fixture requires --run-mode fixture")
    uri = common.mongo_uri("fixture")
    if "mongodb.net" in uri:
        raise SystemExit("refusing to seed fixture data into a shared cluster")
    if args.ns in PERSISTENT_NAMESPACES:
        raise SystemExit(f"refusing to seed persistent namespace {args.ns!r}")
    manifest = os.path.join(MANIFEST_DIR, f"{args.ns}.json")
    if os.path.exists(manifest):
        raise SystemExit(
            f"refusing to seed namespace {args.ns!r}: immutable manifest exists at "
            f"{manifest}"
        )

    db, quarantine_db = _seed_fixture_units(cli, args.ns)
    for name, field in NS_FIELD.items():
        target = db if name in CORE_COLLECTIONS else quarantine_db
        target[name].delete_many({field: args.ns})

    rng = random.Random(args.ns)
    batch = fr.batch_no(args.ns)
    customers = [_fixture_customer(args.ns, i, batch) for i in range(40)]
    invoices = [_fixture_invoice(args.ns, i, batch, rng) for i in range(30)]
    documents = [_fixture_document(args.ns, i) for i in range(10)]
    snapshots = [_fixture_snapshot(args.ns, i) for i in range(5)]
    files = [_fixture_file(args.ns, i) for i in range(12)]
    customer_quarantine = []
    for i, reason in enumerate(("dirty_date", "dirty_date", "malformed_csv_list")):
        customer_quarantine.append({
            "_id": _fixture_id(args.ns, "customer-quarantine", i),
            "customer_id": f"{args.ns}-quarantined-{i:03d}",
            "namespace": args.ns,
            "reason": reason,
            "field": "signup_dt" if reason == "dirty_date" else "related_acct_ids",
            "raw_value": "31-FEB-24" if reason == "dirty_date" else "1001,NULL",
            "parsed_elements": ["1001"] if reason == "malformed_csv_list" else [],
            "source": {"table": "OW_BILLING.CUSTOMER_MASTER", "batch_no": batch},
        })
    line_quarantine = []
    for i in range(2):
        line_quarantine.append({
            "_id": _fixture_id(args.ns, "line-quarantine", i),
            "ns": args.ns,
            "reason": "orphan_no_header",
            "source": {
                "system": "oracle",
                "schema": "OW_BILLING",
                "table": "INVOICE_LINE",
                "line_id": f"{args.ns}-orphan-line-{i:03d}",
                "invoice_id": None,
                "invoice_no": None,
                "cust_id": None,
            },
            "parsed": {
                "amount": Decimal128(f"{i + 1}.00"),
                "tax_amt": Decimal128("0.00"),
                "qty": Decimal128("1"),
                "unit_price": Decimal128(f"{i + 1}.00"),
            },
        })
    db[CUSTOMERS].insert_many(customers)
    db[INVOICES].insert_many(invoices)
    db[DOCUMENTS].insert_many(documents)
    db[SNAPSHOTS].insert_many(snapshots)
    db[FILES].insert_many(files)
    quarantine_db[CUSTOMERS_QUARANTINE].insert_many(customer_quarantine)
    quarantine_db[LINES_QUARANTINE].insert_many(line_quarantine)
    summary = {
        "namespace": args.ns,
        "database": db.name,
        "quarantine_database": quarantine_db.name,
        "batch_no": batch,
        "counts": {
            "customers": len(customers),
            "invoices": len(invoices),
            "documents": len(documents),
            "document_snapshots": len(snapshots),
            "files": len(files),
            "customers_quarantine": len(customer_quarantine),
            "invoice_lines_quarantine": len(line_quarantine),
        },
        "validators": {
            "validationAction": "error",
            "source_units": ["mongo_customers", "mongo_invoices",
                             "mongo_documents", "mongo_files"],
        },
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def baseline_path(ns: str) -> str:
    return os.path.join(BASELINE_DIR, f"mongo_showcase.{ns}.json")


def recon_path(ns: str) -> str:
    return os.path.join(RECON_DIR, f"mongo_showcase.{ns}.recon.json")


def load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: str, payload: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def check(checks: list, cid: str, expected, actual, source_of_truth: str) -> dict:
    entry = {
        "id": cid,
        "expected": expected,
        "actual": actual,
        "source_of_truth": source_of_truth,
        "result": "pass" if expected == actual else "fail",
    }
    checks.append(entry)
    return entry


# --------------------------------------------------------------------------- #
# values recomputed from the target
# --------------------------------------------------------------------------- #


def customers_checksum(db, ns: str) -> tuple[str, int]:
    """The estate's `<customer_id>:<current balance>` md5, in primary-key order."""
    digest = hashlib.md5()
    rows = 0
    cursor = (
        db[CUSTOMERS]
        .find({"namespace": ns}, {"customer_id": 1, "balances.current_amount": 1})
        .sort("customer_id", 1)
    )
    for doc in cursor:
        amount = doc.get("balances", {}).get("current_amount")
        if amount is None:
            raise SystemExit(
                f"customer {doc.get('customer_id')} carries no current balance; "
                "the estate checksum cannot be recomputed from the target"
            )
        digest.update(f"{doc['customer_id']}:{decimal_of(amount):.2f}\n".encode())
        rows += 1
    return digest.hexdigest(), rows


def invoice_line_checksum(db, quarantine_db, ns: str) -> tuple[str, int, int]:
    """The estate's `<line_id>:<amount>` md5 over embedded + quarantined lines."""
    pairs: list[tuple[str, str]] = []
    embedded_ids = set()
    for doc in db[INVOICES].find({"ns": ns}, {"lines.line_id": 1, "lines.amount": 1}):
        for line in doc.get("lines", []):
            pairs.append((line["line_id"], f"{decimal_of(line['amount']):.2f}"))
            embedded_ids.add(line["line_id"])
    embedded = len(pairs)
    for doc in quarantine_db[LINES_QUARANTINE].find(
        {"ns": ns}, {"source.line_id": 1, "parsed.amount": 1}
    ):
        amount = doc.get("parsed", {}).get("amount")
        line_id = doc["source"]["line_id"]
        # a NULL amount is never defaulted to zero, and a line the estate could
        # still embed is only counted once
        if amount is None or line_id in embedded_ids:
            continue
        pairs.append((line_id, f"{decimal_of(amount):.2f}"))
    digest = hashlib.md5()
    for line_id, amount in sorted(pairs):
        digest.update(f"{line_id}:{amount}\n".encode())
    return digest.hexdigest(), embedded, len(pairs)


def quarantine_membership(quarantine_db, ns: str) -> dict:
    """Quarantine ids and reason breakdown, recomputed from the target."""
    customers = {}
    for doc in quarantine_db[CUSTOMERS_QUARANTINE].find(
        {"namespace": ns}, {"customer_id": 1, "reason": 1}
    ):
        customers[f"{doc['reason']}:{doc['customer_id']}"] = True
    lines = {}
    for doc in quarantine_db[LINES_QUARANTINE].find(
        {"ns": ns}, {"source.line_id": 1, "reason": 1}
    ):
        lines[f"{doc['reason']}:{doc['source']['line_id']}"] = True
    ids = sorted(customers) + sorted(lines)
    by_reason: dict[str, int] = {}
    for entry in ids:
        by_reason[entry.split(":", 1)[0]] = by_reason.get(entry.split(":", 1)[0], 0) + 1
    return {"ids": ids, "by_reason": dict(sorted(by_reason.items()))}


def collection_counts(db, quarantine_db, ns: str) -> dict:
    counts = {}
    for name in CORE_COLLECTIONS:
        counts[name] = db[name].count_documents({NS_FIELD[name]: ns})
    for name in (CUSTOMERS_QUARANTINE, LINES_QUARANTINE):
        counts[name] = quarantine_db[name].count_documents({NS_FIELD[name]: ns})
    return counts


def validators_present(db) -> dict:
    present = {}
    for info in db.list_collections():
        if info["name"] in CORE_COLLECTIONS:
            validator = info.get("options", {}).get("validator") or {}
            present[info["name"]] = "$jsonSchema" in validator
    return dict(sorted(present.items()))


# --------------------------------------------------------------------------- #
# status
# --------------------------------------------------------------------------- #


def cmd_status(args, cli) -> int:
    db, quarantine_db = databases(cli, args.ns)
    payload = {
        "namespace": args.ns,
        "database": db.name,
        "quarantine_database": quarantine_db.name,
        "counts": collection_counts(db, quarantine_db, args.ns),
        "validators": validators_present(db),
        "drift_journal": db[DRIFT_JOURNAL].count_documents({}),
        "generated_at": now(),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


# --------------------------------------------------------------------------- #
# validate-demo
# --------------------------------------------------------------------------- #

SHOWCASE_TAG = "tp_showcase_probe"


def _probe_id(ns: str, case: str) -> uuid.UUID:
    return uuid.uuid5(
        uuid.uuid5(uuid.NAMESPACE_URL, "https://otterworks.internal/tp/mongodb"),
        f"{ns}:showcase-probe:{case}",
    )


def customer_probes(ns: str) -> list[tuple[str, dict, bool]]:
    """(case, document, must_be_accepted) triples for the customers contract."""
    conforming = {
        "_id": _probe_id(ns, "customer-conforming"),
        "customer_id": "00000000-0000-0000-0000-0000000c0de1",
        "namespace": ns,
        "customer_no": f"{ns.upper()}-PROBE-01",
        "customer_name": "Probe Otter",
        "signup_dt": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "related_acct_ids": ["10001", "10002"],
        "promo_codes": ["SPRING24"],
        "balances": {"current_amount": Decimal128("10.00")},
        "source": {"table": "OW_BILLING.CUSTOMER_MASTER", "batch_no": fr.batch_no(ns)},
    }
    string_date = dict(conforming)
    string_date["_id"] = _probe_id(ns, "customer-string-date")
    string_date["customer_id"] = "00000000-0000-0000-0000-0000000c0de2"
    # the legacy estate stores SIGNUP_DT as DD-MON-YY text
    string_date["signup_dt"] = "31-FEB-24"
    rogue_field = dict(conforming)
    rogue_field["_id"] = _probe_id(ns, "customer-rogue-field")
    rogue_field["customer_id"] = "00000000-0000-0000-0000-0000000c0de3"
    # column 156, added by hand in 2019 and never in any schema
    rogue_field["tax_region_override"] = "see ticket 48213"
    csv_string = dict(conforming)
    csv_string["_id"] = _probe_id(ns, "customer-csv-string")
    csv_string["customer_id"] = "00000000-0000-0000-0000-0000000c0de4"
    csv_string["related_acct_ids"] = "10001,10002,NULL"
    return [
        ("conforming-document", conforming, True),
        ("legacy-dd-mon-yy-date", string_date, False),
        ("rogue-156th-field", rogue_field, False),
        ("legacy-csv-list-string", csv_string, False),
    ]


def invoice_probes(ns: str) -> list[tuple[str, dict, bool]]:
    line = {
        "line_id": "00000000-0000-0000-0000-00000000l1e1",
        "line_no": 1,
        "line_type_code": 1,
        "amount": Decimal128("10.00"),
        "tax_amt": Decimal128("0.83"),
        "qty": Decimal128("1"),
        "unit_price": Decimal128("10.00"),
    }
    conforming = {
        "_id": _probe_id(ns, "invoice-conforming"),
        "ns": ns,
        "invoice_no": f"{ns.upper()}-PROBE-01",
        "issue_date": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "lines_total": Decimal128("10.00"),
        "lines_tax_total": Decimal128("0.83"),
        "lines_count": 1,
        "lines": [line],
        "source": {
            "system": "oracle",
            "schema": "OW_BILLING",
            "table": "INVOICE_HEADER",
            "invoice_id": "__showcase_probe__",
        },
    }
    string_date = dict(conforming)
    string_date["_id"] = _probe_id(ns, "invoice-string-date")
    string_date["issue_date"] = "15-JAN-24"
    scalar_lines = dict(conforming)
    scalar_lines["_id"] = _probe_id(ns, "invoice-scalar-lines")
    # the legacy report flattened lines into a single text blob
    scalar_lines["lines"] = "1 x Monthly platform fee"
    return [
        ("conforming-document", conforming, True),
        ("legacy-dd-mon-yy-date", string_date, False),
        ("lines-not-an-array", scalar_lines, False),
    ]


def run_probes(collection, probes) -> list[dict]:
    results = []
    for case, document, must_accept in probes:
        outcome: dict = {"case": case, "expected": "accepted" if must_accept else
                         f"rejected: server error {DOCUMENT_VALIDATION_FAILURE}"}
        try:
            collection.insert_one(dict(document))
        except WriteError as exc:
            outcome["actual"] = f"rejected: server error {exc.code}"
            outcome["error"] = str(exc).splitlines()[0][:200]
        else:
            outcome["actual"] = "accepted"
            collection.delete_one({"_id": document["_id"]})
            outcome["cleaned_up"] = (
                collection.count_documents({"_id": document["_id"]}) == 0
            )
        outcome["result"] = "pass" if outcome["actual"] == outcome["expected"] else "fail"
        results.append(outcome)
    return results


def cmd_validate_demo(args, cli) -> int:
    db, _ = databases(cli, args.ns)
    validators = validators_present(db)
    missing = [name for name in (CUSTOMERS, INVOICES) if not validators.get(name)]
    if missing:
        print(json.dumps({
            "namespace": args.ns,
            "database": db.name,
            "result": "fail",
            "detail": f"no $jsonSchema validator on: {', '.join(missing)}",
            "validators": validators,
        }, indent=2, sort_keys=True))
        return 1

    before = {
        CUSTOMERS: db[CUSTOMERS].count_documents({"namespace": args.ns}),
        INVOICES: db[INVOICES].count_documents({"ns": args.ns}),
    }
    results = {
        CUSTOMERS: run_probes(db[CUSTOMERS], customer_probes(args.ns)),
        INVOICES: run_probes(db[INVOICES], invoice_probes(args.ns)),
    }
    after = {
        CUSTOMERS: db[CUSTOMERS].count_documents({"namespace": args.ns}),
        INVOICES: db[INVOICES].count_documents({"ns": args.ns}),
    }
    failures = [
        f"{collection}:{probe['case']}"
        for collection, probes in results.items()
        for probe in probes
        if probe["result"] == "fail"
    ]
    if before != after:
        failures.append("collection-counts-unchanged")
    payload = {
        "namespace": args.ns,
        "database": db.name,
        "validators": validators,
        "probes": results,
        "counts_before": before,
        "counts_after": after,
        "failing_probes": failures,
        "result": "pass" if not failures else "fail",
        "generated_at": now(),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.out:
        write_json(args.out, payload)
    return 0 if not failures else 1


# --------------------------------------------------------------------------- #
# report / baseline
# --------------------------------------------------------------------------- #


def golden_diff(golden: dict, actual: dict) -> list[dict]:
    """Report rows plus the balances rollup, compared against the legacy golden."""
    diffs = fr.report_diff(golden, actual)
    if golden.get("balances") != actual.get("balances"):
        diffs.append({
            "section": "balances",
            "key": [],
            "legacy": golden.get("balances"),
            "mongodb": actual.get("balances"),
        })
    return diffs


def print_report(payload: dict) -> None:
    print(f"# RPT-114 month-end finance — ns={payload['namespace']} "
          f"batch={payload['batch_no']} engine={payload['source']['engine']}")
    print(f"{'status':<12} {'invoices':>9} {'header_total_amt':>18}")
    for row in payload["by_status"]:
        print(f"{row['status']:<12} {row['invoice_count']:>9} "
              f"{row['header_total_amt'] or '-':>18}")
    print()
    print(f"{'status':<12} {'line_type':<12} {'lines':>8} {'amount':>16} "
          f"{'tax':>14} {'invoices':>9}")
    for row in payload["by_status_line_type"]:
        print(f"{row['status']:<12} {row['line_type']:<12} {row['line_count']:>8} "
              f"{row['line_amount']:>16} {row['line_tax']:>14} "
              f"{row['invoices_touched']:>9}")
    print()
    print("balances: " + json.dumps(payload["balances"], sort_keys=True))


def target_report(db, ns: str) -> dict:
    """The report exactly as the billing service serves it, plus the balances."""
    return {**fr.month_end_report(db, ns), "balances": fr.balances(db, ns)}


def cmd_report(args, cli) -> int:
    db, _ = databases(cli, args.ns)
    payload = target_report(db, args.ns)
    payload["generated_at"] = now()
    print_report(payload)
    exit_code = 0
    path = args.baseline or baseline_path(args.ns)
    if os.path.exists(path):
        golden = load_json(path)["legacy_report"]
        diffs = golden_diff(golden, payload)
        payload["golden_parity"] = {
            "baseline": os.path.relpath(path, REPO_ROOT),
            "differences": diffs,
            "result": "pass" if not diffs else "fail",
        }
        print()
        print("golden parity vs the legacy Oracle report: "
              + ("EXACT MATCH" if not diffs else f"{len(diffs)} difference(s)"))
        if diffs:
            print(json.dumps(diffs[:10], indent=2, sort_keys=True))
            exit_code = 1
    elif args.baseline:
        raise SystemExit(f"baseline not found: {args.baseline}")
    if args.out:
        write_json(args.out, payload)
    return exit_code


def fetch_legacy_report(base_url: str, path: str, ns: str) -> dict:
    url = f"{base_url.rstrip('/')}{path}?ns={ns}"
    with urllib.request.urlopen(url, timeout=120) as response:
        if response.status != 200:
            raise SystemExit(f"legacy report {url} returned HTTP {response.status}")
        return json.loads(response.read().decode())


def manifest_facts(ns: str) -> dict:
    path = os.path.join(MANIFEST_DIR, f"{ns}.json")
    if not os.path.exists(path):
        raise SystemExit(
            f"seed manifest {path} is missing; run `make seed-legacy NS={ns}` and "
            "`make oracle-billing-seed NS=" + ns + "` first"
        )
    with open(path, "rb") as handle:
        raw = handle.read()
    manifest = json.loads(raw.decode())
    return {
        "path": os.path.relpath(path, REPO_ROOT),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "seed": manifest.get("seed"),
        "targets": manifest.get("targets", {}),
        "planted_anomalies": manifest.get("planted_anomalies", []),
    }


def target_derived_manifest(db, quarantine_db, ns: str, counts: dict) -> dict:
    """A rehearsal stand-in for the immutable Oracle manifest.

    A rehearsal namespace has no legacy estate behind it, so there is no golden
    manifest to reconcile against. This records the target's own green state as
    the contract instead, which is what makes staged drift detectable: recon
    still recomputes every value from the target, it is simply reconciled
    against a self-captured baseline rather than the legacy source of truth.
    Never used for a namespace that has a manifest.
    """
    checksum, checksum_rows = customers_checksum(db, ns)
    line_checksum, _embedded, checksum_lines = invoice_line_checksum(
        db, quarantine_db, ns)
    return {
        "path": None,
        "sha256": None,
        "seed": None,
        "derived_from_target": True,
        "targets": {
            "oracle.OW_BILLING.CUSTOMER_MASTER": {
                "rows": checksum_rows,
                "checksum": checksum,
            },
            "oracle.OW_BILLING.INVOICE_HEADER": {"rows": counts[INVOICES]},
            "oracle.OW_BILLING.INVOICE_LINE": {
                "rows": checksum_lines,
                "checksum": line_checksum,
            },
        },
        "planted_anomalies": [
            {"kind": kind, "count": count, "target": "recomputed from the target"}
            for kind, count in (
                ("dirty_dates", quarantine_membership(quarantine_db, ns)["by_reason"]
                 .get("dirty_date", 0)),
                ("malformed_csv_lists", quarantine_membership(quarantine_db, ns)
                 ["by_reason"].get("malformed_csv_list", 0)),
                ("orphaned_rows", quarantine_membership(quarantine_db, ns)["by_reason"]
                 .get("orphan_no_header", 0)),
            )
        ],
    }


def cmd_baseline(args, cli) -> int:
    """Capture the golden before-state this namespace is reconciled against."""
    db, quarantine_db = databases(cli, args.ns)
    counts = collection_counts(db, quarantine_db, args.ns)
    quarantine = quarantine_membership(quarantine_db, args.ns)
    if args.from_target:
        if os.path.exists(os.path.join(MANIFEST_DIR, f"{args.ns}.json")):
            raise SystemExit(
                f"ns={args.ns} has an immutable seed manifest; capture its baseline "
                "from the legacy estate with --legacy-url instead of --from-target"
            )
        if args.ns in PERSISTENT_NAMESPACES:
            raise SystemExit(
                f"refusing to self-baseline the persistent namespace {args.ns}"
            )
        manifest = target_derived_manifest(db, quarantine_db, args.ns, counts)
        legacy_report = {
            "engine": {"engine": "none", "system": "rehearsal namespace: no legacy "
                                                 "estate behind it"},
            "url": None,
            **{key: value for key, value in target_report(db, args.ns).items()
               if key in ("by_status", "by_status_line_type", "balances")},
        }
    elif not args.legacy_url:
        raise SystemExit(
            "baseline needs --legacy-url <legacy-billing url> (or --from-target for a "
            "rehearsal namespace with no legacy estate)"
        )
    else:
        manifest = manifest_facts(args.ns)
        month_end = fetch_legacy_report(
            args.legacy_url, "/api/reports/month-end", args.ns)
        reconciliation = fetch_legacy_report(
            args.legacy_url, "/api/reports/reconciliation", args.ns
        )
        legacy_report = {
            "engine": month_end["source"],
            "url": f"{args.legacy_url.rstrip('/')}/api/reports/month-end?ns={args.ns}",
            "by_status": month_end["by_status"],
            "by_status_line_type": month_end["by_status_line_type"],
            "balances": reconciliation["balances"],
        }
    payload = {
        "kind": "mongo-showcase-baseline",
        "unit": UNIT,
        "namespace": args.ns,
        "captured_at": now(),
        "batch_no": fr.batch_no(args.ns),
        "manifest": manifest,
        "legacy_report": legacy_report,
        "target_state": {
            "counts": counts,
            "quarantine": quarantine,
            "provenance": {
                "manifest": (
                    "the target's own green state, self-captured for a rehearsal "
                    "namespace with no legacy estate: legacy parity is NOT proven "
                    "by this baseline"
                    if manifest.get("derived_from_target")
                    else "the immutable seed manifest recorded from the legacy estate"
                ),
                "customers": "row count and checksum are the Oracle manifest targets",
                "invoices": "row counts and the line checksum are the Oracle "
                            "manifest targets",
                "documents/document_snapshots/files": "captured from the target at "
                    "baseline time: the Postgres and DynamoDB manifest targets are "
                    "recorded by their own unit recons "
                    "(docs/tech-partnerships/recon/), not by this namespace manifest",
                "quarantine": "membership captured at the green baseline; the "
                    "per-unit recons prove it against the legacy estate",
            },
        },
    }
    path = args.out or baseline_path(args.ns)
    write_json(path, payload)
    # the app cannot read the repository, so the namespace carries its own copy
    # of the golden report: that is what the reconciliation endpoint compares
    # against when it decides whether to serve a green or a red banner
    db[fr.BASELINE_COLLECTION].replace_one(
        {"_id": fr.BASELINE_ID},
        {
            "_id": fr.BASELINE_ID,
            "namespace": args.ns,
            "captured_at": payload["captured_at"],
            "legacy_report": payload["legacy_report"],
            "counts": counts,
        },
        upsert=True,
    )
    print(json.dumps({
        "baseline": os.path.relpath(path, REPO_ROOT),
        "baseline_document": f"{db.name}.{fr.BASELINE_COLLECTION}",
        "namespace": args.ns,
        "manifest_sha256": manifest["sha256"],
        "legacy_report_rows": {
            "by_status": len(payload["legacy_report"]["by_status"]),
            "by_status_line_type": len(
                payload["legacy_report"]["by_status_line_type"]),
        },
        "counts": counts,
        "quarantine_by_reason": quarantine["by_reason"],
    }, indent=2, sort_keys=True))
    return 0


# --------------------------------------------------------------------------- #
# recon
# --------------------------------------------------------------------------- #


def planted_counts(manifest: dict) -> dict:
    counts: dict[str, int] = {}
    for anomaly in manifest.get("planted_anomalies", []):
        counts[anomaly["kind"]] = counts.get(anomaly["kind"], 0) + anomaly["count"]
    return dict(sorted(counts.items()))


def recon_report(cli, ns: str, baseline: dict, run_mode: str) -> dict:
    db, quarantine_db = databases(cli, ns)
    manifest = baseline["manifest"]
    targets = manifest["targets"]
    baseline_counts = baseline["target_state"]["counts"]
    checks: list[dict] = []

    counts = collection_counts(db, quarantine_db, ns)
    check(checks, "customers-count", targets["oracle.OW_BILLING.CUSTOMER_MASTER"]["rows"],
          counts[CUSTOMERS],
          "manifest CUSTOMER_MASTER rows vs customers documents counted in the target")
    check(checks, "invoices-count", targets["oracle.OW_BILLING.INVOICE_HEADER"]["rows"],
          counts[INVOICES],
          "manifest INVOICE_HEADER rows vs invoices documents counted in the target")

    checksum, checksum_rows = customers_checksum(db, ns)
    check(checks, "customers-checksum",
          targets["oracle.OW_BILLING.CUSTOMER_MASTER"]["checksum"], checksum,
          "manifest CUSTOMER_MASTER checksum vs md5 over "
          "<customer_id>:<current balance> recomputed from the target in key order")
    check(checks, "customers-checksum-coverage",
          targets["oracle.OW_BILLING.CUSTOMER_MASTER"]["rows"], checksum_rows,
          "documents fed into the recomputed customer checksum")

    line_checksum, embedded_lines, checksum_lines = invoice_line_checksum(
        db, quarantine_db, ns)
    expected_lines = (targets["oracle.OW_BILLING.INVOICE_LINE"]["rows"]
                      - counts[LINES_QUARANTINE])
    check(checks, "invoices-embedded-lines", expected_lines, embedded_lines,
          "manifest INVOICE_LINE rows minus the quarantined lines vs lines embedded "
          "in the invoice documents")
    check(checks, "invoice-lines-checksum",
          targets["oracle.OW_BILLING.INVOICE_LINE"]["checksum"], line_checksum,
          "manifest INVOICE_LINE checksum vs md5 over <line_id>:<amount> recomputed "
          "from the embedded lines plus the quarantined lines")
    check(checks, "invoice-lines-checksum-coverage",
          targets["oracle.OW_BILLING.INVOICE_LINE"]["rows"], checksum_lines,
          "lines fed into the recomputed invoice-line checksum")

    quarantine = quarantine_membership(quarantine_db, ns)
    check(checks, "quarantine-membership",
          {"missing": [], "unexpected": []},
          {
              "missing": sorted(
                  set(baseline["target_state"]["quarantine"]["ids"])
                  - set(quarantine["ids"]))[:20],
              "unexpected": sorted(
                  set(quarantine["ids"])
                  - set(baseline["target_state"]["quarantine"]["ids"]))[:20],
          },
          "quarantine ids captured at the green baseline vs quarantine ids "
          "recomputed from the target now, compared as sets")
    check(checks, "planted-anomaly-counts",
          {"dirty_dates": planted_counts(manifest).get("dirty_dates", 0),
           "malformed_csv_lists":
               planted_counts(manifest).get("malformed_csv_lists", 0),
           "orphaned_rows": planted_counts(manifest).get("orphaned_rows", 0)},
          {"dirty_dates": quarantine["by_reason"].get("dirty_date", 0),
           "malformed_csv_lists": quarantine["by_reason"].get("malformed_csv_list", 0),
           "orphaned_rows": quarantine["by_reason"].get("orphan_no_header", 0)},
          "manifest planted anomaly counts vs quarantine reasons recomputed from the "
          "target")

    for collection in (DOCUMENTS, SNAPSHOTS, FILES):
        check(checks, f"{collection.replace('_', '-')}-count",
              baseline_counts[collection], counts[collection],
              f"{collection} documents captured at the green baseline vs counted in "
              "the target now")

    check(checks, "money-bson-type", 0, fr.non_decimal_money(db, ns),
          "count of embedded money and quantity fields whose stored BSON type is not "
          "decimal128")

    validators = validators_present(db)
    check(checks, "validators-applied", {CUSTOMERS: True, INVOICES: True},
          {CUSTOMERS: validators.get(CUSTOMERS, False),
           INVOICES: validators.get(INVOICES, False)},
          "$jsonSchema presence read back from the collections' options")
    probe = run_probes(db[INVOICES], [
        p for p in invoice_probes(ns) if p[0] == "legacy-dd-mon-yy-date"])[0]
    check(checks, "validator-rejects-legacy-date",
          f"rejected: server error {DOCUMENT_VALIDATION_FAILURE}", probe["actual"],
          "live insert of an invoice carrying the legacy DD-MON-YY string issue date")

    report = target_report(db, ns)
    diffs = golden_diff(baseline["legacy_report"], report)
    check(checks, "report-golden-parity", [], diffs[:10],
          "RPT-114 month-end report from the legacy Oracle estate vs the same report "
          "produced by one aggregation pipeline over the migrated invoices, compared "
          "row by row to the cent")

    second_pass = target_report(db, ns)
    repeatable = golden_diff(second_pass, report) == [] and customers_checksum(
        db, ns)[0] == checksum
    failures = [entry["id"] for entry in checks if entry["result"] == "fail"]
    unverified = [
        ("Postgres document and DynamoDB file manifest targets are reconciled by "
         "their own unit recons; this report compares those collections against the "
         "green baseline capture only"),
    ]
    if manifest.get("derived_from_target"):
        unverified.append(
            "this namespace has no legacy estate: its baseline was self-captured from "
            "the target, so every check proves drift from the captured green state "
            "and none of them proves parity with the legacy source of truth"
        )
    return {
        "kind": "recon-report",
        "unit": UNIT,
        "namespace": ns,
        "generated_at": now(),
        "run_mode": run_mode,
        "result": "pass" if not failures else "fail",
        "failed_checks": failures,
        "checks": checks,
        "values_recomputed_from_target": True,
        "idempotency_rerun": {
            "performed": True,
            "result": "pass" if repeatable else "fail",
            "evidence": "the report pipeline and the customer checksum were "
                        "recomputed a second time against the target in the same run "
                        "and returned identical values",
        },
        "planted_anomaly_detections": {
            "expected_set": baseline["target_state"]["quarantine"]["ids"],
            "actual_set": quarantine["ids"],
            "missing": sorted(set(baseline["target_state"]["quarantine"]["ids"])
                              - set(quarantine["ids"])),
            "unexpected": sorted(set(quarantine["ids"])
                                 - set(baseline["target_state"]["quarantine"]["ids"])),
        },
        "unverified_paths": unverified,
        "source": {
            "baseline": baseline.get("manifest", {}).get("path"),
            "manifest_sha256": manifest["sha256"],
            "legacy_report": baseline["legacy_report"]["url"],
        },
        "target": {
            "database": db.name,
            "quarantine_database": quarantine_db.name,
            "counts": counts,
            "customers_checksum": checksum,
            "invoice_lines_checksum": line_checksum,
            "report": report,
        },
    }


def load_baseline(args) -> dict:
    path = args.baseline or baseline_path(args.ns)
    if not os.path.exists(path):
        raise SystemExit(
            f"no showcase baseline for ns={args.ns} at {path}; capture one with "
            f"`showcase.py --ns {args.ns} baseline --legacy-url <legacy-billing url>`"
        )
    return load_json(path)


def cmd_recon(args, cli) -> int:
    report = recon_report(cli, args.ns, load_baseline(args), args.run_mode)
    path = args.out or recon_path(args.ns)
    write_json(path, report)
    print(json.dumps({
        "namespace": args.ns,
        "result": report["result"],
        "failed_checks": report["failed_checks"],
        "checks": len(report["checks"]),
        "report": os.path.relpath(path, REPO_ROOT),
        "counts": report["target"]["counts"],
    }, indent=2, sort_keys=True))
    for entry in report["checks"]:
        if entry["result"] == "fail":
            print(f"FAIL {entry['id']}: expected {json.dumps(entry['expected'])[:200]} "
                  f"actual {json.dumps(entry['actual'])[:200]}", file=sys.stderr)
    return 0 if report["result"] == "pass" else 1


# --------------------------------------------------------------------------- #
# run-job: recon + failure notification
# --------------------------------------------------------------------------- #


def notify(webhook_url: str, payload: dict) -> dict:
    secret = os.getenv(WEBHOOK_SECRET_ENV)
    if not secret:
        raise SystemExit(
            f"{WEBHOOK_SECRET_ENV} is not set; the recon failure cannot be signalled "
            "(the secret is never inlined in the repository)"
        )
    if not webhook_url.startswith("https://"):
        raise SystemExit("refusing to POST the recon failure over a non-HTTPS webhook")
    request = urllib.request.Request(
        webhook_url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "X-Webhook-Secret": secret},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode()[:400]
            return {"status": response.status, "body": body}
    except urllib.error.HTTPError as exc:
        return {"status": exc.code, "body": exc.read().decode()[:400]}


def cmd_run_job(args, cli) -> int:
    report = recon_report(cli, args.ns, load_baseline(args), args.run_mode)
    path = args.out or recon_path(args.ns)
    write_json(path, report)
    summary = {
        "namespace": args.ns,
        "result": report["result"],
        "failed_checks": report["failed_checks"],
        "report": os.path.relpath(path, REPO_ROOT),
        "run_url": args.run_url,
        "notified": False,
    }
    if report["result"] == "pass":
        summary["notification"] = "not fired: reconciliation is green"
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    webhook_url = args.webhook_url or os.getenv(WEBHOOK_URL_ENV)
    if not webhook_url:
        summary["notification"] = (
            f"not fired: no webhook url (pass --webhook-url or set {WEBHOOK_URL_ENV})")
        print(json.dumps(summary, indent=2, sort_keys=True), file=sys.stderr)
        return 1
    payload = {
        "namespace": args.ns,
        "failing_checks": report["failed_checks"],
        "run_url": args.run_url,
        "base_branch": args.base_branch,
    }
    if args.dry_run:
        summary["notification"] = "dry run: webhook not called"
        summary["payload"] = payload
        print(json.dumps(summary, indent=2, sort_keys=True), file=sys.stderr)
        return 1
    response = notify(webhook_url, payload)
    summary["notified"] = 200 <= response["status"] < 300
    summary["notification"] = f"POST {webhook_url.split('/api/')[0]}/… -> HTTP " \
                              f"{response['status']}"
    summary["payload"] = payload
    summary["response"] = response
    print(json.dumps(summary, indent=2, sort_keys=True), file=sys.stderr)
    return 1


# --------------------------------------------------------------------------- #
# drift: stage a real failure in a rehearsal namespace
# --------------------------------------------------------------------------- #


def journal(db, ns: str, kind: str, detail: dict) -> None:
    db[DRIFT_JOURNAL].insert_one({
        "_id": f"{ns}:{kind}:{now()}",
        "ns": ns,
        "kind": kind,
        "staged_at": now(),
        "detail": detail,
        "note": "staged by scripts/tp_mongo/showcase.py drift for the recon failure "
                "demo; remediate by re-running the idempotent migration for this "
                "namespace",
    })


def drift_missing(db, ns: str, count: int) -> dict:
    ids = [doc["_id"] for doc in db[INVOICES]
           .find({"ns": ns}, {"_id": 1, "invoice_no": 1})
           .sort("invoice_no", 1).limit(count)]
    numbers = [doc["invoice_no"] for doc in db[INVOICES]
               .find({"_id": {"$in": ids}}, {"invoice_no": 1})]
    deleted = db[INVOICES].delete_many({"_id": {"$in": ids}}).deleted_count
    return {"deleted_invoices": deleted, "invoice_nos": sorted(numbers)}


def drift_corrupt(db, ns: str, count: int) -> dict:
    touched = []
    cursor = (db[INVOICES]
              .find({"ns": ns, "lines.0": {"$exists": True}},
                    {"_id": 1, "invoice_no": 1, "lines.line_id": 1, "lines.amount": 1})
              .sort("invoice_no", 1).limit(count))
    for doc in cursor:
        line = doc["lines"][0]
        corrupted = decimal_of(line["amount"]) + Decimal("1.11")
        db[INVOICES].update_one(
            {"_id": doc["_id"]},
            {"$set": {"lines.0.amount": Decimal128(f"{corrupted:.2f}")}},
        )
        touched.append({
            "invoice_no": doc["invoice_no"],
            "line_id": line["line_id"],
            "was": f"{decimal_of(line['amount']):.2f}",
            "now": f"{corrupted:.2f}",
        })
    return {"corrupted_lines": len(touched), "lines": touched}


def drift_stale(db, ns: str, count: int) -> dict:
    """Roll a slice of customers back to a pre-migration balance snapshot."""
    touched = []
    cursor = (db[CUSTOMERS]
              .find({"namespace": ns},
                    {"_id": 1, "customer_id": 1, "balances.current_amount": 1})
              .sort("customer_id", 1).limit(count))
    for doc in cursor:
        amount = decimal_of(doc["balances"]["current_amount"])
        stale = amount / 2
        db[CUSTOMERS].update_one(
            {"_id": doc["_id"]},
            {"$set": {"balances.current_amount": Decimal128(f"{stale:.2f}")}},
        )
        touched.append({
            "customer_id": doc["customer_id"],
            "was": f"{amount:.2f}",
            "now": f"{stale:.2f}",
        })
    return {"staled_customers": len(touched), "customers": touched}


DRIFT_KINDS = {"stale": drift_stale, "corrupt": drift_corrupt, "missing": drift_missing}


def cmd_drift(args, cli) -> int:
    if args.ns in PERSISTENT_NAMESPACES:
        raise SystemExit(
            f"refusing to drift persistent namespace {args.ns!r}: the demo keeps it "
            "green and browsable (override the list with TP_MONGO_PERSISTENT_NS)"
        )
    db, _ = databases(cli, args.ns)
    if db[INVOICES].count_documents({"ns": args.ns}, limit=1) == 0:
        raise SystemExit(f"namespace {args.ns!r} has no migrated invoices to drift")
    detail = DRIFT_KINDS[args.kind](db, args.ns, args.count)
    journal(db, args.ns, args.kind, detail)
    payload = {
        "namespace": args.ns,
        "database": db.name,
        "kind": args.kind,
        "detail": detail,
        "staged_at": now(),
        "next": f"scripts/tp_mongo/showcase.py --ns {args.ns} run-job",
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


# --------------------------------------------------------------------------- #


COMMANDS = {
    "status": cmd_status,
    "validate-demo": cmd_validate_demo,
    "seed-fixture": cmd_seed_fixture,
    "report": cmd_report,
    "baseline": cmd_baseline,
    "recon": cmd_recon,
    "run-job": cmd_run_job,
    "drift": cmd_drift,
}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ns", required=True, help="demo namespace, e.g. demo")
    parser.add_argument("--run-mode", choices=["live", "fixture"], default="live",
                        help="live uses MONGODB_ATLAS_URI, fixture uses "
                             "TP_MONGO_FIXTURE_URI")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="counts, validators and drift journal")
    sub.add_parser("seed-fixture", help="seed a deterministic local fixture namespace")

    validate = sub.add_parser("validate-demo",
                              help="prove the $jsonSchema validators live")
    validate.add_argument("--out", help="write the probe evidence to this path")

    report = sub.add_parser("report", help="RPT-114 as one aggregation pipeline")
    report.add_argument("--baseline", help="golden baseline to diff against")
    report.add_argument("--out", help="write the report JSON to this path")

    baseline = sub.add_parser("baseline", help="capture the golden before-state")
    baseline.add_argument("--legacy-url",
                          help="legacy-billing base url serving the Oracle report")
    baseline.add_argument("--from-target", action="store_true",
                          help="rehearsal namespaces only: capture the target's own "
                               "green state instead of the legacy golden report")
    baseline.add_argument("--out")

    recon = sub.add_parser("recon", help="recompute every baseline check from target")
    recon.add_argument("--baseline")
    recon.add_argument("--out")

    job = sub.add_parser("run-job", help="recon, and POST failures to Devin")
    job.add_argument("--baseline")
    job.add_argument("--out")
    job.add_argument("--webhook-url", help=f"defaults to ${WEBHOOK_URL_ENV}")
    job.add_argument("--run-url", default="", help="CI or local run url for the audit")
    job.add_argument("--base-branch", required=True,
                     help="branch the remediation PR must target")
    job.add_argument("--dry-run", action="store_true",
                     help="report what would be POSTed without calling the webhook")

    drift = sub.add_parser("drift", help="stage real drift in a rehearsal namespace")
    drift.add_argument("--kind", choices=sorted(DRIFT_KINDS), required=True)
    drift.add_argument("--count", type=int, default=25)

    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    common._validate_ns(args.ns)
    cli = client(args)
    try:
        return COMMANDS[args.command](args, cli)
    finally:
        cli.close()


if __name__ == "__main__":
    raise SystemExit(main())
