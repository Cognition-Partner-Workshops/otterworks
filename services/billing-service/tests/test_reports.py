"""RPT-114 over the migrated documents, checked against an independent rollup.

The pipeline in ``app.reports`` is the only implementation the app and the
migration recon share, so these tests never assert hand-written totals: they
build a fixture estate, aggregate it a second time in plain Python (the same
rules the legacy SQL spelled out), and require the two to agree to the cent.

The fixture is seeded into the compose document store
(``docker-compose.procs.yml`` service ``billing-service-docs``), never a live
Atlas target. Set ``TP_REQUIRE_DOCUMENT_FIXTURE=1`` to turn "no fixture
reachable" into a failure instead of a skip, which is what CI does once the
fixture is up.
"""

from __future__ import annotations

import os
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from bson.decimal128 import Decimal128
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from app.reports import (
    INV_STATUS,
    LINE_TYPES,
    balances,
    batch_no,
    estate_database_name,
    month_end_report,
    non_decimal_money,
    report_diff,
)

FIXTURE_NS = "reportfx"
FIXTURE_URI = os.getenv(
    "BILLING_SVC_DOCUMENT_URI", "mongodb://localhost:57432/?directConnection=true"
)
# statuses and line types the fixture exercises, including codes the legacy
# CODES table never mapped (rendered UNKNOWN(<cd>)) and a NULL header total
STATUS_CODES = [10, 20, 30, 40, 99]
LINE_TYPE_CODES = [1, 2, 3, 9, 7]


def money(value: str) -> Decimal128:
    return Decimal128(Decimal(value))


def fixture_invoices(ns: str) -> list[dict]:
    """A deterministic estate slice in the shape mongo_invoices migrates to."""
    docs = []
    for index, status_code in enumerate(STATUS_CODES):
        for repeat in range(2):
            seq = index * 2 + repeat
            lines = []
            for line_no, line_type in enumerate(LINE_TYPE_CODES, start=1):
                # amounts differ per line so a mis-grouped row cannot pass
                amount = Decimal(f"{100 + seq * 10 + line_no}.{(line_no * 7) % 100:02d}")
                lines.append({
                    "line_id": f"{ns}-{seq}-{line_no}",
                    "line_no": line_no,
                    "line_type_code": line_type,
                    "item_desc": f"line {line_no}",
                    "qty": money("2.00"),
                    "unit_price": money(f"{amount / 2:.2f}"),
                    "amount": money(f"{amount:.2f}"),
                    "tax_amt": money(f"{amount * Decimal('0.0825'):.2f}"),
                })
            lines_total = sum(line["amount"].to_decimal() for line in lines)
            tax_total = sum(line["tax_amt"].to_decimal() for line in lines)
            # every second invoice carries the legacy NULL total_amt
            header_total = None if repeat else money(f"{lines_total:.2f}")
            docs.append({
                "_id": uuid.uuid5(uuid.NAMESPACE_URL, f"{ns}:{seq}"),
                "ns": ns,
                "invoice_no": f"INV-{seq:04d}",
                "issue_date": datetime(2026, 1, 1 + seq, tzinfo=UTC),
                "due_date": datetime(2026, 2, 1 + seq, tzinfo=UTC),
                "status_code": status_code,
                "header_total": header_total,
                "lines_total": money(f"{lines_total:.2f}"),
                "lines_tax_total": money(f"{tax_total:.2f}"),
                "lines_count": len(lines),
                "header_total_matches_lines": header_total is not None,
                "customer": {"cust_id": f"CUST-{seq}", "tenant_id": "t1"},
                "source": {
                    "system": "oracle",
                    "table": "OW_BILLING.INVOICE_HEADER",
                    "invoice_id": f"INVH-{seq}",
                    "invoice_no": f"INV-{seq:04d}",
                    "batch_no": batch_no(ns),
                },
                "lines": lines,
            })
    # a document from another batch: the report must not see it
    other = dict(docs[0])
    other["_id"] = uuid.uuid5(uuid.NAMESPACE_URL, f"{ns}:other-batch")
    other["source"] = {**docs[0]["source"], "batch_no": batch_no(ns) + 1}
    docs.append(other)
    return docs


def fixture_customers(ns: str) -> list[dict]:
    docs = []
    for seq in range(5):
        docs.append({
            "_id": uuid.uuid5(uuid.NAMESPACE_URL, f"{ns}:cust:{seq}"),
            "namespace": ns,
            "customer_id": f"CUST-{seq}",
            "balances": {
                "current_amount": money(f"{100 + seq}.55"),
                "past_due_amount": money(f"{seq}.05"),
            },
            "source": {"batch_no": batch_no(ns)},
        })
    other = dict(docs[0])
    other["_id"] = uuid.uuid5(uuid.NAMESPACE_URL, f"{ns}:cust:other-batch")
    other["source"] = {"batch_no": batch_no(ns) + 1}
    docs.append(other)
    return docs


def decode(code: int | None, codes: dict[int, str]) -> str:
    """The legacy DECODE/CODES lookup, spelled out independently."""
    if code in codes:
        return codes[code]
    return f"UNKNOWN({'' if code is None else code})"


def expected_month_end(docs: list[dict], ns: str) -> dict:
    """The RPT-114 rollup computed without MongoDB."""
    rows = [doc for doc in docs if doc["source"]["batch_no"] == batch_no(ns)]
    by_status: dict[str, dict] = defaultdict(
        lambda: {"invoice_count": 0, "total": Decimal("0"), "present": 0}
    )
    lines: dict[tuple[str, str], dict] = defaultdict(
        lambda: {
            "line_count": 0,
            "amount": Decimal("0"),
            "tax": Decimal("0"),
            "invoices": set(),
        }
    )
    for doc in rows:
        status = decode(doc["status_code"], INV_STATUS)
        bucket = by_status[status]
        bucket["invoice_count"] += 1
        if doc["header_total"] is not None:
            bucket["total"] += doc["header_total"].to_decimal()
            bucket["present"] += 1
        for line in doc["lines"]:
            key = (status, decode(line["line_type_code"], LINE_TYPES))
            entry = lines[key]
            entry["line_count"] += 1
            entry["amount"] += line["amount"].to_decimal()
            entry["tax"] += line["tax_amt"].to_decimal()
            entry["invoices"].add(doc["_id"])
    return {
        "by_status": [
            {
                "status": status,
                "invoice_count": bucket["invoice_count"],
                "header_total_amt": (
                    f"{bucket['total']:.2f}" if bucket["present"] else None
                ),
            }
            for status, bucket in sorted(by_status.items())
        ],
        "by_status_line_type": [
            {
                "status": status,
                "line_type": line_type,
                "line_count": entry["line_count"],
                "line_amount": f"{entry['amount']:.2f}",
                "line_tax": f"{entry['tax']:.2f}",
                "invoices_touched": len(entry["invoices"]),
            }
            for (status, line_type), entry in sorted(lines.items())
        ],
    }


@pytest.fixture(scope="module")
def estate_db():
    try:
        client = MongoClient(
            FIXTURE_URI, uuidRepresentation="standard", serverSelectionTimeoutMS=3000
        )
        client.admin.command("ping")
    except PyMongoError as error:
        if os.getenv("TP_REQUIRE_DOCUMENT_FIXTURE"):
            raise
        pytest.skip(f"no document-store fixture at {FIXTURE_URI}: {error}")
    if "mongodb.net" in FIXTURE_URI:
        raise AssertionError("refusing to seed report fixtures into a shared cluster")
    database = client[estate_database_name(FIXTURE_NS)]
    database["invoices"].delete_many({"ns": FIXTURE_NS})
    database["customers"].delete_many({"namespace": FIXTURE_NS})
    database["invoices"].insert_many(fixture_invoices(FIXTURE_NS))
    database["customers"].insert_many(fixture_customers(FIXTURE_NS))
    yield database
    database["invoices"].delete_many({"ns": FIXTURE_NS})
    database["customers"].delete_many({"namespace": FIXTURE_NS})


def test_month_end_matches_an_independent_rollup(estate_db) -> None:
    report = month_end_report(estate_db, FIXTURE_NS)
    expected = expected_month_end(fixture_invoices(FIXTURE_NS), FIXTURE_NS)

    assert report["report"] == "month-end-finance"
    assert report["namespace"] == FIXTURE_NS
    assert report["batch_no"] == batch_no(FIXTURE_NS)
    assert report["source"]["engine"] == "mongodb"
    assert report_diff(expected, report) == []


def test_month_end_renders_unmapped_codes_like_the_legacy_report(estate_db) -> None:
    report = month_end_report(estate_db, FIXTURE_NS)
    statuses = {row["status"] for row in report["by_status"]}
    line_types = {row["line_type"] for row in report["by_status_line_type"]}

    assert "UNKNOWN(99)" in statuses
    assert statuses >= set(INV_STATUS.values())
    assert "UNKNOWN(7)" in line_types


def test_month_end_reports_null_header_totals_as_null(estate_db) -> None:
    # SUM() over an all-NULL group is NULL in Oracle, and the migrated report
    # keeps that: only groups with no header total at all render as null.
    estate_db["invoices"].update_many(
        {"ns": FIXTURE_NS, "status_code": 10}, {"$set": {"header_total": None}}
    )
    try:
        rows = {row["status"]: row for row in month_end_report(
            estate_db, FIXTURE_NS)["by_status"]}
        assert rows["draft"]["header_total_amt"] is None
        assert rows["paid"]["header_total_amt"] is not None
    finally:
        for doc in fixture_invoices(FIXTURE_NS):
            estate_db["invoices"].update_one(
                {"_id": doc["_id"]}, {"$set": {"header_total": doc["header_total"]}}
            )


def test_balances_and_money_typing_come_from_the_documents(estate_db) -> None:
    rollup = balances(estate_db, FIXTURE_NS)
    docs = [
        doc
        for doc in fixture_customers(FIXTURE_NS)
        if doc["source"]["batch_no"] == batch_no(FIXTURE_NS)
    ]
    current = sum(doc["balances"]["current_amount"].to_decimal() for doc in docs)
    past_due = sum(doc["balances"]["past_due_amount"].to_decimal() for doc in docs)

    assert rollup == {
        "customer_count": len(docs),
        "current_balance_total": f"{current:.2f}",
        "past_due_total": f"{past_due:.2f}",
    }
    assert non_decimal_money(estate_db, FIXTURE_NS) == 0


def test_report_diff_names_the_rows_that_disagree() -> None:
    golden = {
        "by_status": [{"status": "paid", "invoice_count": 2,
                       "header_total_amt": "10.00"}],
        "by_status_line_type": [],
    }
    actual = {
        "by_status": [{"status": "paid", "invoice_count": 2,
                       "header_total_amt": "10.01"}],
        "by_status_line_type": [],
    }

    assert report_diff(golden, golden) == []
    diff = report_diff(golden, actual)
    assert len(diff) == 1
    assert diff[0]["section"] == "by_status"
    assert diff[0]["key"] == ["paid"]
    assert diff[0]["legacy"]["header_total_amt"] == "10.00"
    assert diff[0]["mongodb"]["header_total_amt"] == "10.01"


def test_batch_no_matches_the_legacy_namespace_batch() -> None:
    # services/legacy-billing/app/reports.ns_batch_no, independently spelled out
    import hashlib

    for ns in ("demo", "ci", FIXTURE_NS):
        seed = int(hashlib.sha256(ns.encode()).hexdigest()[:8], 16)
        assert batch_no(ns) == seed % 90_000_000 + 1_000_000


def test_estate_database_name_is_namespace_scoped() -> None:
    assert estate_database_name("demo") == "ow_tp_mongodb_demo"
    with pytest.raises(ValueError):
        estate_database_name("../other")
