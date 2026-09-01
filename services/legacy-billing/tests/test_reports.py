"""Contract tests for the legacy month-end report endpoints.

Run from services/legacy-billing:
    uv run --with pytest --with flask==3.1.1 pytest tests/

Any backend serving the billing report page must satisfy this contract:
same paths, same JSON shape, only source.engine and reconciliation checks
differ. See docs/tech-partnerships/billing-report-contract.md.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import reports as reports_module
from bson import Decimal128
from flask import Flask
from reports import (
    ns_batch_no,
    reports,
    shape_balance_row,
    shape_balances,
    shape_line_rows,
    shape_status_rows,
)


@pytest.fixture
def client(monkeypatch):
    fixtures = {
        reports_module.STATUS_SQL: [("ISSUED", 100, "12345.00"), ("PAID", 50, "999.00")],
        reports_module.LINE_SQL: [("ISSUED", "CHARGE", 400, "12000.00", "345.00", 100)],
        reports_module.BALANCES_SQL: [(25000, "1234567.00", "8901.00")],
    }
    monkeypatch.setattr(reports_module, "oracle_query", lambda sql, params: fixtures[sql])
    checks = [
        {"name": "customers-populated", "status": "pass", "expected": "> 0", "actual": 25000},
        {"name": "customers-namespaced", "status": "pass", "expected": 25000, "actual": 25000},
    ]
    monkeypatch.setattr(
        reports_module, "mongo_reconciliation",
        lambda batch_no: (fixtures[reports_module.BALANCES_SQL][0], checks),
    )
    app = Flask(__name__)
    app.register_blueprint(reports)
    return app.test_client()


def test_ns_batch_no_matches_seed_derivation():
    # sha256("demo")[:8] % 90_000_000 + 1_000_000 — must equal the seeder's batch.
    import hashlib

    seed = int(hashlib.sha256(b"demo").hexdigest()[:8], 16)
    assert ns_batch_no("demo") == seed % 90_000_000 + 1_000_000
    assert 1_000_000 <= ns_batch_no("rehearsal1") < 91_000_000


def test_shapers():
    assert shape_status_rows([("PAID", 1, "2.00")]) == [
        {"status": "PAID", "invoice_count": 1, "header_total_amt": "2.00"}
    ]
    assert shape_line_rows([("PAID", "CHARGE", 3, "4.00", "5.00", 6)]) == [
        {
            "status": "PAID",
            "line_type": "CHARGE",
            "line_count": 3,
            "line_amount": "4.00",
            "line_tax": "5.00",
            "invoices_touched": 6,
        }
    ]
    assert shape_balances((7, "8.00", "9.00")) == {
        "customer_count": 7,
        "current_balance_total": "8.00",
        "past_due_total": "9.00",
    }


def test_shape_balance_row_preserves_oracle_sum_null_semantics():
    assert shape_balance_row([]) == (0, None, None)
    all_null = {"customer_count": 3, "current_balance_total": 0, "current_balance_values": 0,
                "past_due_total": 0, "past_due_values": 0}
    assert shape_balance_row([all_null]) == (3, None, None)
    mixed = {"customer_count": 3, "current_balance_total": Decimal128("12.5"),
             "current_balance_values": 2, "past_due_total": Decimal128("0"),
             "past_due_values": 1}
    assert shape_balance_row([mixed]) == (3, "12.50", "0.00")


def test_month_end_contract(client):
    body = client.get("/api/reports/month-end?ns=demo").get_json()
    assert body["report"] == "month-end-finance"
    assert body["namespace"] == "demo"
    assert body["batch_no"] == ns_batch_no("demo")
    assert body["source"]["engine"] == "oracle"
    assert body["by_status"][0] == {
        "status": "ISSUED", "invoice_count": 100, "header_total_amt": "12345.00"
    }
    assert body["by_status_line_type"][0]["line_type"] == "CHARGE"
    assert "generated_at" in body


def test_reconciliation_contract(client):
    body = client.get("/api/reports/reconciliation?ns=demo").get_json()
    assert body["source"]["engine"] == "mongodb"
    assert body["balances"] == {
        "customer_count": 25000,
        "current_balance_total": "1234567.00",
        "past_due_total": "8901.00",
    }
    assert body["status"] == "pass"
    assert [c["name"] for c in body["checks"]] == ["customers-populated", "customers-namespaced"]
    assert all(c["status"] == "pass" for c in body["checks"])


def test_reconciliation_fails_when_a_check_fails(client, monkeypatch):
    checks = [{"name": "customers-namespaced", "status": "fail", "expected": 25000, "actual": 24999}]
    monkeypatch.setattr(
        reports_module, "mongo_reconciliation", lambda batch_no: ((24999, "1.00", "0.00"), checks)
    )
    body = client.get("/api/reports/reconciliation?ns=demo").get_json()
    assert body["status"] == "fail"
    assert body["checks"] == checks


def test_reconciliation_target_offline_returns_503(client, monkeypatch):
    def boom(batch_no):
        raise RuntimeError("ServerSelectionTimeoutError")

    monkeypatch.setattr(reports_module, "mongo_reconciliation", boom)
    response = client.get("/api/reports/reconciliation")
    assert response.status_code == 503
    assert response.get_json()["error"] == "legacy estate unavailable"


def test_estate_offline_returns_503(client, monkeypatch):
    def boom(sql, params):
        raise RuntimeError("ORA-12541: no listener")

    monkeypatch.setattr(reports_module, "oracle_query", boom)
    response = client.get("/api/reports/month-end")
    assert response.status_code == 503
    assert response.get_json()["error"] == "legacy estate unavailable"
