import time
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import UUID

import jwt
from fastapi.testclient import TestClient
from test_access import PLAN, SECRET, TENANT
from test_plans_api import CREATED

import app.main as main
from app.domain import EntitlementRow
from app.repository import PostgresPlansRepository

USER = UUID("a0000000-0000-0000-0000-000000000002")


def test_customer_tokens_without_tenant_claims_use_server_membership(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    monkeypatch.setattr(main, "migrate", lambda: None)
    connection = MagicMock()
    connection.__enter__.return_value = connection
    monkeypatch.setattr(main, "connect", lambda: connection)
    memberships = {(TENANT, USER)}

    def execute(_sql, parameters):
        result = MagicMock()
        result.fetchone.return_value = {"member": 1} if parameters in memberships else None
        return result

    connection.execute.side_effect = execute
    monkeypatch.setattr(
        main,
        "entitlement",
        lambda *_: EntitlementRow(
            TENANT,
            "STARTER",
            "starter",
            Decimal("49.00"),
            100,
            "active",
            None,
            date(2026, 3, 1),
        ),
    )
    monkeypatch.setattr(main, "change_plan", lambda *_: ([CREATED], CREATED))
    token = jwt.encode(
        {
            "sub": str(USER),
            "email": "customer@otterworks.dev",
            "roles": ["USER"],
            "type": "access",
            "iat": int(time.time()),
            "exp": int(time.time()) + 60,
        },
        SECRET,
        algorithm="HS256",
    )
    headers = {"Authorization": "Bearer " + token}
    with TestClient(main.app) as client:
        read = f"/api/tenants/{TENANT}/entitlement?on=2026-03-01"
        write = f"/api/tenants/{TENANT}/plan-change"
        payload = {"plan_id": str(PLAN), "effective_on": "2026-03-01"}
        assert client.get(read, headers=headers).status_code == 200
        assert client.post(write, headers=headers, json=payload).status_code == 200
        assert connection.execute.call_args.args[1] == (TENANT, USER)
        foreign = UUID("00000000-0000-0000-0000-000000000002")
        assert (
            client.get(read.replace(str(TENANT), str(foreign)), headers=headers).status_code == 403
        )
        assert (
            client.post(
                write.replace(str(TENANT), str(foreign)), headers=headers, json=payload
            ).status_code
            == 403
        )
        memberships.clear()
        assert client.get(read, headers=headers).status_code == 403
        assert client.post(write, headers=headers, json=payload).status_code == 403
        assert client.get(read, headers={"X-User-ID": str(USER)}).status_code == 401
        assert client.post(write, headers={"X-User-ID": str(USER)}, json=payload).status_code == 401


def test_membership_query_is_parameterized_and_scoped():
    connection = MagicMock()
    connection.execute.return_value.fetchone.return_value = None
    assert not PostgresPlansRepository(connection).is_tenant_member(TENANT, USER)
    sql, parameters = connection.execute.call_args.args
    assert "tenant_id = %s AND user_id = %s" in sql
    assert parameters == (TENANT, USER)


def test_invalid_identity_never_reaches_membership_lookup(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    monkeypatch.setattr(main, "migrate", lambda: None)
    connect = MagicMock(side_effect=AssertionError("Unauthenticated database lookup"))
    monkeypatch.setattr(main, "connect", connect)
    claims = {"sub": str(USER), "type": "access", "exp": int(time.time()) + 60}
    invalid = [
        "not-a-jwt",
        jwt.encode(claims, "wrong-signing-key-that-is-at-least-32-bytes", algorithm="HS256"),
        jwt.encode({**claims, "exp": 1}, SECRET, algorithm="HS256"),
        jwt.encode({**claims, "type": "refresh"}, SECRET, algorithm="HS256"),
    ]
    with TestClient(main.app) as client:
        for token in invalid:
            headers = {"Authorization": "Bearer " + token}
            assert (
                client.get(f"/api/tenants/{TENANT}/entitlement", headers=headers).status_code == 401
            )
            assert (
                client.post(f"/api/tenants/{TENANT}/plan-change", headers=headers).status_code
                == 401
            )
    connect.assert_not_called()
