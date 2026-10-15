"""Black-box sharing flows: file shares (viewer/editor, shared-with-me, revoke) and
document share links, including denial for users the item was never shared with."""

import hashlib

import pytest


pytestmark = pytest.mark.api_flow

SHARE_TOKEN_LENGTH = 16


def _upload(api_client, owner, name="shared.txt", body=b"sharing flow payload"):
    response = api_client.client.post(
        "/api/v1/files/upload",
        headers=owner.auth_headers,
        files={"file": (name, body, "text/plain")},
    )
    assert response.status_code == 201, response.text
    file_id = response.json()["file"]["id"]
    api_client.created_files.append(file_id)
    return file_id


def _share(api_client, actor, file_id, target, permission="viewer", shared_by=None):
    return api_client.client.post(
        f"/api/v1/files/{file_id}/share",
        headers=actor.auth_headers,
        json={
            "shared_with": target.id,
            "permission": permission,
            "shared_by": shared_by or actor.id,
        },
    )


def _shared_ids(api_client, user):
    response = api_client.client.get("/api/v1/files/shared", headers=user.auth_headers)
    assert response.status_code == 200, response.text
    return {item["id"]: item for item in response.json()["files"]}


def _mint_link(api_client, user, document_id):
    return api_client.client.post(
        f"/api/v1/documents/{document_id}/share", headers=user.auth_headers
    )


# ── File shares ───────────────────────────────────────────────────────


def test_share_file_with_viewer_appears_in_shared_with_me(api_client):
    owner = api_client.register_user("share-owner")
    viewer = api_client.register_user("share-viewer")
    file_id = _upload(api_client, owner)

    response = _share(api_client, owner, file_id, viewer, "viewer")
    api_client.assert_gateway_route_available(response, "/api/v1/files/{id}/share")
    assert response.status_code == 201, response.text
    share = response.json()["share"]
    assert share["file_id"] == file_id
    assert share["shared_with"] == viewer.id
    assert share["shared_by"] == owner.id
    assert share["permission"] == "viewer"

    shared = _shared_ids(api_client, viewer)
    assert file_id in shared
    assert shared[file_id]["owner_id"] == owner.id


def test_share_with_editor_permission(api_client):
    owner = api_client.register_user("share-owner")
    editor = api_client.register_user("share-editor")
    file_id = _upload(api_client, owner)

    response = _share(api_client, owner, file_id, editor, "editor")
    assert response.status_code == 201, response.text
    assert response.json()["share"]["permission"] == "editor"
    assert file_id in _shared_ids(api_client, editor)


def test_reshare_upgrades_permission_without_duplicating(api_client):
    owner = api_client.register_user("share-owner")
    collaborator = api_client.register_user("share-collab")
    file_id = _upload(api_client, owner)

    first = _share(api_client, owner, file_id, collaborator, "viewer")
    assert first.status_code == 201, first.text
    upgrade = _share(api_client, owner, file_id, collaborator, "editor")
    assert upgrade.status_code == 200, upgrade.text
    assert upgrade.json()["share"]["permission"] == "editor"
    assert upgrade.json()["share"]["id"] == first.json()["share"]["id"]

    shared = api_client.client.get("/api/v1/files/shared", headers=collaborator.auth_headers)
    assert [f["id"] for f in shared.json()["files"]].count(file_id) == 1


def test_share_rejects_unknown_permission(api_client):
    owner = api_client.register_user("share-owner")
    collaborator = api_client.register_user("share-collab")
    file_id = _upload(api_client, owner)

    response = _share(api_client, owner, file_id, collaborator, "owner")
    assert response.status_code in (400, 422), response.text


def test_share_missing_file_is_404(api_client):
    owner = api_client.register_user("share-owner")
    collaborator = api_client.register_user("share-collab")
    response = _share(
        api_client, owner, "00000000-0000-4000-8000-000000000000", collaborator
    )
    assert response.status_code == 404, response.text


def test_sharing_endpoints_require_authentication(api_client):
    owner = api_client.register_user("share-owner")
    collaborator = api_client.register_user("share-collab")
    file_id = _upload(api_client, owner)

    share = api_client.client.post(
        f"/api/v1/files/{file_id}/share",
        json={"shared_with": collaborator.id, "permission": "viewer", "shared_by": owner.id},
    )
    assert share.status_code == 401
    listing = api_client.client.get("/api/v1/files/shared")
    assert listing.status_code == 401


def test_unshared_user_does_not_see_file_in_shared_with_me(api_client):
    owner = api_client.register_user("share-owner")
    collaborator = api_client.register_user("share-collab")
    stranger = api_client.register_user("share-stranger")
    file_id = _upload(api_client, owner)
    assert _share(api_client, owner, file_id, collaborator).status_code == 201

    assert file_id not in _shared_ids(api_client, stranger)


def test_revoke_share_removes_access_from_shared_with_me(api_client):
    owner = api_client.register_user("share-owner")
    collaborator = api_client.register_user("share-collab")
    file_id = _upload(api_client, owner)
    assert _share(api_client, owner, file_id, collaborator).status_code == 201
    assert file_id in _shared_ids(api_client, collaborator)

    revoke = api_client.client.delete(
        f"/api/v1/files/{file_id}/share/{collaborator.id}", headers=owner.auth_headers
    )
    assert revoke.status_code == 204, revoke.text
    assert file_id not in _shared_ids(api_client, collaborator)

    again = api_client.client.delete(
        f"/api/v1/files/{file_id}/share/{collaborator.id}", headers=owner.auth_headers
    )
    assert again.status_code == 404, again.text


@pytest.mark.gap_revealer
def test_unshared_user_is_denied_file_metadata_and_download(api_client):
    """[REAL] file-service has no object-level authz on GET /files/{id} and /download
    (security/dast/attack-surface.yaml: other owners' object ids must return 403/404)."""
    owner = api_client.register_user("share-owner")
    stranger = api_client.register_user("share-stranger")
    file_id = _upload(api_client, owner, body=b"owner-only content")

    metadata = api_client.client.get(f"/api/v1/files/{file_id}", headers=stranger.auth_headers)
    assert metadata.status_code in (403, 404), metadata.text
    download = api_client.client.get(
        f"/api/v1/files/{file_id}/download", headers=stranger.auth_headers
    )
    assert download.status_code in (403, 404), download.text


@pytest.mark.gap_revealer
def test_non_owner_cannot_share_someone_elses_file(api_client):
    """[REAL] POST /files/{id}/share never checks the caller owns the file and trusts
    the body's shared_by, so any user can grant themselves access."""
    owner = api_client.register_user("share-owner")
    stranger = api_client.register_user("share-stranger")
    file_id = _upload(api_client, owner)

    response = _share(api_client, stranger, file_id, stranger, "editor", shared_by=owner.id)
    assert response.status_code in (403, 404), response.text
    assert file_id not in _shared_ids(api_client, stranger)


@pytest.mark.gap_revealer
def test_non_owner_cannot_revoke_someone_elses_share(api_client):
    """[REAL] DELETE /files/{id}/share/{user} never checks the caller owns the file."""
    owner = api_client.register_user("share-owner")
    collaborator = api_client.register_user("share-collab")
    stranger = api_client.register_user("share-stranger")
    file_id = _upload(api_client, owner)
    assert _share(api_client, owner, file_id, collaborator).status_code == 201

    revoke = api_client.client.delete(
        f"/api/v1/files/{file_id}/share/{collaborator.id}", headers=stranger.auth_headers
    )
    assert revoke.status_code in (403, 404), revoke.text
    assert file_id in _shared_ids(api_client, collaborator)


# ── Document share links ─────────────────────────────────────────────


def test_document_share_link_opens_for_another_user(api_client):
    owner = api_client.register_user("doc-share-owner")
    reader = api_client.register_user("doc-share-reader")
    document = api_client.create_document(owner, "Shared Doc", "link-shared body")

    mint = _mint_link(api_client, owner, document["id"])
    api_client.assert_gateway_route_available(mint, "/api/v1/documents/{id}/share")
    assert mint.status_code == 200, mint.text
    token = mint.json()["token"]
    assert mint.json()["document_id"] == document["id"]
    assert len(token) == SHARE_TOKEN_LENGTH

    opened = api_client.client.get(
        "/api/v1/documents/shared",
        headers=reader.auth_headers,
        params={"document_id": document["id"], "token": token},
    )
    assert opened.status_code == 200, opened.text
    assert opened.json()["title"] == "Shared Doc"
    assert opened.json()["content"] == "link-shared body"


def test_non_owner_cannot_mint_document_share_link(api_client):
    owner = api_client.register_user("doc-share-owner")
    stranger = api_client.register_user("doc-share-stranger")
    document = api_client.create_document(owner, "Private Doc", "private")

    response = _mint_link(api_client, stranger, document["id"])
    assert response.status_code == 403, response.text


def test_unshared_user_is_denied_direct_document_access(api_client):
    owner = api_client.register_user("doc-share-owner")
    stranger = api_client.register_user("doc-share-stranger")
    document = api_client.create_document(owner, "Private Doc", "private")

    response = api_client.client.get(
        f"/api/v1/documents/{document['id']}", headers=stranger.auth_headers
    )
    assert response.status_code in (403, 404), response.text


def test_document_share_link_rejects_wrong_and_cross_document_tokens(api_client):
    owner = api_client.register_user("doc-share-owner")
    reader = api_client.register_user("doc-share-reader")
    doc_a = api_client.create_document(owner, "Doc A", "a")
    doc_b = api_client.create_document(owner, "Doc B", "b")
    token_a = _mint_link(api_client, owner, doc_a["id"]).json()["token"]

    for doc_id, token in ((doc_a["id"], "0" * SHARE_TOKEN_LENGTH), (doc_b["id"], token_a)):
        response = api_client.client.get(
            "/api/v1/documents/shared",
            headers=reader.auth_headers,
            params={"document_id": doc_id, "token": token},
        )
        assert response.status_code == 403, response.text


@pytest.mark.xfail(
    strict=True,
    reason="[PLANTED] OW-SEC-403 / DAST-SHARE-TOKEN-FORGERY: share tokens are MD5 over a "
    "source-visible default salt, so anyone can forge a link offline.",
)
def test_document_share_token_cannot_be_forged_offline(api_client):
    owner = api_client.register_user("doc-share-owner")
    attacker = api_client.register_user("doc-share-attacker")
    document = api_client.create_document(owner, "Never Shared", "confidential")

    forged = hashlib.md5(f"{document['id']}:otterworks-share".encode()).hexdigest()  # noqa: S324
    response = api_client.client.get(
        "/api/v1/documents/shared",
        headers=attacker.auth_headers,
        params={"document_id": document["id"], "token": forged[:SHARE_TOKEN_LENGTH]},
    )
    assert response.status_code == 403, response.text
