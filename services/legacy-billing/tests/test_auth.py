import jwt
import pytest

import app as legacy_app

SECRET = "test-secret"
TENANT_A = "00000000-0000-0000-0000-000000000001"
TENANT_B = "00000000-0000-0000-0000-000000000005"
INVOICE_B = "00000000-0000-0000-0000-00000000b001"
PLAN = "10000000-0000-0000-0000-000000000001"


def token(tenant_ids=(TENANT_A,), roles=("USER",), secret=SECRET, **extra):
    claims = {"sub": "user-1", "roles": list(roles), "tenant_ids": list(tenant_ids), **extra}
    return jwt.encode(claims, secret, algorithm="HS256")


def bearer(value):
    return {"Authorization": f"Bearer {value}"}


@pytest.fixture
def db(monkeypatch):
    calls = {"select": [], "execute": []}

    def fake_select(sql, params=()):
        calls["select"].append((sql, params))
        if "FROM billing.invoices" in sql:
            return [{"tenant_id": TENANT_B}] if params[0] == INVOICE_B else []
        return [{"tenant_id": params[0] if params else None}]

    def fake_execute(sql, params=()):
        calls["execute"].append((sql, params))

    monkeypatch.setattr(legacy_app, "select", fake_select)
    monkeypatch.setattr(legacy_app, "execute", fake_execute)
    return calls


@pytest.fixture
def client(monkeypatch, db):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    legacy_app.app.config["TESTING"] = True
    return legacy_app.app.test_client()


def test_health_and_catalog_stay_public(client):
    assert client.get("/health").status_code == 200
    assert client.get("/plans").status_code == 200


def test_tenant_route_requires_bearer_token(client, db):
    response = client.get(f"/plans/{TENANT_B}/entitlement")
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert db["select"] == []


def test_forged_token_is_rejected(client, db):
    response = client.get(
        f"/plans/{TENANT_A}/entitlement", headers=bearer(token(secret="wrong"))
    )
    assert response.status_code == 401
    assert db["select"] == []


def test_unsigned_token_is_rejected(client, db):
    unsigned = jwt.encode({"sub": "user-1", "tenant_ids": [TENANT_A]}, None, algorithm="none")
    assert client.get(f"/plans/{TENANT_A}/entitlement", headers=bearer(unsigned)).status_code == 401
    assert db["select"] == []


def test_missing_secret_fails_closed(client, db, monkeypatch):
    monkeypatch.delenv("JWT_SECRET")
    assert client.get(f"/plans/{TENANT_A}/entitlement", headers=bearer(token())).status_code == 401
    assert db["select"] == []


def test_caller_can_read_own_tenant(client, db):
    response = client.get(f"/plans/{TENANT_A}/entitlement", headers=bearer(token()))
    assert response.status_code == 200
    assert db["select"][0][1][0] == TENANT_A


def test_cross_tenant_read_is_rejected(client, db):
    response = client.get(f"/plans/{TENANT_B}/entitlement", headers=bearer(token()))
    assert response.status_code == 403
    assert db["select"] == []


def test_cross_tenant_plan_change_is_rejected(client, db):
    response = client.post(
        f"/plans/{TENANT_B}/change",
        data={"plan_id": PLAN, "effective_on": "2026-03-01"},
        headers=bearer(token()),
    )
    assert response.status_code == 403
    assert db["execute"] == []


def test_cross_tenant_invoice_issue_is_rejected(client, db):
    response = client.post(
        f"/api/invoices/{TENANT_B}/issue",
        data={"period_start": "2026-02-01", "period_end": "2026-02-28"},
        headers=bearer(token()),
    )
    assert response.status_code == 403
    assert db["execute"] == []


def test_body_tenant_is_bound_to_principal(client, db):
    body = {"tenant_id": TENANT_B, "period_start": "2026-02-01", "period_end": "2026-02-28"}
    assert client.post("/api/rating/finalize", json=body, headers=bearer(token())).status_code == 403
    assert db["execute"] == []
    body["tenant_id"] = TENANT_A
    assert client.post("/api/rating/finalize", json=body, headers=bearer(token())).status_code == 200
    assert db["execute"][0][1][0] == TENANT_A


def test_body_tenant_is_required(client, db):
    body = {"period_start": "2026-02-01", "period_end": "2026-02-28"}
    assert client.post("/api/rating/preview", json=body, headers=bearer(token())).status_code == 400
    assert db["select"] == []


def test_invoice_lines_resolve_owning_tenant(client, db):
    assert client.get(f"/api/invoices/{INVOICE_B}/lines", headers=bearer(token())).status_code == 403
    assert all("fn_invoice_lines" not in sql for sql, _ in db["select"])
    ok = client.get(f"/api/invoices/{INVOICE_B}/lines", headers=bearer(token(tenant_ids=[TENANT_B])))
    assert ok.status_code == 200
    unknown = "00000000-0000-0000-0000-00000000dead"
    assert client.get(f"/api/invoices/{unknown}/lines", headers=bearer(token())).status_code == 404


def test_dunning_requires_operator_role(client, db):
    assert client.get("/api/dunning/overdue", headers=bearer(token())).status_code == 403
    assert client.post("/api/dunning/suspend", data={"as_of": "2026-02-28"}, headers=bearer(token())).status_code == 403
    assert db["select"] == [] and db["execute"] == []
    admin = token(tenant_ids=[], roles=["ADMIN"])
    assert client.get("/api/dunning/overdue", headers=bearer(admin)).status_code == 200


def test_admin_may_act_across_tenants(client, db):
    admin = token(tenant_ids=[], roles=["ADMIN"])
    assert client.get(f"/plans/{TENANT_B}/entitlement", headers=bearer(admin)).status_code == 200


def test_single_tenant_id_claim_is_accepted(client, db):
    single = jwt.encode({"sub": "user-2", "tenant_id": TENANT_B}, SECRET, algorithm="HS256")
    assert client.get(f"/plans/{TENANT_B}/entitlement", headers=bearer(single)).status_code == 200
    assert client.get(f"/plans/{TENANT_A}/entitlement", headers=bearer(single)).status_code == 403


def test_malformed_tenant_id_is_rejected_before_db(client, db):
    assert client.get("/plans/not-a-uuid/entitlement", headers=bearer(token())).status_code == 400
    assert db["select"] == []
