import base64
import json

import pytest


pytestmark = pytest.mark.api_flow


def test_register_login_profile_refresh_and_logout(api_client):
    user = api_client.register_user("auth-flow")

    login_data = api_client.login_user(user)
    assert login_data["tokenType"] == "Bearer"
    assert login_data["accessToken"]
    assert login_data["refreshToken"]
    assert login_data["user"]["email"] == user.email

    profile_response = api_client.client.get(
        "/api/v1/auth/profile",
        headers={"Authorization": f"Bearer {login_data['accessToken']}"},
    )
    assert profile_response.status_code == 200, profile_response.text
    assert profile_response.json()["email"] == user.email

    update_response = api_client.client.put(
        "/api/v1/auth/profile",
        headers={"Authorization": f"Bearer {login_data['accessToken']}"},
        json={"displayName": "API Flow Updated User"},
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["displayName"] == "API Flow Updated User"

    refresh_response = api_client.client.post(
        "/api/v1/auth/refresh",
        headers={"Authorization": f"Bearer {login_data['refreshToken']}"},
    )
    assert refresh_response.status_code == 200, refresh_response.text
    refreshed = refresh_response.json()
    assert refreshed["accessToken"]
    assert refreshed["refreshToken"]
    assert refreshed["refreshToken"] != login_data["refreshToken"]

    reused_refresh_response = api_client.client.post(
        "/api/v1/auth/refresh",
        headers={"Authorization": f"Bearer {login_data['refreshToken']}"},
    )
    assert reused_refresh_response.status_code in {400, 401, 403}

    logout_response = api_client.client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {refreshed['accessToken']}"},
    )
    assert logout_response.status_code == 204, logout_response.text


def test_auth_validation_and_protected_routes(api_client):
    invalid_register = api_client.client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "short", "displayName": ""},
    )
    assert invalid_register.status_code == 400

    user = api_client.register_user("duplicate-auth-flow")
    duplicate = api_client.client.post(
        "/api/v1/auth/register",
        json={
            "email": user.email,
            "password": user.password,
            "displayName": user.display_name,
        },
    )
    assert duplicate.status_code in {400, 409}

    invalid_login = api_client.client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "wrong-password"},
    )
    assert invalid_login.status_code in {400, 401}

    unauthenticated_profile = api_client.client.get("/api/v1/auth/profile")
    assert unauthenticated_profile.status_code in {401, 403}

    non_admin_users = api_client.client.get("/api/v1/auth/users", headers=user.auth_headers)
    assert non_admin_users.status_code in {401, 403}


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unsigned_jwt(header: dict, payload: dict, signature: str) -> str:
    return ".".join(
        (
            _b64url(json.dumps(header).encode()),
            _b64url(json.dumps(payload).encode()),
            _b64url(signature.encode()) if signature else "",
        )
    )


def _refresh(api_client, token: str):
    return api_client.client.post(
        "/api/v1/auth/refresh",
        headers={"Authorization": f"Bearer {token}"},
    )


def test_login_returns_fresh_token_pair_and_profile_matches(api_client):
    user = api_client.register_user("auth-login-pair")
    first = api_client.login_user(user)
    second = api_client.login_user(user)
    assert first["refreshToken"] != second["refreshToken"]
    assert first["expiresIn"] > 0
    assert first["user"]["id"] == user.id

    for tokens in (first, second):
        profile = api_client.client.get(
            "/api/v1/auth/profile",
            headers={"Authorization": f"Bearer {tokens['accessToken']}"},
        )
        assert profile.status_code == 200, profile.text
        assert profile.json()["id"] == user.id


def test_auth_responses_never_leak_password_material(api_client):
    user = api_client.register_user("auth-no-leak")
    login_response = api_client.client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": user.password},
    )
    profile_response = api_client.client.get("/api/v1/auth/profile", headers=user.auth_headers)
    for response in (login_response, profile_response):
        assert response.status_code == 200, response.text
        assert user.password not in response.text
        assert "passwordHash" not in response.text
        assert "$2a$" not in response.text


def test_bad_password_and_unknown_user_get_same_error(api_client):
    user = api_client.register_user("auth-bad-password")
    wrong_password = api_client.client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "WrongPassword123!"},
    )
    unknown_user = api_client.client.post(
        "/api/v1/auth/login",
        json={"email": api_client.unique_email("auth-ghost"), "password": "WrongPassword123!"},
    )
    assert wrong_password.status_code == 400, wrong_password.text
    assert unknown_user.status_code == wrong_password.status_code
    assert wrong_password.json()["message"] == unknown_user.json()["message"]
    assert "accessToken" not in wrong_password.json()


def test_login_validation_rejects_bad_input(api_client):
    for payload in (
        {"email": "not-an-email", "password": "OtterworksTest123!"},
        {"email": api_client.unique_email("auth-empty-pw"), "password": ""},
        {"email": "", "password": "OtterworksTest123!"},
    ):
        response = api_client.client.post("/api/v1/auth/login", json=payload)
        assert response.status_code == 400, f"{payload}: {response.text}"


def test_refresh_rotation_chain_and_replay_rejection(api_client):
    user = api_client.register_user("auth-refresh-chain")
    current = user.refresh_token
    seen = {current}
    for _ in range(3):
        response = _refresh(api_client, current)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["refreshToken"] not in seen
        seen.add(body["refreshToken"])
        profile = api_client.client.get(
            "/api/v1/auth/profile",
            headers={"Authorization": f"Bearer {body['accessToken']}"},
        )
        assert profile.status_code == 200, profile.text
        stale = current
        current = body["refreshToken"]
        assert _refresh(api_client, stale).status_code in {400, 401, 403}


def test_refresh_rejects_access_tokens_and_garbage(api_client):
    user = api_client.register_user("auth-refresh-wrong-type")
    assert _refresh(api_client, user.access_token).status_code in {400, 401, 403}
    assert _refresh(api_client, "not.a.jwt").status_code == 401
    tampered = user.refresh_token[:-4] + ("AAAA" if not user.refresh_token.endswith("AAAA") else "BBBB")
    assert _refresh(api_client, tampered).status_code == 401


def test_logout_revokes_refresh_tokens_from_every_session(api_client):
    user = api_client.register_user("auth-logout-all")
    second_session = api_client.login_user(user)

    logout = api_client.client.post("/api/v1/auth/logout", headers=user.auth_headers)
    assert logout.status_code == 204, logout.text

    assert _refresh(api_client, user.refresh_token).status_code in {400, 401, 403}
    assert _refresh(api_client, second_session["refreshToken"]).status_code in {400, 401, 403}

    relogin = api_client.login_user(user)
    assert _refresh(api_client, relogin["refreshToken"]).status_code == 200


def test_logout_requires_authentication(api_client):
    response = api_client.client.post("/api/v1/auth/logout")
    assert response.status_code == 401
    api_client.assert_json_error(response)


def test_change_password_rotates_credentials_and_revokes_refresh(api_client):
    user = api_client.register_user("auth-change-password")
    new_password = "OtterworksChanged456!"

    wrong_current = api_client.client.post(
        "/api/v1/auth/change-password",
        headers=user.auth_headers,
        json={"currentPassword": "NotMyPassword1!", "newPassword": new_password},
    )
    assert wrong_current.status_code == 400, wrong_current.text

    changed = api_client.client.post(
        "/api/v1/auth/change-password",
        headers=user.auth_headers,
        json={"currentPassword": user.password, "newPassword": new_password},
    )
    assert changed.status_code == 204, changed.text

    assert _refresh(api_client, user.refresh_token).status_code in {400, 401, 403}
    old_login = api_client.client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": user.password}
    )
    assert old_login.status_code == 400
    new_login = api_client.client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": new_password}
    )
    assert new_login.status_code == 200, new_login.text


@pytest.mark.parametrize(
    "authorization",
    [
        None,
        "Bearer",
        "Bearer not-a-jwt",
        "Basic dXNlcjpwYXNz",
        "alg-none",
    ],
)
def test_gateway_rejects_missing_or_invalid_bearer_on_protected_routes(api_client, authorization):
    if authorization == "alg-none":
        authorization = "Bearer " + _unsigned_jwt(
            {"alg": "none", "typ": "JWT"}, {"sub": "admin", "roles": ["ADMIN"]}, ""
        )
    headers = {"Authorization": authorization} if authorization else {}
    for route in ("/api/v1/auth/profile", "/api/v1/auth/users", "/api/v1/auth/change-password"):
        response = api_client.client.get(route, headers=headers)
        assert response.status_code == 401, f"{route}: {response.status_code} {response.text}"
        api_client.assert_json_error(response)


def test_gateway_rejects_expired_token_signed_with_unknown_key(api_client):
    expired = _unsigned_jwt(
        {"alg": "HS256", "typ": "JWT"},
        {"sub": "user-1", "type": "access", "exp": 1},
        "signature-not-valid",
    )
    response = api_client.client.get(
        "/api/v1/auth/profile", headers={"Authorization": f"Bearer {expired}"}
    )
    assert response.status_code == 401


# ---- [REAL] defects found during auth QA; intentionally left failing on main ----


@pytest.mark.gap_revealer
def test_real_refresh_token_must_not_work_as_access_token_on_gateway_routes(api_client):
    """[REAL] Gateway JWT middleware ignores the `type` claim, so a 30-day refresh token is
    accepted as a bearer on proxied (non-auth-service) routes."""
    user = api_client.register_user("auth-refresh-as-bearer")
    response = api_client.client.get(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {user.refresh_token}"},
    )
    assert response.status_code == 401, f"refresh token accepted: {response.status_code}"


@pytest.mark.gap_revealer
def test_real_login_email_is_case_insensitive(api_client):
    """[REAL] Emails are stored/compared case-sensitively: a user registered as Mixed@Case
    cannot sign in as mixed@case."""
    user = api_client.register_user("Auth-Case")
    response = api_client.client.post(
        "/api/v1/auth/login",
        json={"email": user.email.lower(), "password": user.password},
    )
    assert response.status_code == 200, response.text


@pytest.mark.gap_revealer
def test_real_email_uniqueness_is_case_insensitive(api_client):
    """[REAL] The same mailbox can be registered twice by changing letter case."""
    user = api_client.register_user("Auth-Dup-Case")
    response = api_client.client.post(
        "/api/v1/auth/register",
        json={"email": user.email.lower(), "password": user.password, "displayName": "dup"},
    )
    assert response.status_code in {400, 409}, response.text


@pytest.mark.gap_revealer
@pytest.mark.parametrize("body", ["{bad json", ""])
def test_real_malformed_login_body_is_client_error(api_client, body):
    """[REAL] auth-service maps HttpMessageNotReadableException to 500."""
    response = api_client.client.post(
        "/api/v1/auth/login",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    assert 400 <= response.status_code < 500, response.text


@pytest.mark.xfail(
    reason="[PLANTED] security/dast DAST-CREDENTIAL-BRUTE-FORCE (CWE-307): main is the "
    "documented DAST before-state; no lockout/backoff is implemented",
    strict=False,
)
def test_account_lockout_after_repeated_bad_passwords(api_client):
    """No lockout/backoff after repeated failed logins (DAST-CREDENTIAL-BRUTE-FORCE)."""
    user = api_client.register_user("auth-brute-force")
    statuses = []
    for _ in range(12):
        response = api_client.client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "WrongPassword123!"},
        )
        statuses.append(response.status_code)
    locked = api_client.client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": user.password},
    )
    assert 429 in statuses or locked.status_code in {401, 403, 423, 429}, statuses
