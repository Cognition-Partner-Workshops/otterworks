"""Admin-area black-box flows through the gateway (admin dashboard backend).

Bugs found while building this suite are tagged:
  [REAL]    genuine defect on main (not in AGENTS.md / scripts/bug-catalog.yaml)
  [PLANTED] deliberate golden-app bug (AGENTS.md / bug-catalog.yaml / chaos flags)
"""

import re
import uuid
from pathlib import Path

import httpx
import pytest


pytestmark = pytest.mark.api_flow

ADMIN = "/api/v1/admin"
REPO_ROOT = Path(__file__).resolve().parents[2]
AUTH_SERVICE_TS = REPO_ROOT / "frontend/admin-dashboard/src/app/core/services/auth.service.ts"


@pytest.fixture
def admin_user(api_client):
    return api_client.register_user("admin-area")


@pytest.fixture
def temp_flag(api_client, admin_user):
    name = f"qa_admin_{uuid.uuid4().hex[:10]}"
    response = api_client.client.post(
        f"{ADMIN}/features",
        headers=admin_user.auth_headers,
        json={"feature": {"name": name, "description": "admin QA temp flag", "enabled": False}},
    )
    assert response.status_code == 201, response.text
    flag = response.json()
    try:
        yield flag
    finally:
        api_client.client.delete(f"{ADMIN}/features/{flag['id']}", headers=admin_user.auth_headers)


def _toggle(api_client, user, flag_id: str, enabled: bool) -> httpx.Response:
    return api_client.client.put(
        f"{ADMIN}/features/{flag_id}", headers=user.auth_headers, json={"feature": {"enabled": enabled}}
    )


def test_admin_endpoints_reject_missing_and_garbage_tokens(api_client):
    for path in ("/users", "/features", "/audit-logs", "/health/services", "/metrics/summary"):
        assert api_client.client.get(f"{ADMIN}{path}").status_code == 401, path
        bad = api_client.client.get(f"{ADMIN}{path}", headers={"Authorization": "Bearer not-a-jwt"})
        assert bad.status_code == 401, path


@pytest.mark.gap_revealer
@pytest.mark.xfail(strict=True, reason="[REAL] admin-service has no admin role check: any valid JWT (role USER) "
                                       "can read and mutate admin resources")
def test_plain_user_token_is_forbidden_from_admin_api(api_client, admin_user):
    response = api_client.client.get(f"{ADMIN}/users", headers=admin_user.auth_headers)
    assert response.status_code == 403, response.text


@pytest.mark.gap_revealer
@pytest.mark.xfail(strict=True, reason="[REAL] the offline mock token baked into admin-dashboard auth.service.ts "
                                       "(used by login() on ANY error) is accepted by the live admin API")
def test_dashboard_mock_token_is_rejected_by_admin_api(api_client):
    match = re.search(r"token:\s*'([^']+)'", AUTH_SERVICE_TS.read_text())
    assert match, "mock token not found in auth.service.ts"
    response = api_client.client.get(f"{ADMIN}/users", headers={"Authorization": f"Bearer {match.group(1)}"})
    assert response.status_code == 401, response.text


def test_users_list_search_show_and_pagination(api_client, admin_user):
    headers = admin_user.auth_headers
    page = api_client.client.get(f"{ADMIN}/users", headers=headers, params={"per_page": 2})
    assert page.status_code == 200, page.text
    body = page.json()
    assert body["per_page"] == 2 and len(body["users"]) <= 2 and body["total"] >= len(body["users"])

    search = api_client.client.get(f"{ADMIN}/users", headers=headers, params={"q": "james.park"})
    assert search.status_code == 200
    emails = [u["email"] for u in search.json()["users"]]
    assert emails and all("james.park" in e for e in emails)

    user_id = search.json()["users"][0]["id"]
    show = api_client.client.get(f"{ADMIN}/users/{user_id}", headers=headers)
    assert show.status_code == 200
    assert show.json()["email"] == emails[0]

    missing = api_client.client.get(f"{ADMIN}/users/{uuid.uuid4()}", headers=headers)
    assert missing.status_code == 404


def test_feature_flag_lifecycle_and_audit_trail(api_client, admin_user, temp_flag):
    headers = admin_user.auth_headers
    listed = api_client.client.get(f"{ADMIN}/features", headers=headers)
    assert listed.status_code == 200
    assert temp_flag["id"] in {f["id"] for f in listed.json()["features"]}

    on = _toggle(api_client, admin_user, temp_flag["id"], True)
    assert on.status_code == 200 and on.json()["enabled"] is True
    off = _toggle(api_client, admin_user, temp_flag["id"], False)
    assert off.status_code == 200 and off.json()["enabled"] is False

    bad = api_client.client.put(
        f"{ADMIN}/features/{temp_flag['id']}", headers=headers, json={"feature": {"rollout_percentage": 150}}
    )
    assert bad.status_code == 422

    audit = api_client.client.get(
        f"{ADMIN}/audit-logs",
        headers=headers,
        params={"resource_type": "FeatureFlag", "resource_id": temp_flag["id"]},
    )
    assert audit.status_code == 200
    actions = [log["action"] for log in audit.json()["audit_logs"]]
    assert "feature_flag.created" in actions
    assert actions.count("feature_flag.updated") >= 2


def test_feature_flag_rejects_invalid_name(api_client, admin_user):
    response = api_client.client.post(
        f"{ADMIN}/features", headers=admin_user.auth_headers, json={"feature": {"name": "Not Snake Case"}}
    )
    assert response.status_code == 422


def test_audit_log_filters(api_client, admin_user):
    headers = admin_user.auth_headers
    by_type = api_client.client.get(
        f"{ADMIN}/audit-logs", headers=headers, params={"action_type": "user.suspended", "per_page": 50}
    )
    assert by_type.status_code == 200
    logs = by_type.json()["audit_logs"]
    assert logs and all(log["action"] == "user.suspended" for log in logs)

    all_logs = api_client.client.get(f"{ADMIN}/audit-logs", headers=headers, params={"per_page": 1}).json()
    ignored = api_client.client.get(
        f"{ADMIN}/audit-logs", headers=headers, params={"action": "user.suspended", "per_page": 1}
    ).json()
    assert ignored["total"] == all_logs["total"], "param is action_type; 'action' is ignored"

    since = api_client.client.get(
        f"{ADMIN}/audit-logs", headers=headers, params={"since": api_client.iso_time(-1), "per_page": 1}
    )
    assert since.status_code == 200 and since.json()["total"] <= all_logs["total"]


def test_health_and_metrics_summary(api_client, admin_user):
    headers = admin_user.auth_headers
    health = api_client.client.get(f"{ADMIN}/health/services", headers=headers)
    assert health.status_code == 200
    body = health.json()
    assert body["status"] in {"healthy", "degraded", "unhealthy"}
    names = {s["name"] for s in body["services"]}
    assert {"auth-service", "document-service", "file-service"} <= names

    summary = api_client.client.get(f"{ADMIN}/metrics/summary", headers=headers)
    assert summary.status_code == 200
    metrics = summary.json()
    for key in ("users", "storage", "features", "audit"):
        assert key in metrics, key
    assert metrics["users"]["total"] >= metrics["users"]["active"]
