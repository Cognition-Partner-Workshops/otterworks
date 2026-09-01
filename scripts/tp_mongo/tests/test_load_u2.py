import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from bson import Decimal128

sys.path.insert(0, str(Path(__file__).parents[1]))
import load_u2


def _header(**overrides):
    row = {
        "INVOICE_ID": "inv-1",
        "INVOICE_NO": "1001",
        "CUST_ID": "cust-1",
        "TENANT_ID": "tenant-1",
        "INVOICE_DT": "05-MAR-24",
        "DUE_DT": "31-MAR-24",
        "STATUS_CD": 1,
        "TOTAL_AMT": Decimal("12.5"),
        "BATCH_NO": 85559852,
    }
    row.update(overrides)
    return row


def _line(**overrides):
    row = {
        "LINE_ID": "line-1",
        "INVOICE_NO": "1001",
        "INVOICE_ID": "inv-1",
        "CUST_ID": "cust-1",
        "CUST_NO": "C1",
        "CUST_NAME": "Customer",
        "TENANT_ID": "tenant-1",
        "LINE_NO": 1,
        "LINE_TYPE_CD": 1,
        "ITEM_DESC": "Item",
        "QTY": Decimal("2.1"),
        "UNIT_PRICE": Decimal("3.2"),
        "AMOUNT": Decimal("6.72"),
        "TAX_AMT": Decimal("0.67"),
        "INVOICE_DT": "05-MAR-24",
        "SERVICE_PERIOD": "032024-032024",
        "POSTED_YN": "Y ",
        "GL_ACCT_CSV": " 4000,4010 ",
        "BATCH_NO": 85559852,
        "SRC_SYSTEM": "LEGACY",
    }
    row.update(overrides)
    return row


def test_parse_date():
    assert load_u2.parse_date("05-MAR-24") == datetime(
        2024, 3, 5, tzinfo=timezone.utc
    )
    assert load_u2.parse_date("31-FEB-24") is None
    assert load_u2.parse_date(None) is None


def test_gl_accounts():
    assert load_u2.gl_accounts(" 4000,4010 ") == ["4000", "4010"]
    assert load_u2.gl_accounts(None) == []


def test_build_invoice_doc_canonicalizes_and_scales():
    doc = load_u2.build_invoice_doc(
        _header(INVOICE_NO="", INVOICE_DT="", TOTAL_AMT=Decimal("12.506")),
        [_line(ITEM_DESC="", QTY=Decimal("1.2349"))],
    )
    assert doc["invoice_no"] is None
    assert doc["invoice_date"] is None
    assert doc["total_amt"] == Decimal128("12.51")
    assert doc["lines"][0]["item_desc"] is None
    assert doc["lines"][0]["qty"] == Decimal128("1.235")
    assert doc["lines"][0]["posted_yn"] == "Y"


def test_build_line_elem_canonicalizes_gl_accounts_and_scales():
    line = load_u2.build_line_elem(_line(POSTED_YN="  ", GL_ACCT_CSV=""))
    assert line["posted_yn"] is None
    assert line["gl_acct_csv"] is None
    assert line["gl_accounts"] == []
    assert line["unit_price"] == Decimal128("3.2000")
    assert line["amount"] == Decimal128("6.72")


def test_orphan_partitioning_preserves_all_lines():
    rows = [_line(), _line(LINE_ID="line-2", INVOICE_ID="unknown"), _line(
        LINE_ID="line-3", INVOICE_ID=None
    )]
    embedded, quarantined, total = load_u2.partition_lines(rows, {"inv-1"})
    assert total == 3
    assert [line["LINE_ID"] for line in embedded["inv-1"]] == ["line-1"]
    assert [line["_id"] for line in quarantined] == ["line-2", "line-3"]
    assert all(item["reason_class"] == "orphan_parent" for item in quarantined)
    assert quarantined[1]["invoice_id"] is None


def test_database_guards():
    with pytest.raises(ValueError):
        load_u2.validate_target_db("other")
    with pytest.raises(ValueError):
        load_u2.validate_quarantine_db("other")
