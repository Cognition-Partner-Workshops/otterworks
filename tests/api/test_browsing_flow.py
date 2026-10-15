"""Browsing-area API flows: dashboard data sources, folder browsing, recent,
pagination, settings and the notifications panel, exactly as the client-app
calls them (see frontend/client-app/src/lib/api.ts)."""

import json
import subprocess
import uuid

import pytest


pytestmark = pytest.mark.api_flow

NOTIFICATIONS_TABLE = "otterworks-notifications"
LOCALSTACK_CONTAINER = "otterworks-localstack"


def _create_folder(api_client, user, name, parent_id=None):
    response = api_client.client.post(
        "/api/v1/folders",
        headers=user.auth_headers,
        json={"name": name, "parent_id": parent_id, "owner_id": user.id},
    )
    assert response.status_code == 201, response.text
    folder = response.json()
    api_client.created_folders.append(folder["id"])
    return folder


def _upload_file(api_client, user, name, folder_id=None):
    data = {"owner_id": user.id}
    if folder_id:
        data["folder_id"] = folder_id
    response = api_client.client.post(
        "/api/v1/files/upload",
        headers=user.auth_headers,
        data=data,
        files={"file": (name, f"browsing qa {name}".encode(), "text/plain")},
    )
    assert response.status_code in {200, 201}, response.text
    body = response.json()
    file_item = body.get("file", body)
    api_client.created_files.append(file_item["id"])
    return file_item


def _insert_notification(user_id, title, read=False):
    """Seed a notification row directly into LocalStack DynamoDB."""
    notification_id = f"qa-browsing-{uuid.uuid4().hex}"
    item = {
        "id": {"S": notification_id},
        "userId": {"S": user_id},
        "type": {"S": "share"},
        "title": {"S": title},
        "message": {"S": f"{title} message"},
        "resourceId": {"S": ""},
        "resourceType": {"S": ""},
        "actorId": {"S": ""},
        "read": {"BOOL": read},
        "deliveredVia": {"L": [{"S": "IN_APP"}]},
        "createdAt": {"S": "2026-01-01T00:00:00Z"},
    }
    try:
        subprocess.run(
            [
                "docker", "exec", LOCALSTACK_CONTAINER, "awslocal", "dynamodb", "put-item",
                "--table-name", NOTIFICATIONS_TABLE, "--item", json.dumps(item),
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        pytest.skip(f"cannot seed notifications into LocalStack DynamoDB: {exc}")
    return notification_id


@pytest.fixture
def seeded_notifications(api_client):
    user = api_client.register_user("browsing-notif")
    ids = [_insert_notification(user.id, f"Browsing QA {i}") for i in range(3)]
    return user, ids


# ── Dashboard data sources ────────────────────────────────────────


def test_dashboard_sources_for_new_user_are_empty_and_scoped(api_client):
    user = api_client.register_user("browsing-dash")
    h = user.auth_headers

    files = api_client.client.get("/api/v1/files", headers=h, params={"page": 1, "page_size": 6})
    assert files.status_code == 200, files.text
    assert files.json()["files"] == [] and files.json()["total"] == 0

    docs = api_client.client.get("/api/v1/documents", headers=h, params={"page": 1, "size": 6})
    assert docs.status_code == 200, docs.text
    assert docs.json()["items"] == []

    activity = api_client.client.get("/api/v1/files/activity", headers=h, params={"limit": 10})
    assert activity.status_code == 200, activity.text
    assert activity.json()["items"] == []


def test_dashboard_reflects_uploaded_file_and_document(api_client):
    user = api_client.register_user("browsing-dash-data")
    h = user.auth_headers
    uploaded = _upload_file(api_client, user, "dash-report.txt")
    api_client.create_document(user, "Dashboard doc", "hello")

    files = api_client.client.get("/api/v1/files", headers=h, params={"page": 1, "page_size": 6})
    assert files.status_code == 200
    assert [f["id"] for f in files.json()["files"]] == [uploaded["id"]]
    assert files.json()["files"][0]["size_bytes"] > 0

    docs = api_client.client.get("/api/v1/documents", headers=h, params={"page": 1, "size": 1})
    assert docs.json()["total"] == 1

    activity = api_client.client.get("/api/v1/files/activity", headers=h, params={"limit": 10})
    assert activity.status_code == 200
    assert any(item.get("resource_id") == uploaded["id"] for item in activity.json()["items"])


def test_dashboard_data_is_not_visible_to_other_users(api_client):
    owner = api_client.register_user("browsing-owner")
    other = api_client.register_user("browsing-other")
    _upload_file(api_client, owner, "private.txt")

    files = api_client.client.get("/api/v1/files", headers=other.auth_headers)
    assert files.status_code == 200
    assert files.json()["total"] == 0


def test_browsing_endpoints_require_auth(api_client):
    for path in ("/api/v1/files", "/api/v1/folders", "/api/v1/notifications", "/api/v1/settings"):
        response = api_client.client.get(path)
        assert response.status_code == 401, f"{path}: {response.status_code} {response.text}"


# ── Folder browsing / breadcrumbs ─────────────────────────────────


def test_folder_tree_browsing(api_client):
    user = api_client.register_user("browsing-folders")
    h = user.auth_headers
    parent = _create_folder(api_client, user, "Parent")
    child = _create_folder(api_client, user, "Child", parent["id"])
    nested = _upload_file(api_client, user, "nested.txt", folder_id=parent["id"])
    root_file = _upload_file(api_client, user, "root.txt")

    roots = api_client.client.get("/api/v1/folders", headers=h).json()["folders"]
    assert [f["id"] for f in roots] == [parent["id"]]

    children = api_client.client.get(
        "/api/v1/folders", headers=h, params={"parent_id": parent["id"]}
    ).json()["folders"]
    assert [f["id"] for f in children] == [child["id"]]

    in_folder = api_client.client.get(
        "/api/v1/files", headers=h, params={"folder_id": parent["id"]}
    ).json()["files"]
    assert [f["id"] for f in in_folder] == [nested["id"]]

    detail = api_client.client.get(f"/api/v1/folders/{parent['id']}", headers=h)
    assert detail.status_code == 200
    assert detail.json()["name"] == "Parent"  # breadcrumb label source

    all_files = {f["id"] for f in api_client.client.get("/api/v1/files", headers=h).json()["files"]}
    assert {nested["id"], root_file["id"]} <= all_files


def test_folder_detail_unknown_and_invalid_ids(api_client):
    user = api_client.register_user("browsing-folder-404")
    missing = api_client.client.get(f"/api/v1/folders/{uuid.uuid4()}", headers=user.auth_headers)
    assert missing.status_code == 404
    invalid = api_client.client.get("/api/v1/folders/not-a-uuid", headers=user.auth_headers)
    assert invalid.status_code == 400


def test_folder_listing_is_owner_scoped(api_client):
    owner = api_client.register_user("browsing-folder-owner")
    other = api_client.register_user("browsing-folder-other")
    parent = _create_folder(api_client, owner, "Secret parent")
    _create_folder(api_client, owner, "Secret child", parent["id"])

    response = api_client.client.get(
        "/api/v1/folders", headers=other.auth_headers, params={"owner_id": owner.id}
    )
    assert response.json()["folders"] == []
    response = api_client.client.get(
        "/api/v1/folders", headers=other.auth_headers, params={"parent_id": parent["id"]}
    )
    assert response.json()["folders"] == []


@pytest.mark.gap_revealer
@pytest.mark.xfail(
    strict=True,
    reason="[REAL] BROWSE-R6: file-service GET/PUT /folders/{id} has no ownership check",
)
def test_folder_detail_and_rename_reject_other_users(api_client):
    owner = api_client.register_user("browsing-idor-owner")
    other = api_client.register_user("browsing-idor-other")
    folder = _create_folder(api_client, owner, "Owner only")

    detail = api_client.client.get(f"/api/v1/folders/{folder['id']}", headers=other.auth_headers)
    rename = api_client.client.put(
        f"/api/v1/folders/{folder['id']}", headers=other.auth_headers, json={"name": "pwned"}
    )
    assert detail.status_code in {403, 404}
    assert rename.status_code in {403, 404}


# ── Pagination ────────────────────────────────────────────────────


def test_file_list_pagination(api_client):
    user = api_client.register_user("browsing-paging")
    h = user.auth_headers
    ids = {_upload_file(api_client, user, f"page-{i}.txt")["id"] for i in range(5)}

    page1 = api_client.client.get("/api/v1/files", headers=h, params={"page": 1, "page_size": 2}).json()
    page2 = api_client.client.get("/api/v1/files", headers=h, params={"page": 2, "page_size": 2}).json()
    page3 = api_client.client.get("/api/v1/files", headers=h, params={"page": 3, "page_size": 2}).json()
    beyond = api_client.client.get("/api/v1/files", headers=h, params={"page": 9, "page_size": 2}).json()

    assert page1["total"] == 5 and page1["page"] == 1 and page1["page_size"] == 2
    assert [len(p["files"]) for p in (page1, page2, page3)] == [2, 2, 1]
    seen = [f["id"] for p in (page1, page2, page3) for f in p["files"]]
    assert len(seen) == len(set(seen)) == 5 and set(seen) == ids
    assert beyond["files"] == [] and beyond["total"] == 5


def test_file_list_page_size_is_capped(api_client):
    user = api_client.register_user("browsing-cap")
    response = api_client.client.get(
        "/api/v1/files", headers=user.auth_headers, params={"page": 1, "page_size": 1000}
    )
    assert response.status_code == 200
    assert response.json()["page_size"] == 100


def test_notifications_pagination_with_page_size(api_client, seeded_notifications):
    user, _ = seeded_notifications
    response = api_client.client.get(
        "/api/v1/notifications", headers=user.auth_headers, params={"page": 1, "page_size": 2}
    )
    body = response.json()
    assert response.status_code == 200
    assert len(body["data"]) == 2 and body["total"] == 3 and body["hasMore"] is True


@pytest.mark.xfail(
    strict=True,
    reason="[REAL] BROWSE-R5: client sends pageSize, notification-service only reads page_size",
)
def test_notifications_pagination_with_client_param_name(api_client, seeded_notifications):
    user, _ = seeded_notifications
    response = api_client.client.get(
        "/api/v1/notifications", headers=user.auth_headers, params={"page": 1, "pageSize": 2}
    )
    assert len(response.json()["data"]) == 2


# ── Notifications panel ───────────────────────────────────────────


def test_notifications_list_and_unread_count(api_client, seeded_notifications):
    user, ids = seeded_notifications
    h = user.auth_headers
    listing = api_client.client.get("/api/v1/notifications", headers=h)
    assert listing.status_code == 200, listing.text
    assert {n["id"] for n in listing.json()["data"]} == set(ids)
    assert all(n["read"] is False for n in listing.json()["data"])

    count = api_client.client.get("/api/v1/notifications/unread-count", headers=h)
    assert count.status_code == 200
    assert count.json()["unreadCount"] == 3


@pytest.mark.xfail(
    strict=True,
    reason="[REAL] BROWSE-R4: client reads unread-count `count`, service returns `unreadCount`",
)
def test_unread_count_matches_client_contract(api_client, seeded_notifications):
    user, _ = seeded_notifications
    body = api_client.client.get("/api/v1/notifications/unread-count", headers=user.auth_headers).json()
    assert body.get("count") == 3


def test_notifications_are_scoped_to_caller_not_query_param(api_client, seeded_notifications):
    owner, _ = seeded_notifications
    other = api_client.register_user("browsing-notif-other")
    response = api_client.client.get(
        "/api/v1/notifications", headers=other.auth_headers, params={"user_id": owner.id}
    )
    assert response.status_code == 200
    assert response.json()["data"] == []


def test_mark_read_and_mark_all_read_with_service_verbs(api_client, seeded_notifications):
    user, ids = seeded_notifications
    h = user.auth_headers
    single = api_client.client.put(f"/api/v1/notifications/{ids[0]}/read", headers=h)
    assert single.status_code == 204
    assert api_client.client.get("/api/v1/notifications/unread-count", headers=h).json()["unreadCount"] == 2

    all_read = api_client.client.put("/api/v1/notifications/read-all", headers=h)
    assert all_read.status_code == 200
    assert all_read.json()["markedCount"] == 2
    assert api_client.client.get("/api/v1/notifications/unread-count", headers=h).json()["unreadCount"] == 0


@pytest.mark.xfail(
    strict=True,
    reason="[REAL] BROWSE-R3: client marks a notification read with PATCH; service only routes PUT",
)
def test_mark_read_with_client_verb(api_client, seeded_notifications):
    user, ids = seeded_notifications
    response = api_client.client.patch(f"/api/v1/notifications/{ids[0]}/read", headers=user.auth_headers)
    assert response.status_code in {200, 204}


@pytest.mark.xfail(
    strict=True,
    reason="[REAL] BROWSE-R2: client 'Mark all as read' uses POST; service only routes PUT (405)",
)
def test_mark_all_read_with_client_verb(api_client, seeded_notifications):
    user, _ = seeded_notifications
    response = api_client.client.post("/api/v1/notifications/read-all", headers=user.auth_headers)
    assert response.status_code == 200


@pytest.mark.gap_revealer
@pytest.mark.xfail(
    strict=True,
    reason="[REAL] BROWSE-R7: GET/PUT /notifications/{id} have no ownership check",
)
def test_other_user_cannot_read_or_ack_notification(api_client, seeded_notifications):
    owner, ids = seeded_notifications
    other = api_client.register_user("browsing-notif-idor")
    detail = api_client.client.get(f"/api/v1/notifications/{ids[0]}", headers=other.auth_headers)
    ack = api_client.client.put(f"/api/v1/notifications/{ids[0]}/read", headers=other.auth_headers)
    assert detail.status_code in {403, 404}
    assert ack.status_code in {403, 404}


# ── Settings ──────────────────────────────────────────────────────


def test_settings_defaults_and_toggle(api_client):
    user = api_client.register_user("browsing-settings")
    h = user.auth_headers
    defaults = api_client.client.get("/api/v1/settings", headers=h)
    assert defaults.status_code == 200
    assert defaults.json()["notificationEmail"] is True
    assert defaults.json()["notificationInApp"] is True
    assert defaults.json()["notificationDesktop"] is False

    updated = api_client.client.patch("/api/v1/settings", headers=h, json={"notificationDesktop": True})
    assert updated.status_code == 200
    assert updated.json()["notificationDesktop"] is True
    assert api_client.client.get("/api/v1/settings", headers=h).json()["notificationDesktop"] is True


def test_profile_update_with_service_verb(api_client):
    user = api_client.register_user("browsing-profile")
    response = api_client.client.put(
        "/api/v1/auth/profile",
        headers=user.auth_headers,
        json={"displayName": "Renamed Browser", "email": user.email},
    )
    assert response.status_code == 200, response.text
    assert response.json()["displayName"] == "Renamed Browser"


@pytest.mark.xfail(
    strict=True,
    reason="[REAL] BROWSE-R1: settings 'Save changes' sends PATCH /auth/profile; auth-service returns 500",
)
def test_profile_update_with_client_verb(api_client):
    user = api_client.register_user("browsing-profile-patch")
    response = api_client.client.patch(
        "/api/v1/auth/profile",
        headers=user.auth_headers,
        json={"displayName": "Renamed Browser", "email": user.email},
    )
    assert response.status_code == 200, response.text
