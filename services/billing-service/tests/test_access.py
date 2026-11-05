from datetime import date
from uuid import UUID

import jwt
from fastapi.testclient import TestClient

import app.main as main
from app.domain import SubscriptionRow

SECRET = "billing-test-key-longer-than-thirty-two-bytes"
TENANT = UUID("00000000-0000-0000-0000-000000000001")
PLAN = UUID("10000000-0000-0000-0000-000000000002")


def token(tenant_id=str(TENANT), roles=None):
    import time

    return jwt.encode(
        {
            "sub": "caller",
            "exp": int(time.time()) + 60,
            "type": "access",
            "roles": roles or ["USER"],
            "tenant_id": tenant_id,
        },
        SECRET,
        algorithm="HS256",
    )


def test_tenant_authentication_and_ownership(monkeypatch):
    from test_plans_api import FakeConnection

    monkeypatch.setenv("JWT_SECRET", SECRET)
    monkeypatch.setattr(main, "migrate", lambda: None)
    monkeypatch.setattr(main, "connect", FakeConnection)
    created = SubscriptionRow(
        UUID("20000000-0000-0000-0000-000000000003"),
        TENANT,
        PLAN,
        date(2026, 3, 1),
        None,
        "active",
        None,
    )
    monkeypatch.setattr(main, "change_plan", lambda *_: ([created], created))
    with TestClient(main.app) as client:
        path = f"/api/tenants/{TENANT}/plan-change"
        body = {"plan_id": str(PLAN), "effective_on": "2026-03-01"}
        assert client.post(path, json=body).status_code == 401
        assert (
            client.post(
                path, json=body, headers={"Authorization": "Bearer " + token("other")}
            ).status_code
            == 403
        )
        assert (
            client.post(path, json=body, headers={"Authorization": "Bearer " + token()}).status_code
            == 200
        )
        assert (
            client.post(
                path, json=body, headers={"Authorization": "Bearer " + token("other", ["ADMIN"])}
            ).status_code
            == 200
        )
        assert client.get(f"/api/tenants/{TENANT}/entitlement?on=2026-03-01").status_code == 401
