"""QA coverage for the auth area: registration, login/logout, refresh, password rules,
protected routes and token expiry, exercised black-box through the API gateway."""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

import pytest

pytestmark = pytest.mark.api_flow

AUTH = "/api/v1/auth"
PROTECTED_ROUTES = [
    ("GET", "/api/v1/auth/profile"),
    ("GET", "/api/v1/documents/"),
    ("GET", "/api/v1/files/"),
    ("GET", "/api/v1/search/?q=otter"),
    ("POST", "/api/v1/auth/logout"),
    ("POST", "/api/v1/auth/refresh"),
]


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def make_jwt(claims: dict, secret: str, alg: str = "HS256") -> str:
    digest = {"HS256": hashlib.sha256, "HS384": hashlib.sha384}[alg]
    header = _b64url(json.dumps({"alg": alg, "typ": "JWT"}).encode())
    payload = _b64url(json.dumps(claims).encode())
    signing_input = f"{header}.{payload}".encode()
    signature = _b64url(hmac.new(secret.encode(), signing_input, digest).digest())
    return f"{header}.{payload}.{signature}"


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register_raw(api_client, email: str, password: str, display_name: str = "QA User"):
    return api_client.client.post(
        f"{AUTH}/register",
        json={"email": email, "password": password, "displayName": display_name},
    )


def login_raw(api_client, email: str, password: str):
    return api_client.client.post(
        f"{AUTH}/login", json={"email": email, "password": password}
    )


# ── Registration & password validation ────────────────────────


@pytest.mark.parametrize(
    "password,expected",
    [("a" * 7, 400), ("a" * 8, 201), ("a" * 128, 201), ("a" * 129, 400)],
)
def test_register_password_length_boundaries(api_client, password, expected):
    response = register_raw(api_client, api_client.unique_email("pwlen"), password)
    assert response.status_code == expected, response.text


@pytest.mark.parametrize(
    "payload",
    [
        {"password": "OtterworksTest123!", "displayName": "No Email"},
        {"email": "missing-pw@example.test", "displayName": "No Password"},
        {"email": "missing-name@example.test", "password": "OtterworksTest123!"},
        {
            "email": "not-an-email",
            "password": "OtterworksTest123!",
            "displayName": "Bad",
        },
        {
            "email": "blank-name@example.test",
            "password": "OtterworksTest123!",
            "displayName": "",
        },
    ],
)
def test_register_rejects_missing_or_invalid_fields(api_client, payload):
    response = api_client.client.post(f"{AUTH}/register", json=payload)
    assert response.status_code == 400, response.text
    assert response.json()["message"]
    assert "Exception" not in response.text


def test_register_response_shape_and_no_secret_leak(api_client):
    email = api_client.unique_email("shape")
    response = register_raw(api_client, email, "OtterworksTest123!")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["tokenType"] == "Bearer"
    assert body["expiresIn"] > 0
    assert body["user"]["email"] == email
    assert "passwordHash" not in response.text
    assert "OtterworksTest123!" not in response.text


def test_register_duplicate_email_rejected(api_client):
    user = api_client.register_user("dup")
    response = register_raw(api_client, user.email, user.password)
    assert response.status_code == 400
    assert "already" in response.json()["message"].lower()


# ── Login ─────────────────────────────────────────────────────


def test_login_returns_tokens_and_updates_profile(api_client):
    user = api_client.register_user("login")
    data = api_client.login_user(user)
    profile = api_client.client.get(
        f"{AUTH}/profile", headers=bearer(data["accessToken"])
    )
    assert profile.status_code == 200, profile.text
    assert profile.json()["id"] == user.id


def test_login_does_not_enumerate_accounts(api_client):
    user = api_client.register_user("enum")
    wrong_password = login_raw(api_client, user.email, "WrongPassword123!")
    unknown_user = login_raw(
        api_client, api_client.unique_email("ghost"), "WrongPassword123!"
    )
    assert wrong_password.status_code == unknown_user.status_code == 400
    assert wrong_password.json()["message"] == unknown_user.json()["message"]


def test_login_rejects_blank_password(api_client):
    user = api_client.register_user("blankpw")
    response = login_raw(api_client, user.email, "")
    assert response.status_code == 400


# ── Token refresh ─────────────────────────────────────────────


def test_refresh_rotates_and_rejects_reuse(api_client):
    user = api_client.register_user("refresh")
    first = api_client.client.post(
        f"{AUTH}/refresh", headers=bearer(user.refresh_token)
    )
    assert first.status_code == 200, first.text
    rotated = first.json()
    assert rotated["refreshToken"] != user.refresh_token
    profile = api_client.client.get(
        f"{AUTH}/profile", headers=bearer(rotated["accessToken"])
    )
    assert profile.status_code == 200

    reuse = api_client.client.post(
        f"{AUTH}/refresh", headers=bearer(user.refresh_token)
    )
    assert reuse.status_code == 400

    second = api_client.client.post(
        f"{AUTH}/refresh", headers=bearer(rotated["refreshToken"])
    )
    assert second.status_code == 200, second.text


def test_refresh_rejects_access_token(api_client):
    user = api_client.register_user("refresh-access")
    response = api_client.client.post(
        f"{AUTH}/refresh", headers=bearer(user.access_token)
    )
    assert response.status_code == 400


def test_auth_service_rejects_refresh_token_as_access_token(api_client):
    user = api_client.register_user("refresh-profile")
    response = api_client.client.get(
        f"{AUTH}/profile", headers=bearer(user.refresh_token)
    )
    assert response.status_code in {401, 403}


# ── Logout & password change ──────────────────────────────────


def test_logout_revokes_refresh_tokens(api_client):
    user = api_client.register_user("logout")
    logout = api_client.client.post(f"{AUTH}/logout", headers=user.auth_headers)
    assert logout.status_code == 204, logout.text
    refresh = api_client.client.post(
        f"{AUTH}/refresh", headers=bearer(user.refresh_token)
    )
    assert refresh.status_code == 400


def test_logout_requires_token(api_client):
    response = api_client.client.post(f"{AUTH}/logout")
    assert response.status_code == 401


def test_change_password_rotates_credentials(api_client):
    user = api_client.register_user("chpw")
    new_password = "NewOtterworks456!"
    wrong = api_client.client.post(
        f"{AUTH}/change-password",
        headers=user.auth_headers,
        json={"currentPassword": "not-it", "newPassword": new_password},
    )
    assert wrong.status_code == 400
    changed = api_client.client.post(
        f"{AUTH}/change-password",
        headers=user.auth_headers,
        json={"currentPassword": user.password, "newPassword": new_password},
    )
    assert changed.status_code == 204, changed.text
    assert login_raw(api_client, user.email, user.password).status_code == 400
    assert login_raw(api_client, user.email, new_password).status_code == 200
    refresh = api_client.client.post(
        f"{AUTH}/refresh", headers=bearer(user.refresh_token)
    )
    assert refresh.status_code == 400


# ── Protected routes & token validity ─────────────────────────


@pytest.mark.parametrize("method,path", PROTECTED_ROUTES)
def test_protected_routes_require_token(api_client, method, path):
    response = api_client.client.request(method, path)
    assert response.status_code == 401, response.text


@pytest.mark.parametrize("method,path", PROTECTED_ROUTES[:4])
def test_protected_routes_reject_forged_token(api_client, method, path):
    forged = make_jwt(
        {"sub": "forged-user", "type": "access", "exp": int(time.time()) + 3600},
        secrets.token_hex(32),
    )
    response = api_client.client.request(method, path, headers=bearer(forged))
    assert response.status_code == 401, response.text


def test_gateway_rejects_tampered_token(api_client):
    user = api_client.register_user("tamper")
    header, _payload, signature = user.access_token.split(".")
    evil_payload = _b64url(
        json.dumps(
            {"sub": "00000000-0000-0000-0000-000000000001", "roles": ["ADMIN"]}
        ).encode()
    )
    response = api_client.client.get(
        "/api/v1/documents/", headers=bearer(f"{header}.{evil_payload}.{signature}")
    )
    assert response.status_code == 401


def test_expired_access_token_rejected(api_client):
    """Session expiry: needs the stack's signing key in OTTERWORKS_JWT_SECRET."""
    secret = os.getenv("OTTERWORKS_JWT_SECRET")
    if not secret:
        pytest.skip("OTTERWORKS_JWT_SECRET not set")
    user = api_client.register_user("expired")
    now = int(time.time())
    claims = {"sub": user.id, "email": user.email, "roles": ["USER"], "type": "access"}
    fresh = make_jwt({**claims, "iat": now, "exp": now + 600}, secret, "HS384")
    expired = make_jwt(
        {**claims, "iat": now - 7200, "exp": now - 3600}, secret, "HS384"
    )
    assert (
        api_client.client.get("/api/v1/documents/", headers=bearer(fresh)).status_code
        == 200
    )
    for path in ("/api/v1/documents/", f"{AUTH}/profile"):
        response = api_client.client.get(path, headers=bearer(expired))
        assert response.status_code == 401, (path, response.text)


# ── Known defects (strict xfail so a fix flips them to XPASS) ─


@pytest.mark.xfail(
    strict=True,
    reason="[REAL] gateway-accepts-refresh-token: api-gateway JWTAuth ignores the `type` claim",
)
def test_gateway_rejects_refresh_token_as_access_token(api_client):
    user = api_client.register_user("gw-refresh")
    response = api_client.client.get(
        "/api/v1/documents/", headers=bearer(user.refresh_token)
    )
    assert response.status_code == 401, response.text


@pytest.mark.xfail(
    strict=True,
    reason="[REAL] auth-email-case: login email comparison is case-sensitive",
)
def test_login_email_is_case_insensitive(api_client):
    user = api_client.register_user("CaseQA")
    response = login_raw(api_client, user.email.upper(), user.password)
    assert response.status_code == 200, response.text


@pytest.mark.xfail(
    strict=True,
    reason="[REAL] auth-email-case: same email with different case creates a second account",
)
def test_register_duplicate_email_differing_in_case_rejected(api_client):
    user = api_client.register_user("casedup")
    response = register_raw(api_client, user.email.upper(), user.password)
    assert response.status_code == 400, response.text


@pytest.mark.xfail(
    strict=True,
    reason="[REAL] auth-malformed-500: malformed request bodies return HTTP 500",
)
@pytest.mark.parametrize(
    "content,content_type",
    [
        ("{", "application/json"),
        ("", "application/json"),
        ("[]", "application/json"),
        ("x", "text/plain"),
    ],
)
def test_login_malformed_body_returns_400(api_client, content, content_type):
    response = api_client.client.post(
        f"{AUTH}/login", content=content, headers={"Content-Type": content_type}
    )
    assert response.status_code == 400, response.text
