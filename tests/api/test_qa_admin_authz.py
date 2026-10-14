"""QA: authentication / authorization of admin-service routes through the gateway."""

import base64
import json
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.api_flow

ADMIN = "/api/v1/admin"
PROTECTED = [
    ("GET", f"{ADMIN}/users"),
    ("GET", f"{ADMIN}/metrics/summary"),
    ("GET", f"{ADMIN}/audit-logs"),
    ("GET", f"{ADMIN}/settings/auto_investigate"),
    ("PUT", f"{ADMIN}/settings/auto_investigate"),
    ("GET", f"{ADMIN}/features"),
    ("GET", f"{ADMIN}/announcements"),
    ("GET", f"{ADMIN}/health/services"),
]
AUTH_SERVICE_TS = (
    Path(__file__).resolve().parents[2] / "frontend/admin-dashboard/src/app/core/services/auth.service.ts"
)


def _b64(data: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()


@pytest.mark.parametrize("method,path", PROTECTED)
def test_admin_routes_reject_missing_token(api_client, method, path):
    response = api_client.client.request(method, path, json={"enabled": True} if method == "PUT" else None)
    assert response.status_code == 401, f"{method} {path} -> {response.status_code}"
    api_client.assert_json_error(response)


@pytest.mark.parametrize("method,path", PROTECTED[:3])
def test_admin_routes_reject_tampered_token(api_client, method, path):
    user = api_client.register_user("qa-admin-tamper")
    header, payload, signature = user.access_token.split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    claims["roles"] = ["ADMIN"]
    forged = f"{header}.{_b64(claims)}.{signature}"
    response = api_client.client.request(method, path, headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401


def test_admin_routes_reject_unsigned_token(api_client):
    token = f"{_b64({'alg': 'none', 'typ': 'JWT'})}.{_b64({'sub': 'attacker', 'role': 'super_admin'})}."
    response = api_client.client.get(f"{ADMIN}/users", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_admin_routes_reject_basic_scheme(api_client):
    user = api_client.register_user("qa-admin-basic")
    response = api_client.client.get(f"{ADMIN}/users", headers={"Authorization": f"Basic {user.access_token}"})
    assert response.status_code == 401


@pytest.mark.gap_revealer
def test_regular_user_cannot_list_admin_users(api_client):
    user = api_client.register_user("qa-admin-plain-user")
    response = api_client.client.get(f"{ADMIN}/users", headers=user.auth_headers)
    assert response.status_code in {401, 403}, (
        f"non-admin token (roles={['USER']}) got {response.status_code} on admin user list"
    )


@pytest.mark.gap_revealer
def test_regular_user_cannot_suspend_admin_users(api_client):
    user = api_client.register_user("qa-admin-plain-user")
    response = api_client.client.put(f"{ADMIN}/users/00000000-0000-0000-0000-000000000000/suspend",
                                     headers=user.auth_headers)
    assert response.status_code in {401, 403}, (
        f"non-admin token reached the suspend handler (status {response.status_code})"
    )


@pytest.mark.gap_revealer
def test_regular_user_cannot_change_admin_settings(api_client):
    user = api_client.register_user("qa-admin-plain-user")
    response = api_client.client.put(f"{ADMIN}/settings/auto_investigate", headers=user.auth_headers, json={})
    assert response.status_code in {401, 403}, f"non-admin reached settings handler ({response.status_code})"


@pytest.mark.gap_revealer
def test_dashboard_offline_mock_token_is_not_accepted_by_gateway(api_client):
    """auth.service.ts ships a hard-coded JWT for its offline fallback; it must not unlock real APIs."""
    match = re.search(r"token: '(eyJ[^']+)'", AUTH_SERVICE_TS.read_text())
    assert match, "mock token not found in auth.service.ts"
    response = api_client.client.get(f"{ADMIN}/users", headers={"Authorization": f"Bearer {match.group(1)}"})
    assert response.status_code == 401, (
        f"hard-coded dashboard mock token is accepted by the gateway ({response.status_code})"
    )
