from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

import app as legacy
from conftest import bearer

TENANT_A = "00000000-0000-0000-0000-000000000001"
TENANT_B = "00000000-0000-0000-0000-000000000002"
INVOICE_A = "60000000-0000-0000-0000-00000000000a"
INVOICE_B = "60000000-0000-0000-0000-00000000000b"
PLAN = "10000000-0000-0000-0000-000000000001"
PERIOD = {"period_start": "2026-02-01", "period_end": "2026-02-28"}
INVOICE_OWNERS = {INVOICE_A: TENANT_A, INVOICE_B: TENANT_B}


def tenant_requests(tenant, invoice):
    """Every request that names a tenant or one of its invoices."""
    return {
        "entitlement": ("GET", f"/plans/{tenant}/entitlement", {}),
        "change_plan": (
            "POST",
            f"/plans/{tenant}/change",
            {"data": {"plan_id": PLAN, "effective_on": "2026-03-01"}},
        ),
        "rating_preview": ("POST", "/api/rating/preview", {"json": {"tenant_id": tenant, **PERIOD}}),
        "rating_finalize": (
            "POST",
            "/api/rating/finalize",
            {"json": {"tenant_id": tenant, **PERIOD}},
        ),
        "invoice_preview": ("GET", f"/api/invoices/{tenant}/preview", {}),
        "invoice_issue": ("POST", f"/api/invoices/{tenant}/issue", {"data": PERIOD}),
        "invoice_lines": ("GET", f"/api/invoices/{invoice}/lines", {}),
    }


GLOBAL_REQUESTS = {
    "overdue": ("GET", "/api/dunning/overdue", {}),
    "schedule_dunning": ("POST", "/api/dunning/schedule", {"data": {"as_of": "2026-02-28"}}),
    "suspend_overdue": ("POST", "/api/dunning/suspend", {"data": {"as_of": "2026-02-28"}}),
}
CATALOGUE_REQUESTS = {"index": ("GET", "/", {}), "plans": ("GET", "/plans", {})}
REQUESTS_FOR_B = {**tenant_requests(TENANT_B, INVOICE_B), **GLOBAL_REQUESTS, **CATALOGUE_REQUESTS}


@pytest.fixture
def calls(monkeypatch):
    """Fakes the database and records every procedure call that reaches it."""
    seen = []

    def fake_select(sql, params=()):
        if "FROM billing.invoices" in sql:
            owner = INVOICE_OWNERS.get(str(params[0]))
            return [{"tenant_id": owner}] if owner else []
        seen.append(sql)
        return []

    monkeypatch.setattr(legacy, "select", fake_select)
    monkeypatch.setattr(legacy, "execute", lambda sql, params=(): seen.append(sql))
    return seen


@pytest.fixture
def client(calls):
    return legacy.app.test_client()


def send(client, request, headers=None):
    method, path, kwargs = request
    return client.open(path, method=method, headers=headers, **kwargs)


def test_request_table_covers_every_route() -> None:
    endpoints = {rule.endpoint for rule in legacy.app.url_map.iter_rules()}

    assert endpoints - {"static", "health"} == set(REQUESTS_FOR_B)


@pytest.mark.parametrize("endpoint", sorted(REQUESTS_FOR_B))
def test_every_route_rejects_a_request_without_credentials(client, calls, endpoint) -> None:
    response = send(client, REQUESTS_FOR_B[endpoint])

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert calls == []


@pytest.mark.parametrize(
    "headers",
    [
        {"Authorization": "Bearer not-a-jwt"},
        {"Authorization": "Basic dXNlcjpwYXNz"},
        bearer(service=True, secret="a-different-signing-key-of-sufficient-length"),
        bearer(service=True, exp=datetime.now(UTC) - timedelta(minutes=1)),
        bearer(service=True, exp=None),
        bearer(service=True, aud="some-other-service"),
        bearer(service=True, aud=None),
        bearer(tenant=TENANT_B, sub=None),
        bearer(tenant_id="not-a-uuid"),
    ],
    ids=[
        "garbage",
        "basic-scheme",
        "wrong-key",
        "expired",
        "no-expiry",
        "wrong-audience",
        "no-audience",
        "no-subject",
        "malformed-tenant",
    ],
)
def test_invalid_tokens_are_rejected(client, calls, headers) -> None:
    response = client.get(f"/api/invoices/{TENANT_B}/preview", headers=headers)

    assert response.status_code == 401
    assert calls == []


@pytest.mark.parametrize("endpoint", sorted(tenant_requests(TENANT_B, INVOICE_B)))
def test_tenant_token_cannot_act_for_another_tenant(client, calls, endpoint) -> None:
    response = send(client, REQUESTS_FOR_B[endpoint], bearer(tenant=TENANT_A))

    assert response.status_code == (404 if endpoint == "invoice_lines" else 403)
    assert calls == []


@pytest.mark.parametrize("endpoint", sorted(tenant_requests(TENANT_A, INVOICE_A)))
def test_tenant_token_acts_for_its_own_tenant(client, calls, endpoint) -> None:
    response = send(client, tenant_requests(TENANT_A, INVOICE_A)[endpoint], bearer(tenant=TENANT_A))

    assert response.status_code in {200, 302}
    assert len(calls) == 1


def test_tenant_token_gets_the_same_answer_for_a_missing_and_a_foreign_invoice(client, calls) -> None:
    foreign = client.get(f"/api/invoices/{INVOICE_B}/lines", headers=bearer(tenant=TENANT_A))
    missing = client.get(
        "/api/invoices/60000000-0000-0000-0000-0000000000ff/lines", headers=bearer(tenant=TENANT_A)
    )

    assert (foreign.status_code, foreign.data) == (missing.status_code, missing.data)
    assert calls == []


@pytest.mark.parametrize("endpoint", sorted(GLOBAL_REQUESTS))
def test_cross_tenant_dunning_requires_the_service_scope(client, calls, endpoint) -> None:
    tenant = send(client, GLOBAL_REQUESTS[endpoint], bearer(tenant=TENANT_A))
    assert tenant.status_code == 403
    assert calls == []

    service = send(client, GLOBAL_REQUESTS[endpoint], bearer(service=True))
    assert service.status_code == 200
    assert len(calls) == 1


@pytest.mark.parametrize("endpoint", sorted(tenant_requests(TENANT_B, INVOICE_B)))
def test_service_token_acts_for_any_tenant(client, calls, endpoint) -> None:
    response = send(client, REQUESTS_FOR_B[endpoint], bearer(service=True))

    assert response.status_code in {200, 302}
    assert len(calls) == 1


@pytest.mark.parametrize("endpoint", sorted(CATALOGUE_REQUESTS))
def test_any_authenticated_caller_reads_the_plan_catalogue(client, calls, endpoint) -> None:
    response = send(client, CATALOGUE_REQUESTS[endpoint], bearer(tenant=TENANT_A))

    assert response.status_code == 200


def test_token_without_tenant_or_service_scope_cannot_act_for_a_tenant(client, calls) -> None:
    response = client.get(f"/api/invoices/{TENANT_B}/preview", headers=bearer())

    assert response.status_code == 403
    assert calls == []


def test_health_stays_open_for_the_compose_health_check(client) -> None:
    assert client.get("/health").status_code == 200
