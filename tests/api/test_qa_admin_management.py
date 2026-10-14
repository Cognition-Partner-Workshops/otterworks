"""QA: admin-service user management, metrics, audit logs, settings via the gateway."""

import uuid

import pytest

pytestmark = pytest.mark.api_flow

ADMIN = "/api/v1/admin"


@pytest.fixture
def operator(api_client):
    return api_client.register_user("qa-admin-operator")


def _users(api_client, operator, **params):
    response = api_client.client.get(f"{ADMIN}/users", headers=operator.auth_headers, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def _pick_active_user(api_client, operator):
    users = _users(api_client, operator, status="active", role="viewer", per_page=100)["users"]
    assert users, "seed data missing: no active viewer in admin_users (run `make seed`)"
    return users[0]


def test_users_list_is_paginated_and_shaped(api_client, operator):
    body = _users(api_client, operator, per_page=2)
    assert body["per_page"] == 2 and body["page"] == 1
    assert body["total"] >= len(body["users"])
    assert len(body["users"]) <= 2
    user = body["users"][0]
    for key in ("id", "email", "display_name", "role", "status", "created_at"):
        assert key in user


def test_users_per_page_is_clamped_to_100(api_client, operator):
    assert _users(api_client, operator, per_page=5000)["per_page"] == 100


def test_users_filter_by_role_and_status(api_client, operator):
    for role in ("viewer", "editor"):
        assert all(u["role"] == role for u in _users(api_client, operator, role=role)["users"])
    suspended = _users(api_client, operator, status="suspended")["users"]
    assert all(u["status"] == "suspended" for u in suspended)


def test_users_search_matches_email_case_insensitively(api_client, operator):
    target = _pick_active_user(api_client, operator)
    fragment = target["email"].split("@")[0].upper()
    found = _users(api_client, operator, q=fragment)["users"]
    assert target["id"] in [u["id"] for u in found]


def test_user_show_and_404(api_client, operator):
    target = _pick_active_user(api_client, operator)
    response = api_client.client.get(f"{ADMIN}/users/{target['id']}", headers=operator.auth_headers)
    assert response.status_code == 200
    assert response.json()["email"] == target["email"]
    missing = api_client.client.get(f"{ADMIN}/users/{uuid.uuid4()}", headers=operator.auth_headers)
    assert missing.status_code == 404
    api_client.assert_json_error(missing)


def test_suspend_then_activate_round_trip_is_audited(api_client, operator):
    target = _pick_active_user(api_client, operator)
    headers = operator.auth_headers
    try:
        suspended = api_client.client.put(
            f"{ADMIN}/users/{target['id']}/suspend", headers=headers, json={"reason": "qa round trip"}
        )
        assert suspended.status_code == 200, suspended.text
        assert suspended.json()["status"] == "suspended"
        assert suspended.json()["suspended_reason"] == "qa round trip"
    finally:
        activated = api_client.client.put(f"{ADMIN}/users/{target['id']}/activate", headers=headers)
    assert activated.status_code == 200, activated.text
    assert activated.json()["status"] == "active"
    assert activated.json()["suspended_reason"] is None

    logs = api_client.client.get(
        f"{ADMIN}/audit-logs",
        headers=headers,
        params={"resource_type": "AdminUser", "resource_id": target["id"], "per_page": 10},
    ).json()["audit_logs"]
    actions = [log["action"] for log in logs]
    assert "user.suspended" in actions and "user.activated" in actions
    mine = [log for log in logs if log["actor_id"] == operator.id]
    assert mine, "audit entries should record the acting user's id"


def test_update_rejects_invalid_role(api_client, operator):
    target = _pick_active_user(api_client, operator)
    response = api_client.client.put(
        f"{ADMIN}/users/{target['id']}", headers=operator.auth_headers, json={"user": {"role": "god_mode"}}
    )
    assert response.status_code == 422
    api_client.assert_json_error(response)


def test_metrics_summary_shape_and_consistency(api_client, operator):
    response = api_client.client.get(f"{ADMIN}/metrics/summary", headers=operator.auth_headers)
    assert response.status_code == 200, response.text
    metrics = response.json()
    for key in ("timestamp", "users", "storage", "features", "announcements", "audit"):
        assert key in metrics
    users = metrics["users"]
    assert users["total"] == _users(api_client, operator)["total"]
    assert users["active"] + users["suspended"] <= users["total"]
    assert sum(users["by_role"].values()) == users["total"]
    features = metrics["features"]
    assert features["enabled"] + features["disabled"] == features["total"]
    assert 0 <= metrics["storage"]["average_usage_percent"] <= 100
    assert metrics["audit"]["events_today"] <= metrics["audit"]["events_this_week"] <= metrics["audit"]["total_events"]
    assert len(metrics["audit"]["top_actions"]) <= 5


def test_audit_logs_newest_first_and_filterable(api_client, operator):
    headers = operator.auth_headers
    body = api_client.client.get(f"{ADMIN}/audit-logs", headers=headers, params={"per_page": 50}).json()
    stamps = [log["created_at"] for log in body["audit_logs"]]
    assert stamps == sorted(stamps, reverse=True)
    filtered = api_client.client.get(
        f"{ADMIN}/audit-logs", headers=headers, params={"action_type": "user.suspended"}
    ).json()["audit_logs"]
    assert all(log["action"] == "user.suspended" for log in filtered)


def test_audit_logs_since_window(api_client, operator):
    since = api_client.iso_time(days_offset=-1)
    logs = api_client.client.get(
        f"{ADMIN}/audit-logs", headers=operator.auth_headers, params={"since": since, "per_page": 100}
    ).json()["audit_logs"]
    assert all(log["created_at"] >= since[:19] for log in logs)


def test_audit_logs_invalid_date_is_400(api_client, operator):
    response = api_client.client.get(f"{ADMIN}/audit-logs", headers=operator.auth_headers, params={"since": "garbage"})
    assert response.status_code == 400
    assert "Invalid date format" in api_client.assert_json_error(response)["error"]


def test_auto_investigate_setting_round_trip(api_client, operator):
    headers = operator.auth_headers
    url = f"{ADMIN}/settings/auto_investigate"
    original = api_client.client.get(url, headers=headers)
    assert original.status_code == 200
    original_value = original.json()["enabled"]
    try:
        flipped = api_client.client.put(url, headers=headers, json={"enabled": not original_value})
        assert flipped.status_code == 200, flipped.text
        assert flipped.json() == {"enabled": not original_value}
        assert api_client.client.get(url, headers=headers).json() == {"enabled": not original_value}
    finally:
        api_client.client.put(url, headers=headers, json={"enabled": original_value})
    assert api_client.client.get(url, headers=headers).json() == {"enabled": original_value}


def test_auto_investigate_requires_enabled(api_client, operator):
    response = api_client.client.put(f"{ADMIN}/settings/auto_investigate", headers=operator.auth_headers, json={})
    assert response.status_code == 400
    api_client.assert_json_error(response)


def test_feature_flag_crud_is_audited(api_client, operator):
    headers = operator.auth_headers
    name = f"qa_admin_flag_{uuid.uuid4().hex[:8]}"
    created = api_client.client.post(
        f"{ADMIN}/features", headers=headers,
        json={"feature": {"name": name, "description": "QA", "enabled": False, "rollout_percentage": 10}},
    )
    assert created.status_code == 201, created.text
    flag_id = created.json()["id"]
    try:
        toggled = api_client.client.put(f"{ADMIN}/features/{flag_id}", headers=headers, json={"feature": {"enabled": True}})
        assert toggled.status_code == 200 and toggled.json()["enabled"] is True
        bad = api_client.client.put(f"{ADMIN}/features/{flag_id}", headers=headers, json={"feature": {"rollout_percentage": 101}})
        assert bad.status_code == 422
    finally:
        assert api_client.client.delete(f"{ADMIN}/features/{flag_id}", headers=headers).status_code == 204
    actions = [
        log["action"] for log in api_client.client.get(
            f"{ADMIN}/audit-logs", headers=headers, params={"resource_type": "FeatureFlag", "resource_id": flag_id}
        ).json()["audit_logs"]
    ]
    assert {"feature_flag.created", "feature_flag.updated", "feature_flag.deleted"} <= set(actions)


def test_feature_flag_name_must_be_snake_case(api_client, operator):
    response = api_client.client.post(
        f"{ADMIN}/features", headers=operator.auth_headers, json={"feature": {"name": "Not Snake", "rollout_percentage": 0}}
    )
    assert response.status_code == 422


def test_announcement_create_publish_delete(api_client, operator):
    headers = operator.auth_headers
    created = api_client.client.post(
        f"{ADMIN}/announcements", headers=headers,
        json={"announcement": {"title": f"QA {api_client.run_id}", "body": "qa", "severity": "info", "status": "draft"}},
    )
    assert created.status_code == 201, created.text
    ann_id = created.json()["id"]
    try:
        assert created.json()["created_by"] == operator.id
        published = api_client.client.put(
            f"{ADMIN}/announcements/{ann_id}", headers=headers, json={"announcement": {"status": "published"}}
        )
        assert published.status_code == 200 and published.json()["status"] == "published"
        active_ids = [
            a["id"] for a in api_client.client.get(
                f"{ADMIN}/announcements", headers=headers, params={"active": "true"}
            ).json()["announcements"]
        ]
        assert ann_id in active_ids
    finally:
        assert api_client.client.delete(f"{ADMIN}/announcements/{ann_id}", headers=headers).status_code == 204


def test_health_services_reports_backends(api_client, operator):
    response = api_client.client.get(f"{ADMIN}/health/services", headers=operator.auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    names = {s["name"] for s in body["services"]}
    assert {"auth-service", "document-service"} <= names
    assert all(s["status"] in {"healthy", "unhealthy", "degraded", "timeout"} for s in body["services"])
