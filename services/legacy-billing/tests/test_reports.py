"""Contract tests for the legacy month-end report endpoints.

Run from services/legacy-billing:
    uv run --with pytest --with flask==3.1.1 pytest tests/

Any backend serving the billing report page must satisfy this contract:
same paths, same JSON shape, only source.engine and reconciliation checks
differ. See docs/tech-partnerships/billing-report-contract.md.
"""

import sys
from pathlib import Path
from shutil import copyfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import reports as reports_module
from flask import Flask
from reports import (
    ns_batch_no,
    reports,
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


def test_admin_report_aliases_require_admin_and_match_legacy(client):
    assert client.get("/api/v1/billing/admin/reports/month-end").status_code == 403
    assert client.get("/api/v1/billing/admin/reports/reconciliation").status_code == 403
    assert client.get("/api/v1/billing/admin/reports/finance").status_code == 403
    headers = {"X-User-Roles": "ADMIN"}
    alias = client.get(
        "/api/v1/billing/admin/reports/month-end?ns=demo", headers=headers,
    ).get_json()
    legacy = client.get("/api/reports/month-end?ns=demo").get_json()
    assert alias == legacy


def test_reconciliation_contract(client):
    body = client.get("/api/reports/reconciliation?ns=demo").get_json()
    assert body["source"]["engine"] == "oracle"
    assert body["balances"] == {
        "customer_count": 25000,
        "current_balance_total": "1234567.00",
        "past_due_total": "8901.00",
    }
    assert body["status"] == "baseline"
    assert body["checks"] == []


def test_estate_offline_returns_503(client, monkeypatch):
    def boom(sql, params):
        raise RuntimeError("ORA-12541: no listener")

    monkeypatch.setattr(reports_module, "oracle_query", boom)
    response = client.get("/api/reports/month-end")
    assert response.status_code == 503
    assert response.get_json()["error"] == "legacy estate unavailable"


def test_finance_report_reads_namespace_batch_fixture(client, monkeypatch, tmp_path):
    report_dir = tmp_path / "reports" / "demo"
    report_dir.mkdir(parents=True)
    copyfile(
        Path(__file__).parent / "fixtures" / "finance_billing_20260228.csv",
        report_dir / "finance_billing_20260228.csv",
    )
    (report_dir / "finance_billing_20260228.xls").write_text("not a report")
    monkeypatch.setenv("FINANCE_REPORT_DIR", str(tmp_path / "reports"))
    response = client.get("/api/reports/finance?ns=demo")
    assert response.status_code == 200
    body = response.get_json()
    assert body["ns"] == "demo"
    assert body["source"]["system"] == "CUSTBILL month-end batch"
    assert body["source"]["file"] == "finance_billing_20260228.csv"
    assert body["rows"][0] == {
        "currency": "USD",
        "record_type": "INVOICE",
        "record_count": 2,
        "total_amount": "25.00",
    }
    assert body["totals"] == {"record_count": 3, "total_amount": "30.00"}


def test_finance_report_missing_namespace_returns_404(client, monkeypatch, tmp_path):
    monkeypatch.setenv("FINANCE_REPORT_DIR", str(tmp_path))
    response = client.get("/api/reports/finance?ns=missing")
    assert response.status_code == 404
    assert response.get_json() == {
        "error": "no finance report for namespace",
        "detail": "run make tp-month-end NS=missing",
    }


def test_finance_report_over_size_limit_returns_413(client, monkeypatch, tmp_path):
    report_dir = tmp_path / "reports" / "demo"
    report_dir.mkdir(parents=True)
    report = report_dir / "finance_billing_20260228.csv"
    copyfile(
        Path(__file__).parent / "fixtures" / "finance_billing_20260228.csv",
        report,
    )
    monkeypatch.setenv("FINANCE_REPORT_DIR", str(tmp_path / "reports"))
    monkeypatch.setenv("FINANCE_REPORT_MAX_BYTES", "1")
    response = client.get("/api/reports/finance?ns=demo")
    assert response.status_code == 413
    assert response.get_json() == {"error": "finance report too large"}


class FakeCollection:
    def __init__(self, docs):
        self.docs = docs

    def find(self, query, projection=None):
        code_type = query.get("_id.codeType")
        return [d for d in self.docs if code_type is None or d["_id"]["codeType"] == code_type]

    def count_documents(self, query):
        known = query["statusCd"]["$nin"]
        return sum(1 for d in self.docs if d.get("batchNo") == query["batchNo"] and d.get("statusCd") not in known)


class FakeFeed(FakeCollection):
    """invoice_feed: answers the two month-end groupings and the reconciliation probes."""

    def aggregate(self, pipeline):
        batch_no = pipeline[0]["$match"]["batchNo"]
        docs = [d for d in self.docs if d.get("batchNo") == batch_no]
        if pipeline[-1] == {"$count": "n"}:
            stray = [line for d in docs for line in d.get("lines", []) if line.get("batchNo") != d.get("batchNo")]
            return [{"n": len(stray)}] if stray else []
        if "$unwind" in pipeline[1]:
            groups = {}
            for d in docs:
                for line in d.get("lines", []):
                    g = groups.setdefault((d.get("statusCd"), line.get("lineTypeCd")), {"line_count": 0, "line_amount": 0, "amount_rows": 0, "line_tax": 0, "tax_rows": 0, "invoices": set()})
                    g["line_count"] += 1
                    g["invoices"].add(d["_id"])
                    if line.get("amount") is not None:
                        g["line_amount"] += line["amount"]
                        g["amount_rows"] += 1
                    if line.get("taxAmt") is not None:
                        g["line_tax"] += line["taxAmt"]
                        g["tax_rows"] += 1
            return [
                {"_id": {"statusCd": status, "lineTypeCd": line_type}, **{k: v for k, v in g.items() if k != "invoices"}, "invoices_touched": len(g["invoices"])}
                for (status, line_type), g in groups.items()
            ]
        groups = {}
        for d in docs:
            g = groups.setdefault(d.get("statusCd"), {"invoice_count": 0, "header_total_amt": 0, "amount_rows": 0})
            g["invoice_count"] += 1
            if d.get("totalAmt") is not None:
                g["header_total_amt"] += d["totalAmt"]
                g["amount_rows"] += 1
        return [{"_id": status, **g} for status, g in groups.items()]


class FakeQuarantine(FakeCollection):
    def __init__(self, docs, headers):
        super().__init__(docs)
        self.headers = headers

    def aggregate(self, pipeline):
        batch_no = pipeline[0]["$match"]["batchNo"]
        hits = [q for q in self.docs if q.get("batchNo") == batch_no and q.get("invoiceId") in self.headers]
        return [{"n": len(hits)}] if hits else []


class FakeCustomers(FakeCollection):
    def aggregate(self, pipeline):
        batch_no = pipeline[0]["$match"]["conversionBatchNo"]
        docs = [d for d in self.docs if d.get("conversionBatchNo") == batch_no]
        if not docs:
            return []
        return [{
            "customer_count": len(docs),
            "current_balance_total": sum(d.get("curBalAmt") or 0 for d in docs),
            "current_rows": sum(1 for d in docs if d.get("curBalAmt") is not None),
            "past_due_total": sum(d.get("pastDueAmt") or 0 for d in docs),
            "past_due_rows": sum(1 for d in docs if d.get("pastDueAmt") is not None),
        }]


class FakeDb:
    def __init__(self, batch_no, feed_docs, quarantine_docs, customer_docs):
        from decimal import Decimal

        self.codes = FakeCollection([
            {"_id": {"codeType": "INV_STATUS", "codeVal": 20}, "codeDesc": "issued"},
            {"_id": {"codeType": "INV_STATUS", "codeVal": 30}, "codeDesc": "paid"},
            {"_id": {"codeType": "TENANT_STATUS", "codeVal": 10}, "codeDesc": "active"},
        ])
        self.invoice_feed = FakeFeed(feed_docs)
        self.invoice_feed_quarantine = FakeQuarantine(quarantine_docs, {d["_id"] for d in feed_docs})
        self.customers = FakeCustomers(customer_docs)
        self.Decimal = Decimal


@pytest.fixture
def mongo_client(monkeypatch):
    from decimal import Decimal

    batch_no = ns_batch_no("demo")
    feed = [
        {"_id": "H1", "batchNo": batch_no, "statusCd": 20, "totalAmt": Decimal("100.00"),
         "lines": [{"lineId": "L1", "batchNo": batch_no, "lineTypeCd": 1, "amount": Decimal("90.00"), "taxAmt": Decimal("10.00")},
                   {"lineId": "L2", "batchNo": batch_no, "lineTypeCd": 2, "amount": Decimal("-5.50"), "taxAmt": None}]},
        {"_id": "H2", "batchNo": batch_no, "statusCd": 20, "totalAmt": Decimal("20.25"),
         "lines": [{"lineId": "L3", "batchNo": batch_no, "lineTypeCd": 1, "amount": Decimal("20.25"), "taxAmt": Decimal("0.00")}]},
        {"_id": "H3", "batchNo": batch_no, "statusCd": 77, "totalAmt": None,
         "lines": [{"lineId": "L4", "batchNo": batch_no, "lineTypeCd": 5, "amount": None, "taxAmt": None}]},
        {"_id": "H4", "batchNo": batch_no + 1, "statusCd": 30, "totalAmt": Decimal("999.00"), "lines": []},
    ]
    quarantine = [{"_id": "Q1", "batchNo": batch_no, "invoiceId": "GHOST"}]
    customers = [
        {"_id": "C1", "conversionBatchNo": batch_no, "curBalAmt": Decimal("10.00"), "pastDueAmt": Decimal("1.00")},
        {"_id": "C2", "conversionBatchNo": batch_no, "curBalAmt": Decimal("2.50"), "pastDueAmt": None},
        {"_id": "C3", "conversionBatchNo": batch_no + 1, "curBalAmt": Decimal("7.00"), "pastDueAmt": Decimal("7.00")},
    ]
    db = FakeDb(batch_no, feed, quarantine, customers)
    monkeypatch.setenv("BILLING_BACKEND", "mongo")
    monkeypatch.setattr(reports_module, "mongo_db", lambda: db)
    monkeypatch.setattr(reports_module, "oracle_query", lambda sql, params: pytest.fail("Oracle must not be queried on the Mongo backend"))
    app = Flask(__name__)
    app.register_blueprint(reports)
    return app.test_client(), db


def test_mongo_month_end_contract(mongo_client):
    client, _db = mongo_client
    body = client.get("/api/reports/month-end?ns=demo").get_json()
    assert body["report"] == "month-end-finance"
    assert body["namespace"] == "demo"
    assert body["batch_no"] == ns_batch_no("demo")
    assert body["source"]["engine"] == "mongodb"
    assert body["by_status"] == [
        {"status": "UNKNOWN(77)", "invoice_count": 1, "header_total_amt": None},
        {"status": "issued", "invoice_count": 2, "header_total_amt": "120.25"},
    ]
    assert body["by_status_line_type"] == [
        {"status": "UNKNOWN(77)", "line_type": "UNKNOWN(5)", "line_count": 1, "line_amount": None, "line_tax": None, "invoices_touched": 1},
        {"status": "issued", "line_type": "CHARGE", "line_count": 2, "line_amount": "110.25", "line_tax": "10.00", "invoices_touched": 2},
        {"status": "issued", "line_type": "CREDIT", "line_count": 1, "line_amount": "-5.50", "line_tax": None, "invoices_touched": 1},
    ]


def test_mongo_reconciliation_contract(mongo_client):
    client, db = mongo_client
    body = client.get("/api/reports/reconciliation?ns=demo").get_json()
    assert body["namespace"] == "demo"
    assert body["source"]["engine"] == "mongodb"
    assert body["balances"] == {"customer_count": 2, "current_balance_total": "12.50", "past_due_total": "1.00"}
    assert body["status"] == "fail"
    by_name = {check["name"]: check for check in body["checks"]}
    assert set(by_name) == {"invoice-feed-quarantine-orphans-only", "invoice-feed-lines-match-header-batch", "invoice-feed-status-codes-mapped"}
    assert by_name["invoice-feed-quarantine-orphans-only"]["status"] == "pass"
    assert by_name["invoice-feed-lines-match-header-batch"]["status"] == "pass"
    assert by_name["invoice-feed-status-codes-mapped"] == {"name": "invoice-feed-status-codes-mapped", "status": "fail", "expected": "0", "actual": "1"}
    db.codes.docs.append({"_id": {"codeType": "INV_STATUS", "codeVal": 77}, "codeDesc": "void"})
    body = client.get("/api/reports/reconciliation?ns=demo").get_json()
    assert body["status"] == "pass" and all(check["status"] == "pass" for check in body["checks"])


def test_oracle_report_path_unchanged_on_mongo_env(client, monkeypatch):
    monkeypatch.setenv("BILLING_BACKEND", "oracle")
    body = client.get("/api/reports/month-end?ns=demo").get_json()
    assert body["source"]["engine"] == "oracle"
    assert body["by_status"][0]["invoice_count"] == 100
