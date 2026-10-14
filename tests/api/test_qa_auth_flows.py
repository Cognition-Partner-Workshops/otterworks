import base64
import hashlib
import hmac
import json
import os
import time

import pytest


pytestmark = pytest.mark.api_flow

LOCAL_DEV_JWT_SECRET = "otterworks-local-dev-jwt-secret-change-me-in-production"


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _decode_payload(token: str) -> dict:
    payload = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))


def _sign(claims: dict, secret: str, alg: str = "HS256") -> str:
    header = _b64(json.dumps({"alg": alg, "typ": "JWT"}).encode())
    body = _b64(json.dumps(claims).encode())
    signature = hmac.new(secret.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest()
    return f"{header}.{body}.{_b64(signature)}"


def _jwt_secret() -> str:
    return os.getenv("OTTERWORKS_JWT_SECRET", LOCAL_DEV_JWT_SECRET)


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def seeded_admin() -> tuple[str, str]:
    email = os.getenv("OTTERWORKS_WEB_LOGIN_EMAIL")
    password = os.getenv("OTTERWORKS_WEB_LOGIN_PASSWORD")
    if not email or not password:
        pytest.skip("OTTERWORKS_WEB_LOGIN_EMAIL / OTTERWORKS_WEB_LOGIN_PASSWORD not set")
    return email, password


def test_register_returns_tokens_and_user_role(api_client):
    user = api_client.register_user("qa-auth-register")

    claims = _decode_payload(user.access_token)
    assert claims["sub"] == user.id
    assert claims["type"] == "access"
    assert claims["roles"] == ["USER"]
    assert claims["exp"] > time.time()

    profile = api_client.client.get("/api/v1/auth/profile", headers=user.auth_headers)
    assert profile.status_code == 200, profile.text
    body = profile.json()
    assert body["email"] == user.email
    assert "passwordHash" not in body and "password" not in body


def test_register_then_login_with_new_credentials(api_client):
    user = api_client.register_user("qa-auth-relogin")
    data = api_client.login_user(user)
    assert data["user"]["id"] == user.id
    assert data["accessToken"] != user.access_token or data["refreshToken"] != user.refresh_token


def test_seeded_admin_login_profile_and_admin_listing(api_client, seeded_admin):
    email, password = seeded_admin
    response = api_client.client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.status_code
    data = response.json()
    assert data["tokenType"] == "Bearer"
    assert "ADMIN" in _decode_payload(data["accessToken"])["roles"]

    profile = api_client.client.get("/api/v1/auth/profile", headers=_bearer(data["accessToken"]))
    assert profile.status_code == 200
    assert profile.json()["email"] == email

    users = api_client.client.get("/api/v1/auth/users", headers=_bearer(data["accessToken"]))
    assert users.status_code == 200, users.text

    logout = api_client.client.post("/api/v1/auth/logout", headers=_bearer(data["accessToken"]))
    assert logout.status_code == 204
    reuse = api_client.client.post("/api/v1/auth/refresh", headers=_bearer(data["refreshToken"]))
    assert reuse.status_code in {400, 401, 403}


def test_invalid_credentials_are_rejected_without_user_enumeration(api_client):
    user = api_client.register_user("qa-auth-invalid")
    wrong_password = api_client.client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "NotTheRightPassword1!"}
    )
    unknown_user = api_client.client.post(
        "/api/v1/auth/login",
        json={"email": api_client.unique_email("qa-auth-ghost"), "password": "Whatever123!"},
    )
    for response in (wrong_password, unknown_user):
        assert response.status_code in {400, 401}, response.text
        assert "accessToken" not in response.text
    assert wrong_password.status_code == unknown_user.status_code
    assert wrong_password.json().get("message") == unknown_user.json().get("message")


def test_login_rejects_malformed_payloads(api_client):
    for payload in ({}, {"email": "not-an-email", "password": "x"}, {"email": "a@b.test"}):
        response = api_client.client.post("/api/v1/auth/login", json=payload)
        assert response.status_code == 400, (payload, response.status_code)


def test_refresh_rotates_and_old_refresh_token_is_revoked(api_client):
    user = api_client.register_user("qa-auth-rotate")
    first = api_client.client.post("/api/v1/auth/refresh", headers=_bearer(user.refresh_token))
    assert first.status_code == 200, first.text
    rotated = first.json()
    assert rotated["refreshToken"] != user.refresh_token

    profile = api_client.client.get("/api/v1/auth/profile", headers=_bearer(rotated["accessToken"]))
    assert profile.status_code == 200

    replay = api_client.client.post("/api/v1/auth/refresh", headers=_bearer(user.refresh_token))
    assert replay.status_code in {400, 401, 403}

    second = api_client.client.post("/api/v1/auth/refresh", headers=_bearer(rotated["refreshToken"]))
    assert second.status_code == 200, second.text


def test_refresh_rejects_access_token(api_client):
    user = api_client.register_user("qa-auth-refresh-access")
    response = api_client.client.post("/api/v1/auth/refresh", headers=_bearer(user.access_token))
    assert response.status_code in {400, 401, 403}


def test_refresh_without_authorization_header_is_client_error(api_client):
    response = api_client.client.post("/api/v1/auth/refresh")
    assert 400 <= response.status_code < 500, response.status_code


def test_logout_revokes_refresh_tokens(api_client):
    user = api_client.register_user("qa-auth-logout")
    logout = api_client.client.post("/api/v1/auth/logout", headers=user.auth_headers)
    assert logout.status_code == 204, logout.text
    refresh = api_client.client.post("/api/v1/auth/refresh", headers=_bearer(user.refresh_token))
    assert refresh.status_code in {400, 401, 403}


def test_protected_routes_require_a_token(api_client):
    for path in ("/api/v1/auth/profile", "/api/v1/documents", "/api/v1/files"):
        response = api_client.client.get(path)
        assert response.status_code == 401, (path, response.status_code)


def test_malformed_authorization_headers_are_rejected(api_client):
    user = api_client.register_user("qa-auth-malformed")
    for header in (user.access_token, f"Basic {user.access_token}", "Bearer not.a.jwt", "Bearer"):
        response = api_client.client.get("/api/v1/documents", headers={"Authorization": header})
        assert response.status_code == 401, (header[:12], response.status_code)


def test_tampered_token_is_rejected(api_client):
    user = api_client.register_user("qa-auth-tamper")
    header, _, signature = user.access_token.split(".")
    claims = _decode_payload(user.access_token)
    claims["roles"] = ["ADMIN"]
    forged = f"{header}.{_b64(json.dumps(claims).encode())}.{signature}"
    for path in ("/api/v1/auth/profile", "/api/v1/documents", "/api/v1/auth/users"):
        response = api_client.client.get(path, headers=_bearer(forged))
        assert response.status_code == 401, (path, response.status_code)


def test_alg_none_token_is_rejected(api_client):
    user = api_client.register_user("qa-auth-none")
    claims = _decode_payload(user.access_token)
    unsigned = f"{_b64(b'{\"alg\":\"none\",\"typ\":\"JWT\"}')}.{_b64(json.dumps(claims).encode())}."
    response = api_client.client.get("/api/v1/documents", headers=_bearer(unsigned))
    assert response.status_code == 401


def test_expired_access_token_is_rejected(api_client):
    user = api_client.register_user("qa-auth-expired")
    claims = _decode_payload(user.access_token)
    claims["iat"] = int(time.time()) - 7200
    claims["exp"] = int(time.time()) - 60
    expired = _sign(claims, _jwt_secret())
    for path in ("/api/v1/auth/profile", "/api/v1/documents"):
        response = api_client.client.get(path, headers=_bearer(expired))
        assert response.status_code == 401, (path, response.status_code)


def test_expired_refresh_token_is_rejected(api_client):
    user = api_client.register_user("qa-auth-expired-refresh")
    claims = _decode_payload(user.refresh_token)
    claims["iat"] = int(time.time()) - 7200
    claims["exp"] = int(time.time()) - 60
    expired = _sign(claims, _jwt_secret())
    response = api_client.client.post("/api/v1/auth/refresh", headers=_bearer(expired))
    assert response.status_code == 401, response.status_code


def test_access_token_lifetime_is_one_hour(api_client):
    user = api_client.register_user("qa-auth-lifetime")
    claims = _decode_payload(user.access_token)
    assert claims["exp"] - claims["iat"] == 3600


def test_refresh_token_cannot_be_used_as_access_token(api_client):
    user = api_client.register_user("qa-auth-refresh-as-access")
    statuses = {
        path: api_client.client.get(path, headers=_bearer(user.refresh_token)).status_code
        for path in ("/api/v1/auth/profile", "/api/v1/documents", "/api/v1/files")
    }
    assert all(code in {401, 403} for code in statuses.values()), statuses


def test_non_admin_cannot_list_users(api_client):
    user = api_client.register_user("qa-auth-nonadmin")
    response = api_client.client.get("/api/v1/auth/users", headers=user.auth_headers)
    assert response.status_code == 403, response.status_code
