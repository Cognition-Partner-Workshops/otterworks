from __future__ import annotations

import base64
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

import app.main as main
from app.domain import EntitlementRow, SubscriptionRow
from tests.conftest import bearer

TENANT_A = UUID("00000000-0000-0000-0000-000000000001")
TENANT_B = UUID("00000000-0000-0000-0000-000000000002")
PLAN = UUID("10000000-0000-0000-0000-000000000002")
PLAN_CHANGE = {"plan_id": str(PLAN), "effective_on": "2026-03-01"}
PROTECTED_ROUTES = sorted(
    (method, route.path)
    for route in main.app.routes
    if isinstance(route, APIRoute) and route.path != "/health"
    for method in route.methods
)


class FakeConnection:
    def __enter__(self) -> FakeConnection:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, _query: str) -> None:
        return None


@pytest.fixture
def calls(monkeypatch) -> list[tuple[str, UUID | None]]:
    """Fakes the data layer and records every call that reaches it."""
    seen: list[tuple[str, UUID | None]] = []

    def fake_entitlement(_rows: object, tenant_id: UUID, on: date) -> EntitlementRow:
        seen.append(("entitlement", tenant_id))
        return EntitlementRow(
            tenant_id, "GROWTH", "growth", Decimal("149.00"), 500, "active", None, on
        )

    def fake_change_plan(_repository: object, tenant_id: UUID, plan_id: UUID, starts_on: date):
        seen.append(("change_plan", tenant_id))
        created = SubscriptionRow(UUID(int=3), tenant_id, plan_id, starts_on, None, "active", None)
        return [created], created

    class FakeRepository:
        def __init__(self, _connection: object) -> None:
            pass

        def find_entitlements(self, _tenant_id: UUID) -> list:
            return []

        def list_plans(self) -> list:
            return []

    monkeypatch.setattr(main, "migrate", lambda: None)
    monkeypatch.setattr(main, "connect", FakeConnection)
    monkeypatch.setattr(main, "PostgresPlansRepository", FakeRepository)
    monkeypatch.setattr(main, "entitlement", fake_entitlement)
    monkeypatch.setattr(main, "change_plan", fake_change_plan)
    monkeypatch.setattr(main, "catalog", lambda _plans: seen.append(("catalog", None)) or [])
    monkeypatch.setattr(main, "reset", lambda: seen.append(("reset", None)))
    monkeypatch.setattr(main.settings, "allow_internal_reset", True)
    return seen


@pytest.fixture
def client(calls) -> TestClient:
    with TestClient(main.app) as test_client:
        yield test_client


def send(client: TestClient, method: str, path: str, headers: dict[str, str] | None = None):
    url = path.replace("{tenant_id}", str(TENANT_B))
    if method == "GET":
        return client.get(url, params={"on": "2026-02-28"}, headers=headers)
    return client.request(method, url, json=PLAN_CHANGE, headers=headers)


def unsigned_token() -> dict[str, str]:
    def segment(value: dict[str, object]) -> str:
        return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=").decode()

    expiry = int((datetime.now(UTC) + timedelta(minutes=5)).timestamp())
    claims = {"sub": "attacker", "aud": "otterworks-billing", "scope": "billing:service"}
    return {
        "Authorization": f"Bearer {segment({'alg': 'none', 'typ': 'JWT'})}."
        f"{segment({**claims, 'exp': expiry})}."
    }


def test_route_inventory_covers_the_tenant_routes() -> None:
    assert ("GET", "/api/tenants/{tenant_id}/entitlement") in PROTECTED_ROUTES
    assert ("POST", "/api/tenants/{tenant_id}/plan-change") in PROTECTED_ROUTES
    assert ("POST", "/internal/reset") in PROTECTED_ROUTES


@pytest.mark.parametrize(("method", "path"), PROTECTED_ROUTES)
def test_every_route_rejects_a_request_without_credentials(client, calls, method, path) -> None:
    response = send(client, method, path)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
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
        unsigned_token(),
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
        "alg-none",
    ],
)
def test_invalid_tokens_are_rejected(client, calls, headers) -> None:
    response = client.get(
        f"/api/tenants/{TENANT_B}/entitlement", params={"on": "2026-02-28"}, headers=headers
    )

    assert response.status_code == 401
    assert calls == []


def test_tenant_token_reads_its_own_entitlement(client, calls) -> None:
    response = client.get(
        f"/api/tenants/{TENANT_A}/entitlement",
        params={"on": "2026-02-28"},
        headers=bearer(tenant=TENANT_A),
    )

    assert response.status_code == 200
    assert response.json()["tenant_id"] == str(TENANT_A)
    assert calls == [("entitlement", TENANT_A)]


def test_tenant_token_cannot_read_another_tenants_entitlement(client, calls) -> None:
    response = client.get(
        f"/api/tenants/{TENANT_B}/entitlement",
        params={"on": "2026-02-28"},
        headers=bearer(tenant=TENANT_A),
    )

    assert response.status_code == 403
    assert calls == []


def test_tenant_token_cannot_change_another_tenants_plan(client, calls) -> None:
    response = client.post(
        f"/api/tenants/{TENANT_B}/plan-change", json=PLAN_CHANGE, headers=bearer(tenant=TENANT_A)
    )

    assert response.status_code == 403
    assert calls == []


def test_token_without_tenant_or_service_scope_cannot_act_for_a_tenant(client, calls) -> None:
    response = client.post(
        f"/api/tenants/{TENANT_B}/plan-change", json=PLAN_CHANGE, headers=bearer()
    )

    assert response.status_code == 403
    assert calls == []


def test_service_token_acts_for_any_tenant(client, calls) -> None:
    read = client.get(
        f"/api/tenants/{TENANT_B}/entitlement",
        params={"on": "2026-02-28"},
        headers=bearer(service=True),
    )
    write = client.post(
        f"/api/tenants/{TENANT_B}/plan-change", json=PLAN_CHANGE, headers=bearer(service=True)
    )

    assert (read.status_code, write.status_code) == (200, 200)
    assert calls == [("entitlement", TENANT_B), ("change_plan", TENANT_B)]


def test_any_authenticated_caller_lists_the_plan_catalogue(client, calls) -> None:
    response = client.get("/api/plans", headers=bearer(tenant=TENANT_A))

    assert response.status_code == 200
    assert calls == [("catalog", None)]


def test_internal_reset_requires_the_service_scope(client, calls) -> None:
    tenant = client.post("/internal/reset", headers=bearer(tenant=TENANT_A))
    service = client.post("/internal/reset", headers=bearer(service=True))

    assert tenant.status_code == 403
    assert service.status_code == 204
    assert calls == [("reset", None)]


def test_health_stays_open_for_the_compose_health_check(client) -> None:
    assert client.get("/health").status_code == 200
