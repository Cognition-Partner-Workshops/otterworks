"""QA browsing: folder tree navigation, deep links, pagination and recent ordering."""

import time
import uuid

import pytest


pytestmark = pytest.mark.api_flow


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


def _upload(api_client, user, name, folder_id=None):
    data = {"owner_id": user.id}
    if folder_id:
        data["folder_id"] = folder_id
    response = api_client.client.post(
        "/api/v1/files/upload",
        headers=user.auth_headers,
        files={"file": (name, f"qa browsing {name}".encode(), "text/plain")},
        data=data,
    )
    assert response.status_code == 201, response.text
    file_metadata = response.json()["file"]
    api_client.created_files.append(file_metadata["id"])
    return file_metadata


def _names(response, key="files"):
    assert response.status_code == 200, response.text
    return sorted(item["name"] for item in response.json()[key])


def test_folder_tree_lists_children_per_level(api_client):
    user = api_client.register_user("qa-browse-tree")
    parent = _create_folder(api_client, user, "Parent")
    child = _create_folder(api_client, user, "Child", parent["id"])
    _create_folder(api_client, user, "Grandchild", child["id"])

    root = api_client.client.get("/api/v1/folders", headers=user.auth_headers)
    assert _names(root, "folders") == ["Parent"]

    level1 = api_client.client.get("/api/v1/folders", headers=user.auth_headers, params={"parent_id": parent["id"]})
    assert _names(level1, "folders") == ["Child"]

    level2 = api_client.client.get("/api/v1/folders", headers=user.auth_headers, params={"parent_id": child["id"]})
    assert _names(level2, "folders") == ["Grandchild"]


def test_folder_deep_link_returns_folder_for_breadcrumb(api_client):
    user = api_client.register_user("qa-browse-deeplink")
    parent = _create_folder(api_client, user, "Breadcrumb Parent")
    child = _create_folder(api_client, user, "Breadcrumb Child", parent["id"])

    response = api_client.client.get(f"/api/v1/folders/{child['id']}", headers=user.auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == "Breadcrumb Child"
    assert body["parent_id"] == parent["id"]


def test_folder_scoped_file_listing(api_client):
    user = api_client.register_user("qa-browse-scope")
    folder = _create_folder(api_client, user, "Scoped")
    _upload(api_client, user, "inside.txt", folder["id"])
    _upload(api_client, user, "outside.txt")

    scoped = api_client.client.get("/api/v1/files", headers=user.auth_headers, params={"folder_id": folder["id"]})
    assert _names(scoped) == ["inside.txt"]


@pytest.mark.gap_revealer
def test_root_file_listing_excludes_files_inside_folders(api_client):
    """The Files root view calls GET /files without folder_id and should only show root-level files."""
    user = api_client.register_user("qa-browse-root")
    folder = _create_folder(api_client, user, "Nested")
    _upload(api_client, user, "nested.txt", folder["id"])
    _upload(api_client, user, "top.txt")

    root = api_client.client.get("/api/v1/files", headers=user.auth_headers)
    assert _names(root) == ["top.txt"], "root listing leaks files that live inside sub-folders"


def test_file_listing_pagination(api_client):
    user = api_client.register_user("qa-browse-page")
    for i in range(3):
        _upload(api_client, user, f"page-{i}.txt")

    seen = []
    for page in (1, 2, 3):
        response = api_client.client.get(
            "/api/v1/files", headers=user.auth_headers, params={"page": page, "page_size": 1}
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["total"] == 3
        assert body["page"] == page
        assert body["page_size"] == 1
        assert len(body["files"]) == 1
        seen.append(body["files"][0]["id"])
    assert len(set(seen)) == 3, "pages must not repeat items"

    beyond = api_client.client.get("/api/v1/files", headers=user.auth_headers, params={"page": 4, "page_size": 1})
    assert beyond.status_code == 200
    assert beyond.json()["files"] == []


def test_file_listing_pagination_bounds_are_clamped(api_client):
    user = api_client.register_user("qa-browse-clamp")
    response = api_client.client.get(
        "/api/v1/files", headers=user.auth_headers, params={"page": 0, "page_size": 1000}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["page"] == 1
    assert body["page_size"] <= 100


def test_recent_files_first_page_is_newest_first(api_client):
    """Dashboard/Recent use GET /files?page=1&page_size=N as 'recent' — newest should come first."""
    user = api_client.register_user("qa-browse-recent")
    names = []
    for i in range(4):
        names.append(_upload(api_client, user, f"recent-{i}.txt")["name"])
        time.sleep(0.05)

    response = api_client.client.get(
        "/api/v1/files", headers=user.auth_headers, params={"page": 1, "page_size": 10}
    )
    assert response.status_code == 200, response.text
    stamps = [f["updated_at"] for f in response.json()["files"]]
    assert stamps == sorted(stamps, reverse=True), "first page of /files is not ordered newest-first"


def test_new_user_sees_empty_browsing_views(api_client):
    user = api_client.register_user("qa-browse-empty")
    for path, key in (("/api/v1/files", "files"), ("/api/v1/folders", "folders"), ("/api/v1/files/trash", "files")):
        response = api_client.client.get(path, headers=user.auth_headers)
        assert response.status_code == 200, f"{path}: {response.text}"
        assert response.json()[key] == [], path


def test_users_only_see_their_own_files_and_folders(api_client):
    owner = api_client.register_user("qa-browse-owner")
    other = api_client.register_user("qa-browse-other")
    _create_folder(api_client, owner, "Private Folder")
    _upload(api_client, owner, "private.txt")

    assert api_client.client.get("/api/v1/files", headers=other.auth_headers).json()["files"] == []
    assert api_client.client.get("/api/v1/folders", headers=other.auth_headers).json()["folders"] == []


@pytest.mark.gap_revealer
def test_folder_deep_link_is_not_readable_by_other_users(api_client):
    owner = api_client.register_user("qa-browse-fowner")
    other = api_client.register_user("qa-browse-fother")
    folder = _create_folder(api_client, owner, "Secret Folder")

    response = api_client.client.get(f"/api/v1/folders/{folder['id']}", headers=other.auth_headers)
    assert response.status_code in {403, 404}, (
        f"another user can read folder metadata via deep link: {response.status_code} {response.text}"
    )


def test_broken_deep_links_return_json_errors(api_client):
    user = api_client.register_user("qa-browse-404")
    missing_folder = api_client.client.get(f"/api/v1/folders/{uuid.uuid4()}", headers=user.auth_headers)
    assert missing_folder.status_code == 404
    api_client.assert_json_error(missing_folder)

    missing_file = api_client.client.get(f"/api/v1/files/{uuid.uuid4()}", headers=user.auth_headers)
    assert missing_file.status_code == 404
    api_client.assert_json_error(missing_file)

    malformed = api_client.client.get("/api/v1/folders/not-a-uuid", headers=user.auth_headers)
    assert malformed.status_code == 400


def test_browsing_endpoints_require_auth(api_client):
    for path in ("/api/v1/files", "/api/v1/folders", "/api/v1/files/trash"):
        assert api_client.client.get(path).status_code == 401, path
