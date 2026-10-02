from datetime import date, datetime, timezone
from decimal import Decimal
import sys
from pathlib import Path

from oracle_custbill_extract import (
    ADMIN_TENANT_ID,
    MONGO_EXTRACT_PIPELINE,
    extract,
    format_record,
    mongo_mode,
    mongo_pipeline,
    ns_batch_no,
    sort_rows,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "services/legacy-billing/app"))
from reports import ns_batch_no as report_ns_batch_no


def test_batch_number_matches_reports():
    assert ns_batch_no("demo") == report_ns_batch_no("demo")
    assert ns_batch_no("rehearsal1") == report_ns_batch_no("rehearsal1")


def test_format_record_truncates_and_pads_legacy_columns():
    record = format_record({
        "invoice_id": "invoice-1",
        "cust_no": "CUSTOMER-TOO-LONG",
        "cust_name": "A" * 40,
        "period_end": date(2026, 2, 28),
        "total_amt": Decimal("12.345"),
        "record_type": "01",
    })
    assert len(record) == 65
    assert record[:10] == "CUSTOMER-T"
    assert record[10:40] == "A" * 30
    assert record[40:48] == "20260228"
    assert record[48:60] == "000000001235"
    assert record[60:] == "USD01"


def test_format_record_uses_credit_code_for_negative_amount():
    record = format_record({
        "invoice_id": "credit-1",
        "cust_no": "C1",
        "cust_name": "Credit",
        "period_end": "2026-03-01",
        "total_amt": "-2.50",
        "record_type": "01",
    })
    assert record[48:60] == "000000000250"
    assert record[63:] == "02"


def test_format_record_transliterates_non_ascii_fields():
    record = format_record({
        "invoice_id": "invoice-1",
        "cust_no": "C-1",
        "cust_name": "José Ltd",
        "period_end": date(2026, 3, 1),
        "total_amt": "2.50",
    })
    assert record[:10] == "C-1       "
    assert record[10:40].startswith("Jose? Ltd")


def test_format_record_rejects_amount_overflow():
    import pytest

    with pytest.raises(ValueError, match="invoice overflow-1 total exceeds CUSTBILL amount field"):
        format_record({
            "invoice_id": "overflow-1",
            "cust_no": "C1",
            "cust_name": "Large",
            "period_end": date(2026, 3, 1),
            "total_amt": "10000000000.00",
        })


def test_rows_are_sorted_by_period_customer_and_invoice():
    rows = [
        {"invoice_id": "b", "cust_no": "C2", "period_end": "2026-02-01"},
        {"invoice_id": "a", "cust_no": "C1", "period_end": "2026-02-02"},
        {"invoice_id": "a", "cust_no": "C1", "period_end": "2026-02-01"},
    ]
    assert [row["invoice_id"] for row in sort_rows(rows)] == ["a", "b", "a"]


class FakeFeed:
    def __init__(self, docs):
        self.docs, self.pipelines = docs, []

    def aggregate(self, pipeline):
        self.pipelines.append(pipeline)
        return iter(self.docs)


class FakeDatabase:
    def __init__(self, docs):
        self.invoice_feed = FakeFeed(docs)


def test_mongo_pipeline_selects_namespace_batch_and_joins_customers():
    pipeline = mongo_pipeline("demo")
    assert pipeline[0] == {"$match": {"$or": [{"batchNo": ns_batch_no("demo")}, {"tenantId": ADMIN_TENANT_ID}]}}
    lookup = next(stage["$lookup"] for stage in pipeline if "$lookup" in stage)
    assert (lookup["from"], lookup["localField"], lookup["foreignField"]) == ("customers", "custId", "_id")
    project = pipeline[-1]["$project"]
    assert set(project) == {"_id", "invoice_id", "cust_no", "cust_name", "period_end", "total_amt"}
    assert MONGO_EXTRACT_PIPELINE[0]["$match"]["$or"][0] == {"batchNo": None}, "the template is never mutated"


class Decimal128Like:
    """What pymongo hands back for a Decimal128 field: an object whose str() is the decimal text."""

    def __init__(self, text):
        self.text = text

    def __str__(self):
        return self.text


def test_extract_from_mongo_writes_the_same_records_as_oracle(tmp_path, monkeypatch):
    rows = [
        {"invoice_id": "B", "cust_no": "C-2", "cust_name": "Zoë Ltd", "period_end": datetime(2026, 1, 31, tzinfo=timezone.utc), "total_amt": Decimal128Like("-12.345")},
        {"invoice_id": "A", "cust_no": "C-1", "cust_name": "Acme", "period_end": datetime(2026, 1, 31, tzinfo=timezone.utc), "total_amt": Decimal128Like("100.10")},
    ]
    monkeypatch.setenv("BILLING_BACKEND", "mongo")
    destination, count = extract("demo", tmp_path, database=FakeDatabase(rows))
    assert destination.name == "CUSTBILL_DEMO_ORACLE.dat" and count == 2
    records = destination.read_bytes().split(b"\n")[:-1]
    assert all(len(record) == 65 for record in records)
    expected = [
        format_record({"invoice_id": "A", "cust_no": "C-1", "cust_name": "Acme", "period_end": date(2026, 1, 31), "total_amt": Decimal("100.10"), "record_type": "01"}),
        format_record({"invoice_id": "B", "cust_no": "C-2", "cust_name": "Zoë Ltd", "period_end": date(2026, 1, 31), "total_amt": Decimal("-12.345"), "record_type": "02"}),
    ]
    assert [record.decode("ascii") for record in records] == expected
    assert records[1][-2:] == b"02" and records[0][-2:] == b"01" and b"Zoe" in records[1]


def test_oracle_stays_the_source_unless_backend_is_mongo(tmp_path, monkeypatch):
    monkeypatch.delenv("BILLING_BACKEND", raising=False)
    assert mongo_mode() is False
    monkeypatch.setenv("BILLING_BACKEND", "mongo")
    assert mongo_mode() is True
    monkeypatch.setenv("BILLING_BACKEND", "oracle")
    assert mongo_mode() is False
