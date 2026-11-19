import importlib
import sys

import pytest

import app as module
from finance_warehouse import COLUMNS


ROW = dict(zip(COLUMNS, (
    "A000318274", "Bramblewood Outfitters", "USD", "2025-10-15",
    "6000.00", "1000.00", "1200.00", "800.00", "500.00", "2500.00", "0.75",
), strict=True))


class FakeWarehouse:
    def __init__(self, rows=None, error=None):
        self.rows = [ROW] if rows is None else rows
        self.error = error
        self.calls = 0

    def ar_aging(self):
        self.calls += 1
        if self.error:
            raise self.error
        return self.rows


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setitem(module.app.config, "TESTING", True)
    monkeypatch.setitem(module.app.config, "FINANCE_WAREHOUSE_ENABLED", True)
    monkeypatch.setitem(module.app.extensions, "finance_warehouse", FakeWarehouse())
    return module.app.test_client()


def test_json_aging(client):
    response = client.get("/finance/ar-aging")
    assert response.status_code == 200
    assert response.get_json() == [ROW]
    assert response.content_type == "application/json"


def test_html_table_escapes_customer_name(client, monkeypatch):
    row = {**ROW, "CUSTOMER_NAME": "<script>alert(1)</script>"}
    monkeypatch.setitem(module.app.extensions, "finance_warehouse", FakeWarehouse([row]))
    response = client.get("/finance/ar-aging?format=html")
    text = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "<table>" in text
    assert "A000318274" in text
    assert "6000.00" in text
    assert "&lt;script&gt;" in text
    assert "<script>" not in text


def test_empty_json_and_table(client, monkeypatch):
    monkeypatch.setitem(module.app.extensions, "finance_warehouse", FakeWarehouse([]))
    assert client.get("/finance/ar-aging").get_json() == []
    response = client.get("/finance/ar-aging?format=html")
    assert "No outstanding receivables." in response.get_data(as_text=True)


def test_disabled_flag_does_not_query(client, monkeypatch):
    fake = FakeWarehouse(error=AssertionError("must not query"))
    monkeypatch.setitem(module.app.extensions, "finance_warehouse", fake)
    monkeypatch.setitem(module.app.config, "FINANCE_WAREHOUSE_ENABLED", False)
    assert client.get("/finance/ar-aging").status_code == 404
    assert fake.calls == 0


def test_invalid_format_does_not_query(client, monkeypatch):
    fake = FakeWarehouse()
    monkeypatch.setitem(module.app.extensions, "finance_warehouse", fake)
    assert client.get("/finance/ar-aging?format=xml").status_code == 400
    assert fake.calls == 0


def test_warehouse_error_is_sanitized(client, monkeypatch):
    monkeypatch.setitem(
        module.app.extensions, "finance_warehouse", FakeWarehouse(error=RuntimeError("private DSN")),
    )
    response = client.get("/finance/ar-aging")
    assert response.status_code == 503
    assert response.get_json() == {"error": "finance warehouse unavailable"}
    assert b"private" not in response.data


def test_import_and_env_flag_without_driver_or_connection(monkeypatch):
    monkeypatch.setitem(sys.modules, "teradatasql", None)
    monkeypatch.setenv("FINANCE_WAREHOUSE_ENABLED", "false")
    importlib.reload(module)
    assert module.app.config["FINANCE_WAREHOUSE_ENABLED"] is False
    monkeypatch.delenv("FINANCE_WAREHOUSE_ENABLED")
    importlib.reload(module)
    assert module.app.config["FINANCE_WAREHOUSE_ENABLED"] is True


def test_existing_plans_route_with_fake_postgres(client, monkeypatch):
    monkeypatch.setattr(module, "select", lambda sql, params=(): [{"code": "TEAM"}])
    assert client.get("/plans").get_json() == [{"code": "TEAM"}]
