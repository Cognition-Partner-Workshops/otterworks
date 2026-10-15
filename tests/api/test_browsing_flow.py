"""Browsing/navigation API flows: dashboard, recent, folder drill-down, settings, notifications bell, deep links.

These exercise the exact gateway routes and payload shapes the client-app browsing pages consume
(frontend/client-app/src/lib/api.ts).
"""
import os
import uuid
from datetime import UTC, datetime

import httpx
import pytest


pytestmark = pytest.mark.api_flow

WEB_URL = os.getenv("OTTERWORKS_WEB_BASE_URL", "http://localhost:3000").rstrip("/")
LOCALSTACK_URL = os.getenv("OTTERWORKS_LOCALSTACK_URL", "http://localhost:4566").rstrip("/")
NOTIFICATIONS_TABLE = os.getenv("OTTERWORKS_NOTIFICATIONS_TABLE", "otterworks-notifications")


def create_folder(api_client, user, name, parent_id=None):
    response = api_client.client.post(
        "/api/v1/folders",
        headers=user.auth_headers,
        json={"name": name, "parent_id": parent_id, "owner_id": user.id},
    )
    assert response.status_code == 201, response.text
    folder = response.json()
    api_client.created_folders.append(folder["id"])
    return folder


def seed_unread_notifications(user_id: str, count: int) -> list[str]:
    """Insert unread in-app notifications straight into the local DynamoDB table (LocalStack)."""
    ids = []
    headers = {
        "X-Amz-Target": "DynamoDB_20120810.PutItem",
        "Content-Type": "application/x-amz-json-1.0",
        "Authorization": (
            "AWS4-HMAC-SHA256 Credential=test/20260101/us-east-1/dynamodb/aws4_request, "
            "SignedHeaders=host, Signature=0"
        ),
    }
    try:
        with httpx.Client(timeout=5.0) as client:
            for index in range(count):
                notification_id = str(uuid.uuid4())
                item = {
                    "id": {"S": notification_id},
                    "userId": {"S": user_id},
                    "type": {"S": "file_shared"},
                    "title": {"S": f"Browsing QA notification {index}"},
                    "message": {"S": "A teammate shared a file with you"},
                    "resourceId": {"S": str(uuid.uuid4())},
                    "resourceType": {"S": "file"},
                    "actorId": {"S": "browsing-qa"},
                    "read": {"BOOL": False},
                    "deliveredVia": {"L": [{"S": "IN_APP"}]},
                    "createdAt": {"S": datetime.now(UTC).isoformat()},
                }
                response = client.post(
                    LOCALSTACK_URL, headers=headers, json={"TableName": NOTIFICATIONS_TABLE, "Item": item}
                )
                if response.status_code != 200:
                    pytest.skip(f"cannot seed notifications in LocalStack: {response.text}")
                ids.append(notification_id)
    except httpx.HTTPError as exc:
        pytest.skip(f"LocalStack not reachable for notification fixture: {exc}")
    return ids


# ── Dashboard ──────────────────────────────────────────────────


def test_dashboard_data_sources_for_new_user(api_client):
    user = api_client.register_user("browse-dashboard")

    files = api_client.client.get(
        "/api/v1/files", headers=user.auth_headers, params={"page": 1, "page_size": 100}
    )
    assert files.status_code == 200, files.text
    assert files.json()["files"] == []
    assert files.json()["total"] == 0

    documents = api_client.client.get(
        "/api/v1/documents", headers=user.auth_headers, params={"page": 1, "size": 100}
    )
    assert documents.status_code == 200, documents.text
    assert documents.json()["items"] == []
    assert documents.json()["total"] == 0

    activity = api_client.client.get(
        "/api/v1/files/activity", headers=user.auth_headers, params={"limit": 20}
    )
    assert activity.status_code == 200, activity.text
    assert activity.json()["items"] == []


def test_sidebar_profile_returns_display_name_and_email(api_client):
    user = api_client.register_user("browse-profile")
    response = api_client.client.get("/api/v1/auth/profile", headers=user.auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == user.id
    assert body["email"] == user.email
    assert body["displayName"] == user.display_name


@pytest.mark.parametrize(
    "route",
    [
        "/api/v1/files",
        "/api/v1/folders",
        "/api/v1/documents",
        "/api/v1/files/activity",
        "/api/v1/notifications/unread-count",
        "/api/v1/settings",
    ],
)
def test_browsing_routes_require_authentication(api_client, route):
    response = api_client.client.get(route)
    assert response.status_code == 401, f"{route}: {response.status_code} {response.text}"


# ── Recent items ───────────────────────────────────────────────


def test_recent_documents_include_new_documents(api_client):
    user = api_client.register_user("browse-recent")
    first = api_client.create_document(user, f"Recent A {api_client.run_id}", "a")
    second = api_client.create_document(user, f"Recent B {api_client.run_id}", "b")

    response = api_client.client.get(
        "/api/v1/documents", headers=user.auth_headers, params={"page": 1, "size": 10}
    )
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    ids = [item["id"] for item in items]
    assert {first["id"], second["id"]} <= set(ids)
    for item in items:
        assert item.get("updated_at") or item.get("updatedAt"), item


def test_recent_documents_are_scoped_to_the_caller(api_client):
    owner = api_client.register_user("browse-recent-owner")
    other = api_client.register_user("browse-recent-other")
    document = api_client.create_document(owner, f"Private recent {api_client.run_id}", "x")

    response = api_client.client.get(
        "/api/v1/documents", headers=other.auth_headers, params={"page": 1, "size": 50}
    )
    assert response.status_code == 200, response.text
    assert document["id"] not in [item["id"] for item in response.json()["items"]]


# ── Folder drill-down / breadcrumbs ────────────────────────────


def test_folder_drill_down_root_and_children(api_client):
    user = api_client.register_user("browse-folders")
    parent = create_folder(api_client, user, "Projects")
    child = create_folder(api_client, user, "Q3 Launch", parent_id=parent["id"])

    root = api_client.client.get("/api/v1/folders", headers=user.auth_headers)
    assert root.status_code == 200, root.text
    root_ids = [f["id"] for f in root.json()["folders"]]
    assert parent["id"] in root_ids
    assert child["id"] not in root_ids

    children = api_client.client.get(
        "/api/v1/folders", headers=user.auth_headers, params={"parent_id": parent["id"]}
    )
    assert children.status_code == 200, children.text
    assert [f["id"] for f in children.json()["folders"]] == [child["id"]]

    files_in_child = api_client.client.get(
        "/api/v1/files",
        headers=user.auth_headers,
        params={"folder_id": child["id"], "page": 1, "page_size": 50},
    )
    assert files_in_child.status_code == 200, files_in_child.text
    assert files_in_child.json()["files"] == []


def test_folder_detail_supplies_breadcrumb_name_and_parent(api_client):
    user = api_client.register_user("browse-breadcrumb")
    parent = create_folder(api_client, user, "Projects")
    child = create_folder(api_client, user, "Q3 Launch", parent_id=parent["id"])

    response = api_client.client.get(f"/api/v1/folders/{child['id']}", headers=user.auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == "Q3 Launch"
    assert body["parent_id"] == parent["id"]

    parent_detail = api_client.client.get(f"/api/v1/folders/{parent['id']}", headers=user.auth_headers)
    assert parent_detail.status_code == 200, parent_detail.text
    assert parent_detail.json()["parent_id"] is None


def test_folder_deep_link_to_unknown_folder_is_json_404(api_client):
    user = api_client.register_user("browse-folder-404")
    response = api_client.client.get(
        f"/api/v1/folders/{uuid.uuid4()}", headers=user.auth_headers
    )
    assert response.status_code == 404, response.text
    api_client.assert_json_error(response)


def test_folder_deep_link_with_malformed_id_is_json_400(api_client):
    user = api_client.register_user("browse-folder-400")
    response = api_client.client.get("/api/v1/folders/not-a-uuid", headers=user.auth_headers)
    assert response.status_code == 400, response.text
    api_client.assert_json_error(response)


# ── Settings ───────────────────────────────────────────────────


def test_settings_defaults_and_patch_persists(api_client):
    user = api_client.register_user("browse-settings")

    initial = api_client.client.get("/api/v1/settings", headers=user.auth_headers)
    api_client.assert_gateway_route_available(initial, "/api/v1/settings")
    assert initial.status_code == 200, initial.text
    defaults = initial.json()
    for key in ("notificationEmail", "notificationInApp", "notificationDesktop", "theme", "language"):
        assert key in defaults, defaults

    flipped = not defaults["notificationDesktop"]
    update = api_client.client.patch(
        "/api/v1/settings", headers=user.auth_headers, json={"notificationDesktop": flipped}
    )
    assert update.status_code == 200, update.text
    assert update.json()["notificationDesktop"] is flipped

    reread = api_client.client.get("/api/v1/settings", headers=user.auth_headers)
    assert reread.status_code == 200, reread.text
    assert reread.json()["notificationDesktop"] is flipped
    assert reread.json()["notificationEmail"] == defaults["notificationEmail"]


def test_settings_are_isolated_per_user(api_client):
    first = api_client.register_user("browse-settings-a")
    second = api_client.register_user("browse-settings-b")
    api_client.client.patch("/api/v1/settings", headers=first.auth_headers, json={"theme": "dark"})

    other = api_client.client.get("/api/v1/settings", headers=second.auth_headers)
    assert other.status_code == 200, other.text
    assert other.json()["theme"] != "dark"


# ── Notifications bell ─────────────────────────────────────────


def test_notification_unread_count_reflects_seeded_notifications(api_client):
    user = api_client.register_user("browse-bell-count")
    seed_unread_notifications(user.id, 3)

    response = api_client.client.get("/api/v1/notifications/unread-count", headers=user.auth_headers)
    assert response.status_code == 200, response.text
    assert response.json()["unreadCount"] == 3

    listing = api_client.client.get(
        "/api/v1/notifications", headers=user.auth_headers, params={"page": 1, "pageSize": 20}
    )
    assert listing.status_code == 200, listing.text
    assert len(listing.json()["data"]) == 3


def test_notification_unread_count_matches_client_contract(api_client):
    """NotificationBell renders `data.count` from this endpoint (notificationsApi.getUnreadCount)."""
    user = api_client.register_user("browse-bell-contract")
    seed_unread_notifications(user.id, 2)

    response = api_client.client.get("/api/v1/notifications/unread-count", headers=user.auth_headers)
    assert response.status_code == 200, response.text
    assert response.json().get("count") == 2, (
        f"client reads `count` but gateway returned {response.json()}; bell badge never renders"
    )


def test_notification_mark_read_methods_match_client_contract(api_client):
    """notificationsApi.markRead uses PATCH /{id}/read and markAllRead uses POST /read-all."""
    user = api_client.register_user("browse-bell-markread")
    [notification_id] = seed_unread_notifications(user.id, 1)

    mark_one = api_client.client.patch(
        f"/api/v1/notifications/{notification_id}/read", headers=user.auth_headers
    )
    mark_all = api_client.client.post("/api/v1/notifications/read-all", headers=user.auth_headers)
    assert (mark_one.status_code, mark_all.status_code) == (200, 200), (
        f"PATCH /{{id}}/read -> {mark_one.status_code}, POST /read-all -> {mark_all.status_code}"
    )


# ── SPA deep links ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "path",
    ["/", "/dashboard", "/recent", "/files", "/files?folder=" + str(uuid.uuid4()), "/settings",
     "/notifications", "/does-not-exist/at/all"],
)
def test_web_app_serves_spa_shell_for_deep_links(path):
    try:
        response = httpx.get(f"{WEB_URL}{path}", timeout=5.0)
    except httpx.HTTPError as exc:
        pytest.skip(f"web app not reachable at {WEB_URL}: {exc}")
    assert response.status_code == 200, response.text
    assert "text/html" in response.headers.get("content-type", "")
    assert '<div id="root">' in response.text
