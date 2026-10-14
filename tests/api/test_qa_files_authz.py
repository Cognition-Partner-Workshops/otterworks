"""QA (files area): a user must not be able to read or mutate another user's file."""

import pytest


pytestmark = [pytest.mark.api_flow, pytest.mark.gap_revealer]

DENIED = {403, 404}


@pytest.fixture
def victimFile(api_client):
    owner = api_client.register_user("qa-files-owner")
    intruder = api_client.register_user("qa-files-intruder")
    upload = api_client.client.post(
        "/api/v1/files/upload",
        headers=owner.auth_headers,
        files={"file": ("private.txt", b"top secret", "text/plain")},
    )
    assert upload.status_code == 201, upload.text
    fileId = upload.json()["file"]["id"]
    api_client.created_files.append(fileId)
    return owner, intruder, fileId


def assertUnchanged(api_client, owner, fileId):
    current = api_client.client.get(f"/api/v1/files/{fileId}", headers=owner.auth_headers)
    assert current.status_code == 200, current.text
    body = current.json()
    assert body["name"] == "private.txt"
    assert body["is_trashed"] is False
    assert body["folder_id"] is None


def test_other_user_cannot_read_metadata(api_client, victimFile):
    _, intruder, fileId = victimFile
    response = api_client.client.get(f"/api/v1/files/{fileId}", headers=intruder.auth_headers)
    assert response.status_code in DENIED, f"metadata leaked to non-owner: {response.status_code}"


def test_other_user_cannot_get_download_url(api_client, victimFile):
    _, intruder, fileId = victimFile
    response = api_client.client.get(f"/api/v1/files/{fileId}/download", headers=intruder.auth_headers)
    assert response.status_code in DENIED, f"download URL issued to non-owner: {response.status_code}"


def test_other_user_cannot_rename(api_client, victimFile):
    owner, intruder, fileId = victimFile
    response = api_client.client.patch(
        f"/api/v1/files/{fileId}/rename", headers=intruder.auth_headers, json={"name": "pwned.txt"}
    )
    assert response.status_code in DENIED, f"non-owner rename allowed: {response.status_code}"
    assertUnchanged(api_client, owner, fileId)


def test_other_user_cannot_move(api_client, victimFile):
    owner, intruder, fileId = victimFile
    folder = api_client.client.post(
        "/api/v1/folders",
        headers=intruder.auth_headers,
        json={"name": f"Intruder {api_client.run_id}", "owner_id": intruder.id},
    )
    assert folder.status_code == 201, folder.text
    api_client.created_folders.append(folder.json()["id"])
    response = api_client.client.put(
        f"/api/v1/files/{fileId}/move", headers=intruder.auth_headers, json={"folder_id": folder.json()["id"]}
    )
    assert response.status_code in DENIED, f"non-owner move allowed: {response.status_code}"
    assertUnchanged(api_client, owner, fileId)


def test_other_user_cannot_trash(api_client, victimFile):
    owner, intruder, fileId = victimFile
    response = api_client.client.post(f"/api/v1/files/{fileId}/trash", headers=intruder.auth_headers)
    assert response.status_code in DENIED, f"non-owner trash allowed: {response.status_code}"
    assertUnchanged(api_client, owner, fileId)


def test_other_user_cannot_delete(api_client, victimFile):
    owner, intruder, fileId = victimFile
    response = api_client.client.delete(f"/api/v1/files/{fileId}", headers=intruder.auth_headers)
    assert response.status_code in DENIED, f"non-owner delete allowed: {response.status_code}"
    assertUnchanged(api_client, owner, fileId)
