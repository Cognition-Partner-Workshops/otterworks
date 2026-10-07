"""Unit tests for the OW_BILLING PostgreSQL backend and its report wiring.

Live parity against Oracle is in tests/characterization/ (golden/oracle.json).
"""
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import psycopg
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import reports as reports_module
from app import app
from backends import UsageRejected, get_backend
from backends import ow_billing_pg


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("49.00"), "49"),
        (Decimal("0.00"), "0"),
        (Decimal("-12.50"), "-12.5"),
        (Decimal("1E+2"), "100"),
        (7, "7"),
    ],
)
def test_numbers_render_like_oracle_number(value, expected):
    assert ow_billing_pg.oracle_number(value) == expected


def test_dates_render_like_oracle_dates():
    assert ow_billing_pg._json_value(datetime(2026, 2, 1)) == "2026-02-01"
    assert ow_billing_pg._json_value(datetime(2026, 2, 1, 9, 30)) == "2026-02-01T09:30:00"
    assert ow_billing_pg._json_value(date(2026, 2, 1)) == "2026-02-01"


def test_backend_selector(monkeypatch):
    monkeypatch.setenv("BILLING_BACKEND", "ow_billing_pg")
    assert get_backend() is ow_billing_pg


def _on_pg(monkeypatch, **stubs):
    monkeypatch.setenv("BILLING_BACKEND", "ow_billing_pg")
    monkeypatch.setattr(ow_billing_pg, "ensure", lambda tenant, email: None)
    for name, fn in stubs.items():
        monkeypatch.setattr(ow_billing_pg, name, fn)
    return app.test_client()


def test_facade_serves_from_postgres(monkeypatch):
    client = _on_pg(
        monkeypatch,
        list_plans=lambda: [{"plan_id": "p1", "code": "STARTER", "tier": "starter",
                             "monthly_fee": "0", "included_units": "1000",
                             "overage_rate": "0.01"}],
    )
    response = client.get("/api/v1/billing/plans", headers={"X-User-ID": "t1"})
    assert response.status_code == 200
    assert response.get_json() == [{
        "plan_id": "p1", "plan_code": "STARTER", "tier": "starter", "monthly_fee": "0",
        "included_units": "1000", "overage_rate": "0.01",
    }]


def test_facade_estate_unavailable_names_postgres(monkeypatch):
    def boom(*_):
        raise psycopg.OperationalError("down")

    client = _on_pg(monkeypatch, list_plans=boom)
    response = client.get("/api/v1/billing/plans", headers={"X-User-ID": "t1"})
    assert response.status_code == 503
    assert response.get_json() == {
        "error": "legacy estate unavailable",
        "detail": "the PostgreSQL billing estate is not reachable",
    }


def test_ingest_rule_rejection_is_422(monkeypatch):
    def reject(*_):
        raise UsageRejected("units must be positive")

    monkeypatch.setenv("USAGE_INTERNAL_TOKEN", "t0ken")
    client = _on_pg(monkeypatch, ingest_usage_event=reject)
    response = client.post(
        "/internal/usage/events",
        headers={"X-Internal-Token": "t0ken"},
        json={"tenant_id": "t1", "event_id": "6f1c1d2e-3a4b-4c5d-8e9f-0a1b2c3d4e5f", "kind": "api",
              "units": 1, "occurred_at": "2026-02-01T00:00:00Z"},
    )
    assert response.status_code == 422


def test_reconciliation_checks_compare_baseline_with_target():
    checks = reports_module.reconciliation_checks(
        [("customers-count", "25000"), ("invoice-line-amount", "10.00")],
        [("customers-count", "25000"), ("invoice-line-amount", "9.99")],
    )
    by_name = {c["name"]: c for c in checks}
    assert by_name["customers-count"]["status"] == "pass"
    assert by_name["invoice-line-amount"] == {
        "name": "invoice-line-amount", "status": "fail",
        "expected": "10.00", "actual": "9.99",
    }
    assert {c["name"] for c in checks} == set(reports_module.RECON_CHECKS)


def test_reconciliation_without_baseline_fails_closed():
    checks = reports_module.reconciliation_checks([], [("customers-count", "0")])
    assert [c["status"] for c in checks] == ["fail"]


def test_reports_on_postgres_use_pg_sql_and_engine(monkeypatch):
    monkeypatch.setenv("BILLING_BACKEND", "ow_billing_pg")
    seen = []

    def fake(sql, params):
        seen.append(sql)
        if sql is reports_module.PG_BALANCES_SQL:
            return [(Decimal(3), "30.00", "0.00")]
        if sql is reports_module.PG_BASELINE_SQL:
            return [(name, "x") for name in reports_module.RECON_CHECKS]
        return [(name, "x") for name in reports_module.RECON_CHECKS]

    monkeypatch.setattr(ow_billing_pg, "report_query", fake)
    response = app.test_client().get("/api/reports/reconciliation?ns=demo")
    body = response.get_json()
    assert response.status_code == 200
    assert body["source"]["engine"] == "postgresql"
    assert body["status"] == "pass"
    assert all("%(batch_no)s" in sql for sql in seen)
