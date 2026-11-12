import pytest


pytestmark = pytest.mark.api_flow


def test_file_folder_upload_lifecycle_share_and_download(api_client):
    owner = api_client.register_user("file-owner")
    collaborator = api_client.register_user("file-collaborator")

    folder_response = api_client.client.post(
        "/api/v1/folders",
        headers=owner.auth_headers,
        json={"name": f"Flow Folder {api_client.run_id}", "owner_id": owner.id},
    )
    api_client.assert_gateway_route_available(folder_response, "/api/v1/folders")
    assert folder_response.status_code == 201, folder_response.text
    folder = folder_response.json()
    api_client.created_folders.append(folder["id"])

    upload_response = api_client.client.post(
        "/api/v1/files/upload",
        headers=owner.auth_headers,
        files={"file": ("flow.txt", b"hello file flow", "text/plain")},
        data={"folder_id": folder["id"]},
    )
    assert upload_response.status_code == 201, upload_response.text
    file_metadata = upload_response.json()["file"]
    file_id = file_metadata["id"]
    api_client.created_files.append(file_id)
    assert file_metadata["owner_id"] == owner.id
    assert file_metadata["folder_id"] == folder["id"]
    assert file_metadata["version"] == 1

    list_response = api_client.client.get(
        "/api/v1/files",
        headers=owner.auth_headers,
        params={"owner_id": owner.id, "page": 1, "page_size": 10},
    )
    assert list_response.status_code == 200, list_response.text
    assert any(item["id"] == file_id for item in list_response.json()["files"])

    get_response = api_client.client.get(f"/api/v1/files/{file_id}", headers=owner.auth_headers)
    assert get_response.status_code == 200, get_response.text
    assert get_response.json()["id"] == file_id

    download_response = api_client.client.get(
        f"/api/v1/files/{file_id}/download",
        headers=owner.auth_headers,
    )
    assert download_response.status_code == 200, download_response.text
    assert download_response.json()["url"]

    versions_response = api_client.client.get(
        f"/api/v1/files/{file_id}/versions",
        headers=owner.auth_headers,
    )
    assert versions_response.status_code == 200, versions_response.text
    assert versions_response.json()["versions"][0]["version"] == 1

    share_response = api_client.client.post(
        f"/api/v1/files/{file_id}/share",
        headers=owner.auth_headers,
        json={
            "shared_with": collaborator.id,
            "permission": "viewer",
            "shared_by": owner.id,
        },
    )
    assert share_response.status_code == 201, share_response.text
    assert share_response.json()["share"]["shared_with"] == collaborator.id

    trash_response = api_client.client.post(f"/api/v1/files/{file_id}/trash", headers=owner.auth_headers)
    assert trash_response.status_code == 200, trash_response.text
    assert trash_response.json()["is_trashed"] is True

    restore_response = api_client.client.post(f"/api/v1/files/{file_id}/restore", headers=owner.auth_headers)
    assert restore_response.status_code == 200, restore_response.text
    assert restore_response.json()["is_trashed"] is False

    move_response = api_client.client.put(
        f"/api/v1/files/{file_id}/move",
        headers=owner.auth_headers,
        json={"folder_id": None},
    )
    assert move_response.status_code == 200, move_response.text
    assert move_response.json()["folder_id"] is None

    delete_file_response = api_client.client.delete(f"/api/v1/files/{file_id}", headers=owner.auth_headers)
    assert delete_file_response.status_code == 204, delete_file_response.text
    api_client.created_files.remove(file_id)

    deleted_get_response = api_client.client.get(f"/api/v1/files/{file_id}", headers=owner.auth_headers)
    assert deleted_get_response.status_code == 404

    delete_folder_response = api_client.client.delete(
        f"/api/v1/folders/{folder['id']}",
        headers=owner.auth_headers,
    )
    assert delete_folder_response.status_code == 204, delete_folder_response.text
    api_client.created_folders.remove(folder["id"])


@pytest.mark.gap_revealer
def test_file_validation_and_route_gaps(api_client):
    owner = api_client.register_user("file-validation")

    empty_upload_response = api_client.client.post(
        "/api/v1/files/upload",
        headers=owner.auth_headers,
        files={"file": ("empty.txt", b"", "text/plain")},
    )
    assert empty_upload_response.status_code in {400, 422}

    missing_owner_upload = api_client.client.post(
        "/api/v1/files/upload",
        files={"file": ("no-owner.txt", b"body", "text/plain")},
    )
    assert missing_owner_upload.status_code in {400, 401, 403}

    invalid_file_id = api_client.client.get("/api/v1/files/not-a-uuid", headers=owner.auth_headers)
    assert invalid_file_id.status_code in {400, 422}

    folder_route_response = api_client.client.post(
        "/api/v1/folders",
        headers=owner.auth_headers,
        json={"name": "route probe", "owner_id": owner.id},
    )
    api_client.assert_gateway_route_available(folder_route_response, "/api/v1/folders")


def _upload_file(api_client, owner, name: str = "private.txt") -> str:
    response = api_client.client.post(
        "/api/v1/files/upload",
        headers=owner.auth_headers,
        files={"file": (name, b"owner-only bytes", "text/plain")},
    )
    assert response.status_code == 201, response.text
    file_id = response.json()["file"]["id"]
    api_client.created_files.append(file_id)
    return file_id


def _share_file(api_client, owner, file_id: str, user, permission: str) -> dict:
    response = api_client.client.post(
        f"/api/v1/files/{file_id}/share",
        headers=owner.auth_headers,
        # The web client still sends shared_by; the service must not rely on it.
        json={"shared_with": user.id, "permission": permission, "shared_by": owner.id},
    )
    assert response.status_code == 201, response.text
    return response.json()["share"]


def _by_id_requests(file_id: str, attacker_id: str, shared_user_id: str) -> list[tuple[str, str, dict]]:
    base = f"/api/v1/files/{file_id}"
    return [
        ("GET", base, {}),
        ("GET", f"{base}/download", {}),
        ("GET", f"{base}/versions", {}),
        ("PATCH", f"{base}/rename", {"json": {"name": "taken-over.txt"}}),
        ("PUT", f"{base}/move", {"json": {"folder_id": None}}),
        ("POST", f"{base}/trash", {}),
        ("POST", f"{base}/restore", {}),
        ("POST", f"{base}/share", {"json": {"shared_with": attacker_id, "permission": "editor"}}),
        ("DELETE", f"{base}/share/{shared_user_id}", {}),
        ("DELETE", base, {}),
    ]


def test_file_by_id_routes_hide_files_from_other_users(api_client):
    owner = api_client.register_user("file-owner")
    collaborator = api_client.register_user("file-collaborator")
    attacker = api_client.register_user("file-attacker")
    file_id = _upload_file(api_client, owner)
    _share_file(api_client, owner, file_id, collaborator, "viewer")

    missing_id = "00000000-0000-4000-8000-000000000000"
    missing_response = api_client.client.get(f"/api/v1/files/{missing_id}", headers=attacker.auth_headers)
    assert missing_response.status_code == 404

    for method, path, kwargs in _by_id_requests(file_id, attacker.id, collaborator.id):
        response = api_client.client.request(method, path, headers=attacker.auth_headers, **kwargs)
        assert response.status_code == 404, f"{method} {path} -> {response.status_code} {response.text}"
        # Same body shape as a file that does not exist, so ids cannot be probed.
        assert response.json()["error"] == missing_response.json()["error"]
        assert "private.txt" not in response.text

    owner_view = api_client.client.get(f"/api/v1/files/{file_id}", headers=owner.auth_headers)
    assert owner_view.status_code == 200, owner_view.text
    file_state = owner_view.json()
    assert file_state["name"] == "private.txt"
    assert file_state["is_trashed"] is False
    assert [share["shared_with"] for share in file_state["shared_with"]] == [collaborator.id]


def test_file_share_records_the_caller_not_the_request_body(api_client):
    owner = api_client.register_user("file-owner")
    collaborator = api_client.register_user("file-collaborator")
    bystander = api_client.register_user("file-bystander")
    file_id = _upload_file(api_client, owner)

    response = api_client.client.post(
        f"/api/v1/files/{file_id}/share",
        headers=owner.auth_headers,
        json={"shared_with": collaborator.id, "permission": "viewer", "shared_by": bystander.id},
    )
    assert response.status_code == 201, response.text
    assert response.json()["share"]["shared_by"] == owner.id

    upgrade = api_client.client.post(
        f"/api/v1/files/{file_id}/share",
        headers=owner.auth_headers,
        json={"shared_with": collaborator.id, "permission": "editor", "shared_by": bystander.id},
    )
    assert upgrade.status_code == 200, upgrade.text
    assert upgrade.json()["share"]["permission"] == "editor"
    assert upgrade.json()["share"]["shared_by"] == owner.id

    without_actor = api_client.client.post(
        f"/api/v1/files/{file_id}/share",
        headers=owner.auth_headers,
        json={"shared_with": bystander.id, "permission": "viewer"},
    )
    assert without_actor.status_code == 201, without_actor.text
    assert without_actor.json()["share"]["shared_by"] == owner.id


def test_file_share_permissions_limit_what_a_collaborator_can_do(api_client):
    owner = api_client.register_user("file-owner")
    viewer = api_client.register_user("file-viewer")
    editor = api_client.register_user("file-editor")
    file_id = _upload_file(api_client, owner)
    _share_file(api_client, owner, file_id, viewer, "viewer")
    _share_file(api_client, owner, file_id, editor, "editor")
    base = f"/api/v1/files/{file_id}"

    for user in (viewer, editor):
        for path in (base, f"{base}/download", f"{base}/versions"):
            response = api_client.client.get(path, headers=user.auth_headers)
            assert response.status_code == 200, f"{path} -> {response.status_code} {response.text}"

    viewer_writes = [
        ("PATCH", f"{base}/rename", {"json": {"name": "viewer-rename.txt"}}),
        ("PUT", f"{base}/move", {"json": {"folder_id": None}}),
        ("POST", f"{base}/trash", {}),
        ("POST", f"{base}/restore", {}),
    ]
    owner_only = [
        ("POST", f"{base}/share", {"json": {"shared_with": viewer.id, "permission": "editor"}}),
        ("DELETE", f"{base}/share/{editor.id}", {}),
        ("DELETE", base, {}),
    ]
    for method, path, kwargs in viewer_writes + owner_only:
        response = api_client.client.request(method, path, headers=viewer.auth_headers, **kwargs)
        assert response.status_code == 404, f"viewer {method} {path} -> {response.status_code}"
    for method, path, kwargs in owner_only:
        response = api_client.client.request(method, path, headers=editor.auth_headers, **kwargs)
        assert response.status_code == 404, f"editor {method} {path} -> {response.status_code}"

    rename = api_client.client.patch(
        f"{base}/rename", headers=editor.auth_headers, json={"name": "editor-rename.txt"}
    )
    assert rename.status_code == 200, rename.text
    trash = api_client.client.post(f"{base}/trash", headers=editor.auth_headers)
    assert trash.status_code == 200, trash.text
    restore = api_client.client.post(f"{base}/restore", headers=editor.auth_headers)
    assert restore.status_code == 200, restore.text
    move = api_client.client.put(f"{base}/move", headers=editor.auth_headers, json={"folder_id": None})
    assert move.status_code == 200, move.text

    owner_view = api_client.client.get(base, headers=owner.auth_headers)
    assert owner_view.status_code == 200, owner_view.text
    file_state = owner_view.json()
    assert file_state["name"] == "editor-rename.txt"
    assert file_state["is_trashed"] is False
    shares = {share["shared_with"]: share["permission"] for share in file_state["shared_with"]}
    assert shares == {viewer.id: "viewer", editor.id: "editor"}
