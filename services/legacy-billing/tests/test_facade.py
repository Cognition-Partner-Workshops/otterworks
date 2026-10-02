import sys
from datetime import date, timedelta
from pathlib import Path

import oracledb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import backends
import facade as facade_module
from app import app


def test_facade_requires_identity(monkeypatch):
    monkeypatch.setenv("BILLING_BACKEND", "oracle")
    response = app.test_client().get("/api/v1/billing/me")
    assert response.status_code == 401


@pytest.mark.parametrize(
    ("path", "headers"),
    [
        ("/api/v1/billing/me?on=2026-02-31", {"X-User-ID": "tenant"}),
        ("/api/v1/billing/entitlement?on=not-a-date", {"X-User-ID": "tenant"}),
        (
            "/api/v1/billing/usage?period_start=2026-03-01&period_end=2026-02-01",
            {"X-User-ID": "tenant"},
        ),
        (
            "/api/v1/billing/usage?period_start=2026-02-01&period_end=not-a-date",
            {"X-User-ID": "tenant"},
        ),
        (
            "/api/v1/billing/admin/overdue?as_of=tomorrow",
            {"X-User-ID": "tenant", "X-User-Roles": "ADMIN"},
        ),
        (
            "/api/v1/billing/admin/dunning?as_of=tomorrow",
            {"X-User-ID": "tenant", "X-User-Roles": "ADMIN"},
        ),
    ],
)
def test_invalid_date_query_params_fail_before_oracle(monkeypatch, path, headers):
    monkeypatch.setenv("BILLING_BACKEND", "oracle")
    monkeypatch.setattr(
        facade_module,
        "_ensure",
        lambda _: pytest.fail("Oracle was touched"),
    )
    monkeypatch.setattr(
        facade_module.oracle,
        "overdue",
        lambda _: pytest.fail("Oracle was touched"),
    )
    monkeypatch.setattr(
        facade_module.oracle,
        "query",
        lambda *_args, **_kwargs: pytest.fail("Oracle was touched"),
    )
    response = app.test_client().get(path, headers=headers)
    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid date"


def test_admin_facade_requires_role(monkeypatch):
    monkeypatch.setenv("BILLING_BACKEND", "oracle")
    response = app.test_client().get(
        "/api/v1/billing/admin/overdue",
        headers={"X-User-ID": "tenant"},
    )
    assert response.status_code == 403


def test_admin_overdue_maps_total_to_amount(monkeypatch):
    monkeypatch.setenv("BILLING_BACKEND", "oracle")
    monkeypatch.setattr(
        facade_module.oracle,
        "overdue",
        lambda as_of: [
            {
                "tenant_id": "tenant-1",
                "invoice_id": "invoice-1",
                "total": "25.00",
                "days_overdue": 12,
            }
        ],
    )
    response = app.test_client().get(
        "/api/v1/billing/admin/overdue",
        headers={"X-User-ID": "tenant", "X-User-Roles": "ADMIN"},
    )
    assert response.status_code == 200
    assert response.get_json() == [
        {
            "tenant_id": "tenant-1",
            "invoice_id": "invoice-1",
            "total": "25.00",
            "amount": "25.00",
            "days_overdue": 12,
        }
    ]


def test_plans_requires_identity(monkeypatch):
    monkeypatch.setenv("BILLING_BACKEND", "oracle")
    response = app.test_client().get("/api/v1/billing/plans")
    assert response.status_code == 401
    assert response.get_json() == {"error": "missing user identity"}


def test_facade_is_unavailable_in_postgres_mode(monkeypatch):
    monkeypatch.setenv("BILLING_BACKEND", "postgres")
    response = app.test_client().get(
        "/api/v1/billing/plans", headers={"X-User-ID": "tenant"}
    )
    assert response.status_code == 501
    assert response.get_json() == {"error": "not available on this backend"}


def test_facade_plans_shape(monkeypatch):
    monkeypatch.setenv("BILLING_BACKEND", "oracle")
    monkeypatch.setattr(
        facade_module.oracle,
        "list_plans",
        lambda: [
            {
                "plan_id": "p1",
                "code": "GROWTH",
                "tier": "growth",
                "monthly_fee": "149.00",
                "included_units": 500,
                "overage_rate": "0.035000",
            }
        ],
    )
    response = app.test_client().get(
        "/api/v1/billing/plans", headers={"X-User-ID": "tenant"}
    )
    assert response.status_code == 200
    assert response.get_json() == [
        {
            "plan_id": "p1",
            "plan_code": "GROWTH",
            "tier": "growth",
            "monthly_fee": "149.00",
            "included_units": 500,
            "overage_rate": "0.035000",
        }
    ]


def test_me_shape(monkeypatch):
    monkeypatch.setenv("BILLING_BACKEND", "oracle")
    monkeypatch.setattr(facade_module, "_ensure", lambda tenant_id: None)
    monkeypatch.setattr(
        facade_module.oracle,
        "entitlement",
        lambda tenant_id, on: [{"tenant_id": tenant_id, "plan_code": "GROWTH"}],
    )
    rows = iter(
        [
            [{"tenant_id": "t1", "name": "admin@example.com", "status": "active", "tax_exempt": "N"}],
            [{"cust_no": "OW-1", "cust_name": "Admin", "cur_bal_amt": "1.00"}],
        ]
    )
    monkeypatch.setattr(facade_module.oracle, "query", lambda sql, params=(): next(rows))
    response = app.test_client().get(
        "/api/v1/billing/me",
        headers={"X-User-ID": "t1", "X-User-Email": "admin@example.com"},
    )
    assert response.status_code == 200
    assert response.get_json()["entitlement"][0]["plan_code"] == "GROWTH"
    assert response.get_json()["customer"]["cust_no"] == "OW-1"


def test_facade_oracle_failure_returns_503(monkeypatch):
    monkeypatch.setenv("BILLING_BACKEND", "oracle")

    def fail():
        raise oracledb.Error("ORA-12541: no listener")

    monkeypatch.setattr(facade_module.oracle, "list_plans", fail)
    response = app.test_client().get(
        "/api/v1/billing/plans", headers={"X-User-ID": "tenant"}
    )
    assert response.status_code == 503
    assert response.get_json() == {
        "error": "legacy estate unavailable",
        "detail": "the Oracle billing estate is not reachable",
    }


class DuplicateError(oracledb.Error):
    pass


class FakeCursor:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql, params):
        raise DuplicateError("ORA-00001: unique constraint violated")


class FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def cursor(self):
        return FakeCursor()

    def commit(self):
        return None


def test_internal_ingest_duplicate(monkeypatch):
    monkeypatch.setenv("BILLING_BACKEND", "oracle")
    monkeypatch.setenv("USAGE_INTERNAL_TOKEN", "test-token")
    monkeypatch.setattr(facade_module.oracle, "ensure_tenant", lambda *args: None)
    monkeypatch.setattr(facade_module.oracle, "oracle_connect", lambda: FakeConnection())
    response = app.test_client().post(
        "/internal/usage/events",
        json={
            "event_id": "00000000-0000-0000-0000-000000000001",
            "tenant_id": "tenant-1",
            "email": "tenant@example.com",
            "kind": "api",
            "units": 1,
            "occurred_at": "2026-02-10T10:00:00Z",
        },
        headers={"X-Internal-Token": "test-token"},
    )
    assert response.status_code == 200
    assert response.get_json() == {"status": "duplicate"}


def test_internal_ingest_requires_token(monkeypatch):
    monkeypatch.setenv("BILLING_BACKEND", "oracle")
    monkeypatch.setenv("USAGE_INTERNAL_TOKEN", "test-token")
    response = app.test_client().post("/internal/usage/events", json={})
    assert response.status_code == 401


def test_internal_ingest_rejects_invalid_payload_before_oracle(monkeypatch):
    monkeypatch.setenv("BILLING_BACKEND", "oracle")
    monkeypatch.setenv("USAGE_INTERNAL_TOKEN", "test-token")
    monkeypatch.setattr(
        facade_module.oracle,
        "oracle_connect",
        lambda: (_ for _ in ()).throw(AssertionError("Oracle touched")),
    )
    response = app.test_client().post(
        "/internal/usage/events",
        headers={"X-Internal-Token": "test-token"},
        json={
            "event_id": "00000000-0000-0000-0000-000000000001",
            "tenant_id": "tenant-1",
            "kind": "invalid",
            "units": 1,
            "occurred_at": "not-a-date",
        },
    )
    assert response.status_code == 400


def test_internal_ingest_rejects_non_uuid_event_id_before_oracle(monkeypatch):
    monkeypatch.setenv("BILLING_BACKEND", "oracle")
    monkeypatch.setenv("USAGE_INTERNAL_TOKEN", "test-token")
    monkeypatch.setattr(
        facade_module.oracle,
        "oracle_connect",
        lambda: (_ for _ in ()).throw(AssertionError("Oracle touched")),
    )
    response = app.test_client().post(
        "/internal/usage/events",
        headers={"X-Internal-Token": "test-token"},
        json={
            "event_id": "x" * 64,
            "tenant_id": "tenant-1",
            "kind": "api",
            "units": 1,
            "occurred_at": "2026-02-10T10:00:00Z",
        },
    )
    assert response.status_code == 400
    assert response.get_json()["detail"] == "event_id must be a canonical UUID"


def test_plan_change_rejects_missing_field_before_oracle(monkeypatch):
    monkeypatch.setenv("BILLING_BACKEND", "oracle")
    called = False

    def list_plans():
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(facade_module.oracle, "list_plans", list_plans)
    response = app.test_client().post(
        "/api/v1/billing/plan-change",
        headers={"X-User-ID": "tenant"},
        json={"effective_on": (date.today() + timedelta(days=1)).isoformat()},
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid plan change"
    assert called is False


def test_plan_change_rejects_bad_date(monkeypatch):
    monkeypatch.setenv("BILLING_BACKEND", "oracle")
    response = app.test_client().post(
        "/api/v1/billing/plan-change",
        headers={"X-User-ID": "tenant"},
        json={"plan_id": "p1", "effective_on": "not-a-date"},
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid plan change"


def test_plan_change_rejects_past_date(monkeypatch):
    monkeypatch.setenv("BILLING_BACKEND", "oracle")
    response = app.test_client().post(
        "/api/v1/billing/plan-change",
        headers={"X-User-ID": "tenant"},
        json={"plan_id": "p1", "effective_on": "2020-01-01"},
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid plan change"


def test_plan_change_rejects_unknown_plan(monkeypatch):
    monkeypatch.setenv("BILLING_BACKEND", "oracle")
    monkeypatch.setattr(facade_module.oracle, "list_plans", lambda: [{"plan_id": "p2"}])
    response = app.test_client().post(
        "/api/v1/billing/plan-change",
        headers={"X-User-ID": "tenant"},
        json={"plan_id": "p1", "effective_on": (date.today() + timedelta(days=1)).isoformat()},
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid plan change"


def test_backend_switch_selects_mongo(monkeypatch):
    monkeypatch.setenv("BILLING_BACKEND", "mongo")
    assert backends.backend_name() == "mongo"
    assert backends.get_backend().DATABASE == "ow_tp_billing_20261001T233613Z"
    monkeypatch.setenv("BILLING_BACKEND", "oracle")
    assert backends.backend_name() == "oracle"
    monkeypatch.delenv("BILLING_BACKEND")
    assert backends.backend_name() == "postgres"


def test_facade_plans_served_by_mongo_backend(monkeypatch):
    monkeypatch.setenv("BILLING_BACKEND", "mongo")
    mongo = backends.get_backend()
    monkeypatch.setattr(
        mongo,
        "list_plans",
        lambda: [
            {
                "plan_id": "p1",
                "code": "GROWTH",
                "tier": "growth",
                "monthly_fee": "149.00",
                "included_units": 500,
                "overage_rate": "0.035000",
            }
        ],
    )
    response = app.test_client().get(
        "/api/v1/billing/plans", headers={"X-User-ID": "tenant"}
    )
    assert response.status_code == 200
    assert response.get_json()[0]["plan_code"] == "GROWTH"


def test_facade_me_on_mongo_has_null_customer_until_u2(monkeypatch):
    monkeypatch.setenv("BILLING_BACKEND", "mongo")
    mongo = backends.get_backend()
    monkeypatch.setattr(mongo, "ensure_tenant", lambda tenant_id, email: False)
    monkeypatch.setattr(
        mongo,
        "entitlement",
        lambda tenant_id, on: [{"tenant_id": tenant_id, "plan_code": "STARTER"}],
    )
    monkeypatch.setattr(
        mongo,
        "tenant_profile",
        lambda tenant_id: [{"tenant_id": tenant_id, "name": "t1", "status": "active", "tax_exempt": "N"}],
    )
    response = app.test_client().get(
        "/api/v1/billing/me", headers={"X-User-ID": "t1"}
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["entitlement"][0]["plan_code"] == "STARTER"
    assert body["customer"] is None


def test_facade_mongo_failure_returns_503(monkeypatch):
    from pymongo.errors import ServerSelectionTimeoutError

    monkeypatch.setenv("BILLING_BACKEND", "mongo")

    def fail():
        raise ServerSelectionTimeoutError("no primary")

    monkeypatch.setattr(backends.get_backend(), "list_plans", fail)
    response = app.test_client().get(
        "/api/v1/billing/plans", headers={"X-User-ID": "tenant"}
    )
    assert response.status_code == 503
    assert response.get_json() == {
        "error": "legacy estate unavailable",
        "detail": "the MongoDB billing database is not reachable",
    }


@pytest.mark.parametrize(
    "path",
    ["/api/v1/billing/customer"],
)
def test_facade_non_u1_routes_not_available_on_mongo(monkeypatch, path):
    monkeypatch.setenv("BILLING_BACKEND", "mongo")
    response = app.test_client().get(path, headers={"X-User-ID": "tenant"})
    assert response.status_code == 501
    assert response.get_json() == {"error": "not available on this backend"}


def test_facade_usage_served_by_mongo_backend(monkeypatch):
    monkeypatch.setenv("BILLING_BACKEND", "mongo")
    mongo = backends.get_backend()
    calls = []
    monkeypatch.setattr(mongo, "ensure_tenant", lambda tenant_id, email: calls.append(("ensure", tenant_id)))
    monkeypatch.setattr(mongo, "usage_summary", lambda t, s, e: [{"kind": "api", "event_count": "1", "units": "260"}])
    monkeypatch.setattr(mongo, "usage_rating", lambda t, s, e: [{"tenant_id": t, "period_start": s, "period_end": e,
                                                                 "billable_units": "160", "overage_amount": "8.8"}])
    monkeypatch.setattr(mongo, "usage_events", lambda t, s, e: [{"id": "e1", "occurred_at": "2026-02-10T10:00:00",
                                                                 "units": "260", "kind": "api"}])
    response = app.test_client().get(
        "/api/v1/billing/usage",
        query_string={"period_start": "2026-02-01", "period_end": "2026-02-28"},
        headers={"X-User-ID": "t1"},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert calls == [("ensure", "t1")]
    assert body["summary"][0]["units"] == "260"
    assert body["rating"][0] == {"tenant_id": "t1", "period_start": "2026-02-01", "period_end": "2026-02-28",
                                 "billable_units": "160", "overage_amount": "8.8"}
    assert body["events"][0]["kind"] == "api"


def test_facade_usage_on_mongo_rejects_bad_dates_before_backend(monkeypatch):
    monkeypatch.setenv("BILLING_BACKEND", "mongo")
    response = app.test_client().get(
        "/api/v1/billing/usage", query_string={"period_start": "2026-02-30"}, headers={"X-User-ID": "t1"}
    )
    assert response.status_code == 400
    assert response.get_json() == {"error": "invalid date", "detail": "period_start must be an ISO date (YYYY-MM-DD)"}


def test_internal_usage_event_recorded_through_mongo_backend(monkeypatch):
    monkeypatch.setenv("BILLING_BACKEND", "mongo")
    monkeypatch.setenv("USAGE_INTERNAL_TOKEN", "secret")
    mongo = backends.get_backend()
    seen = []
    monkeypatch.setattr(mongo, "ensure_tenant", lambda tenant_id, email: seen.append(("ensure", tenant_id, email)))
    statuses = iter(["recorded", "duplicate"])

    def record(event_id, tenant_id, occurred_at, units, kind):
        seen.append((event_id, tenant_id, occurred_at, units, kind))
        return next(statuses)

    monkeypatch.setattr(mongo, "record_usage_event", record)
    payload = {"event_id": "30000000-0000-0000-0000-00000000ffff", "tenant_id": "t1", "email": "a@example.com",
               "kind": "api", "units": 3, "occurred_at": "2026-02-10T10:00:00Z"}
    client = app.test_client()
    first = client.post("/internal/usage/events", json=payload, headers={"X-Internal-Token": "secret"})
    assert (first.status_code, first.get_json()) == (201, {"status": "recorded"})
    second = client.post("/internal/usage/events", json=payload, headers={"X-Internal-Token": "secret"})
    assert (second.status_code, second.get_json()) == (200, {"status": "duplicate"})
    assert seen[0] == ("ensure", "t1", "a@example.com")
    assert seen[1] == (payload["event_id"], "t1", "2026-02-10T10:00:00Z", 3, "api")


def test_internal_usage_event_on_mongo_keeps_validation_and_rejections(monkeypatch):
    monkeypatch.setenv("BILLING_BACKEND", "mongo")
    monkeypatch.setenv("USAGE_INTERNAL_TOKEN", "secret")
    mongo = backends.get_backend()
    monkeypatch.setattr(mongo, "ensure_tenant", lambda tenant_id, email: None)

    def reject(*args):
        raise mongo.UsageEventRejected("unknown usage kind")

    monkeypatch.setattr(mongo, "record_usage_event", reject)
    client = app.test_client()
    payload = {"event_id": "30000000-0000-0000-0000-00000000ffff", "tenant_id": "t1", "kind": "api", "units": 3,
               "occurred_at": "2026-02-10T10:00:00Z"}
    assert client.post("/internal/usage/events", json=payload, headers={"X-Internal-Token": "nope"}).status_code == 401
    bad = client.post("/internal/usage/events", json={**payload, "kind": "bandwidth"}, headers={"X-Internal-Token": "secret"})
    assert bad.status_code == 400 and bad.get_json()["detail"].startswith("kind must be")
    rejected = client.post("/internal/usage/events", json=payload, headers={"X-Internal-Token": "secret"})
    assert rejected.status_code == 422



def test_facade_invoices_served_by_mongo_backend(monkeypatch):
    monkeypatch.setenv("BILLING_BACKEND", "mongo")
    mongo = backends.get_backend()
    seen = []
    monkeypatch.setattr(mongo, "ensure_tenant", lambda tenant_id, email: seen.append(tenant_id) or True)
    monkeypatch.setattr(
        mongo,
        "invoices_for_tenant",
        lambda tenant_id: [
            {
                "invoice_id": "inv-1",
                "period_start": "2026-02-01",
                "period_end": "2026-02-28",
                "subtotal": "54.56",
                "tax": "4.5",
                "total": "59.06",
                "status": "issued",
            }
        ],
    )
    response = app.test_client().get(
        "/api/v1/billing/invoices", headers={"X-User-ID": "t6"}
    )
    assert response.status_code == 200
    assert response.get_json()[0]["invoice_id"] == "inv-1"
    assert response.get_json()[0]["total"] == "59.06"
    assert seen == ["t6"]


def test_facade_invoice_lines_on_mongo_checks_ownership(monkeypatch):
    monkeypatch.setenv("BILLING_BACKEND", "mongo")
    mongo = backends.get_backend()
    monkeypatch.setattr(mongo, "ensure_tenant", lambda tenant_id, email: True)
    monkeypatch.setattr(mongo, "invoice_owned", lambda invoice_id, tenant_id: tenant_id == "t6")
    monkeypatch.setattr(
        mongo,
        "invoice_lines",
        lambda invoice_id: [
            {"line_no": "1", "line_type": "plan", "description": "GROWTH", "amount": "149"},
            {"line_no": "2", "line_type": "usage", "description": "usage overage", "amount": "12.29"},
        ],
    )
    client = app.test_client()
    owned = client.get("/api/v1/billing/invoices/inv-6/lines", headers={"X-User-ID": "t6"})
    assert owned.status_code == 200
    assert [line["line_type"] for line in owned.get_json()] == ["plan", "usage"]
    foreign = client.get("/api/v1/billing/invoices/inv-6/lines", headers={"X-User-ID": "t3"})
    assert foreign.status_code == 404
    assert foreign.get_json() == {"error": "invoice not found"}


def test_facade_invoices_on_postgres_stay_not_available(monkeypatch):
    monkeypatch.delenv("BILLING_BACKEND", raising=False)
    client = app.test_client()
    for path in ("/api/v1/billing/invoices", "/api/v1/billing/invoices/x/lines"):
        response = client.get(path, headers={"X-User-ID": "t1"})
        assert response.status_code == 501, path
