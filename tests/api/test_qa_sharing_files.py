"""QA: file sharing between registered users through the api-gateway."""

import uuid

import pytest


pytestmark = pytest.mark.api_flow


def uploadFile(apiClient, owner, name="qa-share.txt", body=b"qa sharing payload"):
    response = apiClient.client.post(
        "/api/v1/files/upload",
        headers=owner.auth_headers,
        files={"file": (name, body, "text/plain")},
    )
    assert response.status_code == 201, response.text
    fileId = response.json()["file"]["id"]
    apiClient.created_files.append(fileId)
    return fileId


def shareFile(apiClient, owner, fileId, target, permission):
    return apiClient.client.post(
        f"/api/v1/files/{fileId}/share",
        headers=owner.auth_headers,
        json={"shared_with": target.id, "permission": permission, "shared_by": owner.id},
    )


def sharedIds(apiClient, user):
    response = apiClient.client.get(
        "/api/v1/files/shared",
        headers=user.auth_headers,
        params={"page": 1, "page_size": 50},
    )
    assert response.status_code == 200, response.text
    return {item["id"] for item in response.json()["files"]}


def test_share_view_then_edit_then_revoke_lifecycle(api_client):
    owner = api_client.register_user("qa-share-owner")
    collaborator = api_client.register_user("qa-share-collab")
    outsider = api_client.register_user("qa-share-outsider")
    fileId = uploadFile(api_client, owner)

    viewResponse = shareFile(api_client, owner, fileId, collaborator, "viewer")
    assert viewResponse.status_code == 201, viewResponse.text
    share = viewResponse.json()["share"]
    assert share["file_id"] == fileId
    assert share["shared_with"] == collaborator.id
    assert share["shared_by"] == owner.id
    assert share["permission"] == "viewer"

    assert fileId in sharedIds(api_client, collaborator)
    assert fileId not in sharedIds(api_client, outsider)
    assert fileId not in sharedIds(api_client, owner)

    editResponse = shareFile(api_client, owner, fileId, collaborator, "editor")
    assert editResponse.status_code == 200, editResponse.text
    assert editResponse.json()["share"]["id"] == share["id"]
    assert editResponse.json()["share"]["permission"] == "editor"

    sameResponse = shareFile(api_client, owner, fileId, collaborator, "editor")
    assert sameResponse.status_code == 200, sameResponse.text
    assert sameResponse.json()["share"]["id"] == share["id"]

    detail = api_client.client.get(f"/api/v1/files/{fileId}", headers=owner.auth_headers)
    assert detail.status_code == 200, detail.text
    entries = [s for s in detail.json()["shared_with"] if s["shared_with"] == collaborator.id]
    assert len(entries) == 1
    assert entries[0]["permission"] == "editor"

    revokeResponse = api_client.client.delete(
        f"/api/v1/files/{fileId}/share/{collaborator.id}", headers=owner.auth_headers
    )
    assert revokeResponse.status_code == 204, revokeResponse.text
    assert fileId not in sharedIds(api_client, collaborator)

    detailAfter = api_client.client.get(f"/api/v1/files/{fileId}", headers=owner.auth_headers)
    assert all(s["shared_with"] != collaborator.id for s in detailAfter.json()["shared_with"])

    revokeAgain = api_client.client.delete(
        f"/api/v1/files/{fileId}/share/{collaborator.id}", headers=owner.auth_headers
    )
    assert revokeAgain.status_code == 404, revokeAgain.text


def test_shared_with_me_requires_auth_and_hides_trashed_files(api_client):
    owner = api_client.register_user("qa-share-trash-owner")
    collaborator = api_client.register_user("qa-share-trash-collab")
    fileId = uploadFile(api_client, owner)
    assert shareFile(api_client, owner, fileId, collaborator, "viewer").status_code == 201

    unauthenticated = api_client.client.get("/api/v1/files/shared")
    assert unauthenticated.status_code == 401, unauthenticated.text

    assert fileId in sharedIds(api_client, collaborator)
    trashResponse = api_client.client.post(f"/api/v1/files/{fileId}/trash", headers=owner.auth_headers)
    assert trashResponse.status_code == 200, trashResponse.text
    assert fileId not in sharedIds(api_client, collaborator)


def test_share_rejects_invalid_permission_and_unknown_file(api_client):
    owner = api_client.register_user("qa-share-validate-owner")
    collaborator = api_client.register_user("qa-share-validate-collab")
    fileId = uploadFile(api_client, owner)

    for badPermission in ("owner", "view", "edit", ""):
        response = shareFile(api_client, owner, fileId, collaborator, badPermission)
        assert response.status_code in {400, 422}, f"{badPermission!r}: {response.status_code} {response.text}"

    missingFile = shareFile(api_client, owner, str(uuid.uuid4()), collaborator, "viewer")
    assert missingFile.status_code == 404, missingFile.text

    badId = api_client.client.delete(
        f"/api/v1/files/not-a-uuid/share/{collaborator.id}", headers=owner.auth_headers
    )
    assert badId.status_code == 400, badId.text
    assert fileId not in sharedIds(api_client, collaborator)


def test_share_target_lookup_by_email(api_client):
    owner = api_client.register_user("qa-share-lookup-owner")
    collaborator = api_client.register_user("qa-share-lookup-collab")

    found = api_client.client.get(
        "/api/v1/auth/users/lookup", headers=owner.auth_headers, params={"email": collaborator.email}
    )
    assert found.status_code == 200, found.text
    assert found.json()["id"] == collaborator.id

    missing = api_client.client.get(
        "/api/v1/auth/users/lookup",
        headers=owner.auth_headers,
        params={"email": api_client.unique_email("qa-nobody")},
    )
    assert missing.status_code in {400, 404}, missing.text


@pytest.mark.gap_revealer
def test_non_shared_user_is_denied_file_metadata_and_download(api_client):
    owner = api_client.register_user("qa-share-private-owner")
    outsider = api_client.register_user("qa-share-private-outsider")
    fileId = uploadFile(api_client, owner)

    metadata = api_client.client.get(f"/api/v1/files/{fileId}", headers=outsider.auth_headers)
    download = api_client.client.get(f"/api/v1/files/{fileId}/download", headers=outsider.auth_headers)
    assert metadata.status_code in {403, 404}, f"outsider read metadata: {metadata.status_code}"
    assert download.status_code in {403, 404}, f"outsider got download URL: {download.status_code}"


@pytest.mark.gap_revealer
def test_non_owner_cannot_grant_or_revoke_shares(api_client):
    owner = api_client.register_user("qa-share-acl-owner")
    collaborator = api_client.register_user("qa-share-acl-collab")
    outsider = api_client.register_user("qa-share-acl-outsider")
    fileId = uploadFile(api_client, owner)
    assert shareFile(api_client, owner, fileId, collaborator, "viewer").status_code == 201

    selfGrant = shareFile(api_client, outsider, fileId, outsider, "editor")
    revokeOther = api_client.client.delete(
        f"/api/v1/files/{fileId}/share/{collaborator.id}", headers=outsider.auth_headers
    )
    outsiderSees = fileId in sharedIds(api_client, outsider)
    collaboratorSees = fileId in sharedIds(api_client, collaborator)

    assert selfGrant.status_code == 403, f"outsider self-granted editor: {selfGrant.status_code}"
    assert revokeOther.status_code == 403, f"outsider revoked a share: {revokeOther.status_code}"
    assert not outsiderSees
    assert collaboratorSees


@pytest.mark.gap_revealer
def test_viewer_cannot_rename_shared_file(api_client):
    owner = api_client.register_user("qa-share-viewer-owner")
    viewer = api_client.register_user("qa-share-viewer")
    fileId = uploadFile(api_client, owner, name="viewer-original.txt")
    assert shareFile(api_client, owner, fileId, viewer, "viewer").status_code == 201

    rename = api_client.client.patch(
        f"/api/v1/files/{fileId}/rename", headers=viewer.auth_headers, json={"name": "viewer-renamed.txt"}
    )
    current = api_client.client.get(f"/api/v1/files/{fileId}", headers=owner.auth_headers).json()
    assert rename.status_code == 403, f"viewer rename returned {rename.status_code}"
    assert current["name"] == "viewer-original.txt"
