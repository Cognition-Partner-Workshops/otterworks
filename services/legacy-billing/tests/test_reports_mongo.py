"""Unit tests for the MongoDB backend read paths (unit u-06).

Uses a fake ``db`` object so no live MongoDB is needed. bson types are only
constructed where pymongo/bson is installed; those tests skip otherwise so
the suite still runs in environments without ``--with pymongo``.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import reports as reports_module
from backends import mongo as mongo_backend
from flask import Flask
from reports import reports


class FakeCollection:
    def __init__(self, docs):
        self.docs = docs
        self.pipelines = []

    def aggregate(self, pipeline):
        self.pipelines.append(pipeline)
        return iter(self.docs)


class FakeDB:
    def __init__(self, docs):
        self.invoiceHeader = FakeCollection(docs)

    def __getitem__(self, name):
        assert name == "invoiceHeader"
        return self.invoiceHeader


def _status_group(status_cd, desc, count, total):
    return {
        "_id": {"cd": status_cd, "desc": desc},
        "invoice_count": count,
        "header_total_amt": total,
    }


def test_status_rows_labels_and_totals():
    bson = pytest.importorskip("bson")
    db = FakeDB(
        [
            _status_group(10, "ISSUED", 100, bson.Decimal128("12345.00")),
            _status_group(42, None, 3, bson.Decimal128("-5.00")),
            _status_group(None, None, 1, bson.Decimal128("7.5")),
        ]
    )
    rows = mongo_backend.month_end_status_rows(db, 85559852)
    assert rows == [
        ("ISSUED", 100, "12345.00"),
        ("UNKNOWN()", 1, "7.50"),
        ("UNKNOWN(42)", 3, "-5.00"),
    ]
    assert all(isinstance(row[1], int) for row in rows)
    assert all(isinstance(row[2], str) for row in rows)
    assert db.invoiceHeader.pipelines[0][0] == {"$match": {"batchNo": 85559852}}


def test_status_rows_sorted_by_label():
    bson = pytest.importorskip("bson")
    db = FakeDB(
        [
            _status_group(30, "PAID", 2, bson.Decimal128("1.00")),
            _status_group(10, "ISSUED", 5, bson.Decimal128("2.00")),
        ]
    )
    assert [row[0] for row in mongo_backend.month_end_status_rows(db, 1)] == [
        "ISSUED",
        "PAID",
    ]


def _line_group(status_cd, desc, line_type_cd, count, amount, tax, touched):
    return {
        "_id": {"cd": status_cd, "desc": desc, "lt": line_type_cd},
        "line_count": count,
        "line_amount": amount,
        "line_tax": tax,
        "invoices_touched": touched,
    }


def test_line_rows_decode_and_unknown_types():
    bson = pytest.importorskip("bson")
    db = FakeDB(
        [
            _line_group(10, "ISSUED", 1, 400, bson.Decimal128("12000.00"),
                        bson.Decimal128("345.00"), bson.int64.Int64(100)),
            _line_group(10, "ISSUED", 9, 2, bson.Decimal128("1.00"),
                        bson.Decimal128("0.10"), 2),
            _line_group(None, None, 7, 1, bson.Decimal128("0.50"),
                        bson.Decimal128("0.01"), 1),
        ]
    )
    rows = mongo_backend.month_end_line_rows(db, 85559852)
    assert rows == [
        ("ISSUED", "CHARGE", 400, "12000.00", "345.00", 100),
        ("ISSUED", "MISC", 2, "1.00", "0.10", 2),
        ("UNKNOWN()", "UNKNOWN(7)", 1, "0.50", "0.01", 1),
    ]
    assert all(isinstance(row[2], int) for row in rows)
    assert all(isinstance(row[5], int) for row in rows)


def test_month_end_endpoint_uses_mongo_source(monkeypatch):
    bson = pytest.importorskip("bson")  # noqa: F841
    monkeypatch.setenv("BILLING_BACKEND", "mongo")
    monkeypatch.setattr(
        mongo_backend,
        "month_end_status_rows",
        lambda db, batch_no: [("ISSUED", 2, "10.00")],
    )
    monkeypatch.setattr(
        mongo_backend,
        "month_end_line_rows",
        lambda db, batch_no: [("ISSUED", "CHARGE", 3, "10.00", "1.00", 2)],
    )
    monkeypatch.setattr(mongo_backend, "get_db", lambda client=None: object())
    app = Flask(__name__)
    app.register_blueprint(reports)
    body = app.test_client().get("/api/reports/month-end?ns=demo").get_json()
    assert body["source"]["engine"] == "mongodb"
    assert body["source"]["system"] == "ow_billing_migration.invoiceHeader (MongoDB)"
    assert body["by_status"] == [
        {"status": "ISSUED", "invoice_count": 2, "header_total_amt": "10.00"}
    ]
    assert body["by_status_line_type"] == [
        {
            "status": "ISSUED",
            "line_type": "CHARGE",
            "line_count": 3,
            "line_amount": "10.00",
            "line_tax": "1.00",
            "invoices_touched": 2,
        }
    ]


def test_month_end_oracle_path_unchanged(monkeypatch):
    monkeypatch.delenv("BILLING_BACKEND", raising=False)
    fixtures = {
        reports_module.STATUS_SQL: [("PAID", 1, "2.00")],
        reports_module.LINE_SQL: [("PAID", "CHARGE", 3, "4.00", "5.00", 6)],
    }
    monkeypatch.setattr(
        reports_module, "oracle_query", lambda sql, params: fixtures[sql]
    )
    app = Flask(__name__)
    app.register_blueprint(reports)
    body = app.test_client().get("/api/reports/month-end?ns=demo").get_json()
    assert body["source"]["engine"] == "oracle"
    assert body["by_status"] == [
        {"status": "PAID", "invoice_count": 1, "header_total_amt": "2.00"}
    ]
