"""QA browsing: trash listing, restore from trash and permanent delete."""

import pytest


pytestmark = pytest.mark.api_flow


def _upload(api_client, user, name, folder_id=None):
    data = {"owner_id": user.id}
    if folder_id:
        data["folder_id"] = folder_id
    response = api_client.client.post(
        "/api/v1/files/upload",
        headers=user.auth_headers,
        files={"file": (name, f"qa trash {name}".encode(), "text/plain")},
        data=data,
    )
    assert response.status_code == 201, response.text
    file_metadata = response.json()["file"]
    api_client.created_files.append(file_metadata["id"])
    return file_metadata


def _ids(response):
    assert response.status_code == 200, response.text
    return {f["id"] for f in response.json()["files"]}


def test_trash_and_restore_round_trip(api_client):
    user = api_client.register_user("qa-trash-roundtrip")
    file_metadata = _upload(api_client, user, "roundtrip.txt")
    fid = file_metadata["id"]

    trashed = api_client.client.post(f"/api/v1/files/{fid}/trash", headers=user.auth_headers)
    assert trashed.status_code == 200, trashed.text
    assert trashed.json()["is_trashed"] is True

    assert fid in _ids(api_client.client.get("/api/v1/files/trash", headers=user.auth_headers))
    assert fid not in _ids(api_client.client.get("/api/v1/files", headers=user.auth_headers))

    restored = api_client.client.post(f"/api/v1/files/{fid}/restore", headers=user.auth_headers)
    assert restored.status_code == 200, restored.text
    assert restored.json()["is_trashed"] is False

    assert fid not in _ids(api_client.client.get("/api/v1/files/trash", headers=user.auth_headers))
    assert fid in _ids(api_client.client.get("/api/v1/files", headers=user.auth_headers))


def test_restore_returns_file_to_its_original_folder(api_client):
    user = api_client.register_user("qa-trash-folder")
    folder = api_client.client.post(
        "/api/v1/folders", headers=user.auth_headers, json={"name": "Home", "owner_id": user.id}
    ).json()
    api_client.created_folders.append(folder["id"])
    fid = _upload(api_client, user, "homed.txt", folder["id"])["id"]

    api_client.client.post(f"/api/v1/files/{fid}/trash", headers=user.auth_headers)
    restored = api_client.client.post(f"/api/v1/files/{fid}/restore", headers=user.auth_headers)
    assert restored.status_code == 200, restored.text
    assert restored.json()["folder_id"] == folder["id"]
    in_folder = api_client.client.get(
        "/api/v1/files", headers=user.auth_headers, params={"folder_id": folder["id"]}
    )
    assert fid in _ids(in_folder)


def test_trash_listing_is_scoped_to_caller_even_with_spoofed_owner(api_client):
    owner = api_client.register_user("qa-trash-owner")
    other = api_client.register_user("qa-trash-other")
    fid = _upload(api_client, owner, "mine.txt")["id"]
    api_client.client.post(f"/api/v1/files/{fid}/trash", headers=owner.auth_headers)

    assert fid not in _ids(api_client.client.get("/api/v1/files/trash", headers=other.auth_headers))
    spoofed = api_client.client.get(
        "/api/v1/files/trash", headers=other.auth_headers, params={"owner_id": owner.id}
    )
    assert fid not in _ids(spoofed)


def test_trash_pagination(api_client):
    user = api_client.register_user("qa-trash-page")
    for i in range(3):
        fid = _upload(api_client, user, f"tp-{i}.txt")["id"]
        api_client.client.post(f"/api/v1/files/{fid}/trash", headers=user.auth_headers)

    first = api_client.client.get("/api/v1/files/trash", headers=user.auth_headers, params={"page": 1, "page_size": 2})
    second = api_client.client.get("/api/v1/files/trash", headers=user.auth_headers, params={"page": 2, "page_size": 2})
    assert first.json()["total"] == 3
    assert len(first.json()["files"]) == 2
    assert len(second.json()["files"]) == 1
    assert _ids(first).isdisjoint(_ids(second))
    stamps = [f["updated_at"] for f in first.json()["files"] + second.json()["files"]]
    assert stamps == sorted(stamps, reverse=True), "trash should be most-recently-trashed first"


def test_permanent_delete_removes_from_trash(api_client):
    user = api_client.register_user("qa-trash-purge")
    fid = _upload(api_client, user, "purge.txt")["id"]
    api_client.client.post(f"/api/v1/files/{fid}/trash", headers=user.auth_headers)

    deleted = api_client.client.delete(f"/api/v1/files/{fid}", headers=user.auth_headers)
    assert deleted.status_code in {200, 204}, deleted.text
    assert fid not in _ids(api_client.client.get("/api/v1/files/trash", headers=user.auth_headers))
    assert api_client.client.get(f"/api/v1/files/{fid}", headers=user.auth_headers).status_code == 404


@pytest.mark.gap_revealer
def test_other_user_cannot_trash_my_file(api_client):
    owner = api_client.register_user("qa-trash-victim")
    attacker = api_client.register_user("qa-trash-attacker")
    fid = _upload(api_client, owner, "victim.txt")["id"]

    response = api_client.client.post(f"/api/v1/files/{fid}/trash", headers=attacker.auth_headers)
    assert response.status_code in {403, 404}, f"cross-user trash allowed: {response.status_code}"
    assert fid in _ids(api_client.client.get("/api/v1/files", headers=owner.auth_headers))


@pytest.mark.gap_revealer
def test_other_user_cannot_restore_my_trashed_file(api_client):
    owner = api_client.register_user("qa-restore-victim")
    attacker = api_client.register_user("qa-restore-attacker")
    fid = _upload(api_client, owner, "binned.txt")["id"]
    api_client.client.post(f"/api/v1/files/{fid}/trash", headers=owner.auth_headers)

    response = api_client.client.post(f"/api/v1/files/{fid}/restore", headers=attacker.auth_headers)
    assert response.status_code in {403, 404}, f"cross-user restore allowed: {response.status_code}"
    assert fid in _ids(api_client.client.get("/api/v1/files/trash", headers=owner.auth_headers))


def test_restore_unknown_file_is_404(api_client):
    user = api_client.register_user("qa-restore-404")
    response = api_client.client.post(
        "/api/v1/files/00000000-0000-4000-8000-000000000000/restore", headers=user.auth_headers
    )
    assert response.status_code == 404, response.text
    api_client.assert_json_error(response)
