"""Unit tests for the u-06 invoiceHeader loader's pure assembly functions.

header_doc/line_elem/assemble take row tuples in the SELECT column order of
load_invoice_header.py and are exercised without Oracle or MongoDB.
"""

import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "migration" / "mongo")
)

import load_invoice_header as loader


bson = pytest.importorskip("bson")


def _header_row(**overrides):
    row = {
        "invoice_id": "inv-1",
        "invoice_no": "INV-0001",
        "cust_id": "cust-1",
        "tenant_id": "tenant-1",
        "invoice_dt": "01-MAR-26",
        "due_dt": "31-MAR-26",
        "status_cd": Decimal("10"),
        "total_amt": Decimal("1234.50"),
        "batch_no": Decimal("85559852"),
    }
    row.update(overrides)
    return tuple(row.values())


def _line_row(**overrides):
    row = {
        "line_id": "line-1",
        "invoice_id": "inv-1",
        "invoice_no": "INV-0001",
        "cust_id": "cust-1",
        "cust_no": "C1",
        "cust_name": "Acme",
        "tenant_id": "tenant-1",
        "line_no": Decimal("1"),
        "line_type_cd": Decimal("1"),
        "item_desc": "widget",
        "qty": Decimal("2.000"),
        "unit_price": Decimal("10.5000"),
        "amount": Decimal("21.00"),
        "tax_amt": Decimal("1.68"),
        "invoice_dt": "01-MAR-26",
        "service_period": "022026-022026",
        "posted_yn": "Y",
        "gl_acct_csv": "4000, 4100 ,4200",
        "batch_no": Decimal("85559852"),
        "src_system": "CUSTBILL",
    }
    row.update(overrides)
    return tuple(row.values())


def test_header_doc_types_and_absent_fields():
    doc = loader.header_doc(
        _header_row(invoice_no="", due_dt=None, total_amt=None), loader.Quarantine()
    )
    assert doc["_id"] == "inv-1"
    assert "invoiceNo" not in doc  # empty_string_is_null
    assert "dueDt" not in doc  # null_missing_equiv
    assert "totalAmt" not in doc
    assert isinstance(doc["statusCd"], bson.int64.Int64)
    assert int(doc["statusCd"]) == 10
    assert isinstance(doc["batchNo"], bson.int64.Int64)
    assert doc["invoiceDt"] == datetime(2026, 3, 1)
    assert doc["lines"] == []


def test_header_doc_decimal128():
    doc = loader.header_doc(_header_row(), loader.Quarantine())
    assert isinstance(doc["totalAmt"], bson.decimal128.Decimal128)
    assert doc["totalAmt"].to_decimal() == Decimal("1234.50")


def test_header_doc_bad_date_kept_and_quarantined():
    quarantine = loader.Quarantine()
    doc = loader.header_doc(_header_row(invoice_dt="not-a-date"), quarantine)
    assert doc["_id"] == "inv-1"  # row kept
    assert "invoiceDt" not in doc
    assert quarantine.reasons == {"bad_date:INVOICE_DT": 1}


def test_line_elem_fields_and_types():
    elem = loader.line_elem(_line_row(), loader.Quarantine())
    assert elem["lineId"] == "line-1"
    assert "invoiceId" not in elem  # parent key never embedded
    assert elem["glAcct"] == ["4000", "4100", "4200"]
    assert elem["posted"] is True
    assert isinstance(elem["lineNo"], bson.int64.Int64)
    assert isinstance(elem["amount"], bson.decimal128.Decimal128)
    assert elem["qty"].to_decimal() == Decimal("2.000")


def test_line_elem_posted_yn_variants():
    quarantine = loader.Quarantine()
    assert loader.line_elem(_line_row(posted_yn="n"), quarantine)["posted"] is False
    assert loader.line_elem(_line_row(posted_yn="true"), quarantine)["posted"] is True
    elem = loader.line_elem(_line_row(posted_yn=None), quarantine)
    assert "posted" not in elem
    elem = loader.line_elem(_line_row(line_id="line-x", posted_yn="?"), quarantine)
    assert "posted" not in elem
    assert quarantine.reasons == {"bad_yn:POSTED_YN": 1}
    assert quarantine.rows == [{"reason": "bad_yn:POSTED_YN", "line_id": "line-x"}]


def test_line_elem_csv_and_empty_absent():
    quarantine = loader.Quarantine()
    elem = loader.line_elem(_line_row(gl_acct_csv=None, item_desc=""), quarantine)
    assert "glAcct" not in elem
    assert "itemDesc" not in elem


def test_assemble_orphan_and_embedded_counts():
    docs, quarantine, embedded = loader.assemble(
        [_header_row()],
        [_line_row(), _line_row(line_id="orphan-1", invoice_id="no-such-inv")],
    )
    assert len(docs) == 1
    assert embedded == 1
    assert quarantine.reasons == {"orphan_line": 1}
    assert quarantine.rows == [
        {"reason": "orphan_line", "line_id": "orphan-1", "invoice_id": "no-such-inv"}
    ]
    assert all(
        elem["lineId"] != "orphan-1"
        for doc in docs
        for elem in doc["lines"]
    )


def test_assemble_duplicate_keys_quarantined():
    docs, quarantine, embedded = loader.assemble(
        [_header_row(), _header_row()],
        [_line_row(), _line_row()],
    )
    assert len(docs) == 1  # first header kept
    assert embedded == 1  # first line kept
    assert quarantine.reasons == {"duplicate_key": 2}


def test_assemble_lines_sorted_by_line_no_then_line_id():
    docs, quarantine, embedded = loader.assemble(
        [_header_row()],
        [
            _line_row(line_id="l-b", line_no=Decimal("2")),
            _line_row(line_id="l-a", line_no=Decimal("2")),
            _line_row(line_id="l-c", line_no=Decimal("1")),
            _line_row(line_id="l-z", line_no=None),
        ],
    )
    assert [e["lineId"] for e in docs[0]["lines"]] == ["l-z", "l-c", "l-a", "l-b"]


def test_line_elem_bad_invoice_dt_quarantined_but_kept():
    quarantine = loader.Quarantine()
    elem = loader.line_elem(_line_row(invoice_dt="99-XXX-99"), quarantine)
    assert elem["lineId"] == "line-1"
    assert "invoiceDt" not in elem
    assert quarantine.reasons == {"bad_date:INVOICE_DT": 1}
