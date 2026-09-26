from datetime import date
from decimal import Decimal
import sys
from pathlib import Path

from oracle_custbill_extract import format_record, ns_batch_no, sort_rows

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


def test_mongo_rows_shapes_documents():
    from datetime import datetime
    from decimal import Decimal

    from oracle_custbill_extract import mongo_rows

    docs = [
        {
            "invoice_id": "inv-1",
            "cust_no": "C1",
            "cust_name": "Acme",
            "period_end": datetime(2026, 2, 28),
            "total_amt": Decimal("12.50"),
        },
        {
            "invoice_id": "inv-2",
            "cust_no": "C2",
            "cust_name": "Beta",
            "period_end": datetime(2026, 3, 1),
            "total_amt": Decimal("-2.50"),
        },
    ]

    class FakeDB:
        def __getitem__(self, name):
            assert name == "invoiceHeader"

            class C:
                def aggregate(self, pipeline):
                    assert pipeline[0]["$match"]["$or"][0]["batchNo"] == ns_batch_no("demo")
                    return iter(docs)

            return C()

    rows = mongo_rows(FakeDB(), "demo")
    assert rows[0]["record_type"] == "01"
    assert rows[1]["record_type"] == "02"
    assert rows[1]["total_amt"] == Decimal("-2.50")
    record = format_record(rows[0])
    assert len(record) == 65
    assert record[40:48] == "20260228"


def test_extract_mongo_writes_file_without_oracle(tmp_path, monkeypatch):
    import pytest

    pytest.importorskip("pymongo")
    import oracle_custbill_extract as extract_module

    rows = [
        {
            "invoice_id": "inv-1",
            "cust_no": "C1",
            "cust_name": "Acme",
            "period_end": "2026-02-28",
            "total_amt": "12.50",
            "record_type": "01",
        }
    ]
    monkeypatch.setattr(extract_module, "mongo_rows", lambda db, ns: rows)

    def no_oracle(**kwargs):
        raise AssertionError("Oracle must not be opened on the mongo backend")

    monkeypatch.setattr(extract_module.oracledb, "connect", no_oracle)
    destination, count = extract_module.extract("demo", tmp_path, backend="mongo")
    assert count == 1
    assert destination.name == "CUSTBILL_DEMO_ORACLE.dat"
    text = destination.read_text(encoding="ascii")
    assert len(text.splitlines()) == 1
    assert len(text.splitlines()[0]) == 65


def test_format_record_fails_closed_on_missing_invoice_dt():
    import pytest

    from oracle_custbill_extract import format_record

    with pytest.raises(ValueError, match="invoice x-1 has no invoiceDt"):
        format_record(
            {
                "invoice_id": "x-1",
                "cust_no": "C1",
                "cust_name": "Acme",
                "period_end": None,
                "total_amt": "1.00",
            }
        )


def test_rows_are_sorted_by_period_customer_and_invoice():
    rows = [
        {"invoice_id": "b", "cust_no": "C2", "period_end": "2026-02-01"},
        {"invoice_id": "a", "cust_no": "C1", "period_end": "2026-02-02"},
        {"invoice_id": "a", "cust_no": "C1", "period_end": "2026-02-01"},
    ]
    assert [row["invoice_id"] for row in sort_rows(rows)] == ["a", "b", "a"]
