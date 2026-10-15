"""Admin console API flows (admin-service via the gateway).

Admin endpoints only validate the JWT (see test_regular_user_cannot_escalate_role), so a
registered user's token is used unless OTTERWORKS_ADMIN_LOGIN_EMAIL/PASSWORD are set.
"""

import os
import uuid

import pytest

pytestmark = pytest.mark.api_flow

ADMIN = "/api/v1/admin"


@pytest.fixture
def admin_headers(api_client):
    email = os.getenv("OTTERWORKS_ADMIN_LOGIN_EMAIL")
    password = os.getenv("OTTERWORKS_ADMIN_LOGIN_PASSWORD")
    if email and password:
        response = api_client.client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['accessToken']}"}
    return api_client.register_user("admin-console").auth_headers


@pytest.fixture
def seeded_user(api_client, admin_headers):
    response = api_client.client.get(
        f"{ADMIN}/users",
        headers=admin_headers,
        params={"status": "active", "role": "viewer", "per_page": 1},
    )
    assert response.status_code == 200, response.text
    users = response.json()["users"]
    if not users:
        pytest.skip("no active viewer in admin_users; run `make seed`")
    user = users[0]
    yield user
    api_client.client.put(f"{ADMIN}/users/{user['id']}/activate", headers=admin_headers)
    api_client.client.put(
        f"{ADMIN}/users/{user['id']}",
        headers=admin_headers,
        json={"user": {"role": user["role"]}},
    )


def test_admin_endpoints_require_a_valid_token(api_client):
    no_token = api_client.client.get(f"{ADMIN}/users")
    assert no_token.status_code == 401
    bad_token = api_client.client.get(
        f"{ADMIN}/users", headers={"Authorization": "Bearer not-a-jwt"}
    )
    assert bad_token.status_code == 401
    api_client.assert_json_error(bad_token)


def test_users_list_pagination_search_and_filters(api_client, admin_headers):
    page = api_client.client.get(
        f"{ADMIN}/users", headers=admin_headers, params={"page": 1, "per_page": 2}
    )
    assert page.status_code == 200, page.text
    body = page.json()
    assert body["page"] == 1 and body["per_page"] == 2
    assert len(body["users"]) <= 2
    assert int(page.headers["x-total-count"]) == body["total"] >= len(body["users"])
    first = body["users"][0]
    assert {
        "id",
        "email",
        "display_name",
        "role",
        "status",
        "storage_quota",
    } <= first.keys()

    search = api_client.client.get(
        f"{ADMIN}/users", headers=admin_headers, params={"q": first["email"].upper()}
    )
    assert search.status_code == 200
    assert first["id"] in [u["id"] for u in search.json()["users"]]

    no_match = api_client.client.get(
        f"{ADMIN}/users", headers=admin_headers, params={"q": f"zz-{uuid.uuid4().hex}"}
    )
    assert no_match.json()["users"] == []

    editors = api_client.client.get(
        f"{ADMIN}/users", headers=admin_headers, params={"role": "editor"}
    )
    assert all(u["role"] == "editor" for u in editors.json()["users"])

    detail = api_client.client.get(
        f"{ADMIN}/users/{first['id']}", headers=admin_headers
    )
    assert detail.status_code == 200
    assert detail.json()["email"] == first["email"]

    missing = api_client.client.get(
        f"{ADMIN}/users/{uuid.uuid4()}", headers=admin_headers
    )
    assert missing.status_code == 404
    api_client.assert_json_error(missing)


def test_suspend_and_activate_user_is_audited(api_client, admin_headers, seeded_user):
    user_id = seeded_user["id"]
    reason = f"qa-{api_client.run_id}"

    suspended = api_client.client.put(
        f"{ADMIN}/users/{user_id}/suspend",
        headers=admin_headers,
        json={"reason": reason},
    )
    assert suspended.status_code == 200, suspended.text
    assert suspended.json()["status"] == "suspended"
    assert suspended.json()["suspended_reason"] == reason

    listed = api_client.client.get(
        f"{ADMIN}/users",
        headers=admin_headers,
        params={"status": "suspended", "per_page": 100},
    )
    assert user_id in [u["id"] for u in listed.json()["users"]]

    logs = api_client.client.get(
        f"{ADMIN}/audit-logs",
        headers=admin_headers,
        params={
            "action_type": "user.suspended",
            "resource_type": "AdminUser",
            "resource_id": user_id,
        },
    )
    assert logs.status_code == 200
    suspended_logs = logs.json()["audit_logs"]
    assert suspended_logs and all(
        log["action"] == "user.suspended" and log["resource_id"] == user_id
        for log in suspended_logs
    )
    assert any(log["changes_made"] == {"reason": reason} for log in suspended_logs)

    activated = api_client.client.put(
        f"{ADMIN}/users/{user_id}/activate", headers=admin_headers
    )
    assert activated.status_code == 200
    assert activated.json()["status"] == "active"
    assert activated.json()["suspended_reason"] is None


def test_role_edit_validates_and_audits(api_client, admin_headers, seeded_user):
    user_id = seeded_user["id"]

    updated = api_client.client.put(
        f"{ADMIN}/users/{user_id}",
        headers=admin_headers,
        json={"user": {"role": "editor"}},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["role"] == "editor"

    invalid = api_client.client.put(
        f"{ADMIN}/users/{user_id}",
        headers=admin_headers,
        json={"user": {"role": "root"}},
    )
    assert invalid.status_code == 422
    assert (
        api_client.client.get(f"{ADMIN}/users/{user_id}", headers=admin_headers).json()[
            "role"
        ]
        == "editor"
    )

    logs = api_client.client.get(
        f"{ADMIN}/audit-logs",
        headers=admin_headers,
        params={
            "action_type": "user.updated",
            "resource_type": "AdminUser",
            "resource_id": user_id,
        },
    ).json()["audit_logs"]
    assert any(log["changes_made"]["after"].get("role") == "editor" for log in logs)


def test_storage_quota_view_update_and_validation(
    api_client, admin_headers, seeded_user
):
    user_id = seeded_user["id"]
    quota = api_client.client.get(f"{ADMIN}/quotas/{user_id}", headers=admin_headers)
    assert quota.status_code == 200, quota.text
    original = quota.json()
    assert {
        "quota_bytes",
        "used_bytes",
        "tier",
        "usage_percentage",
        "over_quota",
        "remaining_bytes",
    } <= original.keys()

    try:
        new_bytes = original["quota_bytes"] * 2
        updated = api_client.client.put(
            f"{ADMIN}/quotas/{user_id}",
            headers=admin_headers,
            json={"quota": {"quota_bytes": new_bytes}},
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["quota_bytes"] == new_bytes
        assert updated.json()["remaining_bytes"] == new_bytes - original["used_bytes"]

        zero = api_client.client.put(
            f"{ADMIN}/quotas/{user_id}",
            headers=admin_headers,
            json={"quota": {"quota_bytes": 0}},
        )
        assert zero.status_code == 422

        logs = api_client.client.get(
            f"{ADMIN}/audit-logs",
            headers=admin_headers,
            params={
                "action_type": "quota.updated",
                "resource_type": "StorageQuota",
                "resource_id": original["id"],
            },
        ).json()["audit_logs"]
        assert any(
            log["changes_made"]["after"]["quota_bytes"] == new_bytes for log in logs
        )
    finally:
        api_client.client.put(
            f"{ADMIN}/quotas/{user_id}",
            headers=admin_headers,
            json={"quota": {"quota_bytes": original["quota_bytes"]}},
        )

    missing = api_client.client.get(
        f"{ADMIN}/quotas/{uuid.uuid4()}", headers=admin_headers
    )
    assert missing.status_code == 404


def test_feature_flag_lifecycle(api_client, admin_headers):
    name = f"qa_admin_flag_{api_client.run_id}_{uuid.uuid4().hex[:6]}"
    created = api_client.client.post(
        f"{ADMIN}/features",
        headers=admin_headers,
        json={
            "feature": {
                "name": name,
                "description": "admin QA",
                "enabled": False,
                "rollout_percentage": 10,
            }
        },
    )
    assert created.status_code == 201, created.text
    flag_id = created.json()["id"]
    try:
        duplicate = api_client.client.post(
            f"{ADMIN}/features", headers=admin_headers, json={"feature": {"name": name}}
        )
        assert duplicate.status_code == 422

        toggled = api_client.client.put(
            f"{ADMIN}/features/{flag_id}",
            headers=admin_headers,
            json={"feature": {"enabled": True}},
        )
        assert toggled.status_code == 200
        assert toggled.json()["enabled"] is True

        enabled = api_client.client.get(
            f"{ADMIN}/features", headers=admin_headers, params={"enabled": "true"}
        )
        assert flag_id in [f["id"] for f in enabled.json()["features"]]

        bad_rollout = api_client.client.put(
            f"{ADMIN}/features/{flag_id}",
            headers=admin_headers,
            json={"feature": {"rollout_percentage": 101}},
        )
        assert bad_rollout.status_code == 422

        logs = api_client.client.get(
            f"{ADMIN}/audit-logs",
            headers=admin_headers,
            params={"resource_type": "FeatureFlag", "resource_id": flag_id},
        ).json()["audit_logs"]
        assert {"feature_flag.created", "feature_flag.updated"} <= {
            log["action"] for log in logs
        }
        assert all(log["resource_id"] == flag_id for log in logs)
    finally:
        deleted = api_client.client.delete(
            f"{ADMIN}/features/{flag_id}", headers=admin_headers
        )
    assert deleted.status_code in {200, 204}
    assert (
        api_client.client.get(
            f"{ADMIN}/features/{flag_id}", headers=admin_headers
        ).status_code
        == 404
    )


def test_audit_log_listing_filters_and_errors(api_client, admin_headers):
    page = api_client.client.get(
        f"{ADMIN}/audit-logs", headers=admin_headers, params={"per_page": 5}
    )
    assert page.status_code == 200
    logs = page.json()["audit_logs"]
    assert len(logs) <= 5
    timestamps = [log["created_at"] for log in logs]
    assert timestamps == sorted(timestamps, reverse=True)

    if logs:
        one = api_client.client.get(
            f"{ADMIN}/audit-logs/{logs[0]['id']}", headers=admin_headers
        )
        assert one.status_code == 200
        assert one.json()["id"] == logs[0]["id"]

    future = api_client.client.get(
        f"{ADMIN}/audit-logs",
        headers=admin_headers,
        params={"since": api_client.iso_time(1)},
    )
    assert future.json()["audit_logs"] == []

    invalid = api_client.client.get(
        f"{ADMIN}/audit-logs", headers=admin_headers, params={"since": "not-a-date"}
    )
    assert invalid.status_code == 400
    api_client.assert_json_error(invalid)

    missing = api_client.client.get(
        f"{ADMIN}/audit-logs/{uuid.uuid4()}", headers=admin_headers
    )
    assert missing.status_code == 404


def test_system_health_and_metrics_summary(api_client, admin_headers):
    health = api_client.client.get(f"{ADMIN}/health/services", headers=admin_headers)
    assert health.status_code == 200, health.text
    body = health.json()
    assert body["status"] in {"healthy", "degraded"}
    names = {s["name"] for s in body["services"]}
    assert {
        "auth-service",
        "file-service",
        "document-service",
        "audit-service",
    } <= names
    assert all(s["status"] in {"healthy", "unhealthy"} for s in body["services"])

    metrics = api_client.client.get(f"{ADMIN}/metrics/summary", headers=admin_headers)
    assert metrics.status_code == 200
    summary = metrics.json()
    assert summary["users"]["total"] >= summary["users"]["active"]
    assert summary["features"]["total"] >= summary["features"]["enabled"]
    assert "users_over_quota" in summary["storage"]


@pytest.mark.gap_revealer
def test_regular_user_cannot_escalate_role(api_client, seeded_user):
    """[REAL] admin-service never checks the JWT role, so any end user can grant super_admin."""
    attacker = api_client.register_user("admin-escalation")
    response = api_client.client.put(
        f"{ADMIN}/users/{seeded_user['id']}",
        headers=attacker.auth_headers,
        json={"user": {"role": "super_admin"}},
    )
    assert response.status_code in {401, 403}, (
        f"non-admin token changed a role: {response.status_code}"
    )
