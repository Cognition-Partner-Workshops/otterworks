"""Sharing area: file shares, permission levels, document share links, shared-with-me and trash."""

import hashlib

import pytest

pytestmark = pytest.mark.api_flow


def _upload(api_client, user, name="shared.txt", body=b"shared body"):
    response = api_client.client.post(
        "/api/v1/files/upload",
        headers=user.auth_headers,
        files={"file": (name, body, "text/plain")},
    )
    assert response.status_code == 201, response.text
    file_id = response.json()["file"]["id"]
    api_client.created_files.append(file_id)
    return file_id


def _share(api_client, actor, file_id, recipient_id, permission="viewer", shared_by=None):
    return api_client.client.post(
        f"/api/v1/files/{file_id}/share",
        headers=actor.auth_headers,
        json={
            "shared_with": recipient_id,
            "permission": permission,
            "shared_by": shared_by or actor.id,
        },
    )


def _shared_ids(api_client, user):
    response = api_client.client.get("/api/v1/files/shared", headers=user.auth_headers)
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()["files"]]


def _trash_ids(api_client, user):
    response = api_client.client.get("/api/v1/files/trash", headers=user.auth_headers)
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()["files"]]


@pytest.fixture
def owner_and_friend(api_client):
    return api_client.register_user("share-owner"), api_client.register_user("share-friend")


def test_share_file_appears_in_recipients_shared_with_me(api_client, owner_and_friend):
    owner, friend = owner_and_friend
    file_id = _upload(api_client, owner)
    assert file_id not in _shared_ids(api_client, friend)

    response = _share(api_client, owner, file_id, friend.id)
    assert response.status_code == 201, response.text
    share = response.json()["share"]
    assert share["shared_with"] == friend.id
    assert share["shared_by"] == owner.id
    assert share["permission"] == "viewer"

    assert file_id in _shared_ids(api_client, friend)
    assert file_id not in _shared_ids(api_client, owner)

    detail = api_client.client.get(f"/api/v1/files/{file_id}", headers=owner.auth_headers)
    assert detail.status_code == 200, detail.text
    assert [s["shared_with"] for s in detail.json()["shared_with"]] == [friend.id]


def test_recipient_lookup_by_email_resolves_user_id(api_client, owner_and_friend):
    owner, friend = owner_and_friend
    response = api_client.client.get(
        "/api/v1/auth/users/lookup", params={"email": friend.email}, headers=owner.auth_headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["id"] == friend.id


def test_resharing_updates_permission_level_without_duplicates(api_client, owner_and_friend):
    owner, friend = owner_and_friend
    file_id = _upload(api_client, owner)
    first = _share(api_client, owner, file_id, friend.id, "viewer").json()["share"]

    again = _share(api_client, owner, file_id, friend.id, "viewer")
    assert again.status_code == 200, again.text
    assert again.json()["share"]["id"] == first["id"]

    upgraded = _share(api_client, owner, file_id, friend.id, "editor")
    assert upgraded.status_code == 200, upgraded.text
    assert upgraded.json()["share"]["id"] == first["id"]
    assert upgraded.json()["share"]["permission"] == "editor"

    detail = api_client.client.get(f"/api/v1/files/{file_id}", headers=owner.auth_headers).json()
    assert [(s["shared_with"], s["permission"]) for s in detail["shared_with"]] == [
        (friend.id, "editor")
    ]
    assert _shared_ids(api_client, friend).count(file_id) == 1


@pytest.mark.parametrize("permission", ["owner", "admin", "VIEWER", ""])
def test_unknown_permission_level_is_rejected(api_client, owner_and_friend, permission):
    owner, friend = owner_and_friend
    file_id = _upload(api_client, owner)
    response = _share(api_client, owner, file_id, friend.id, permission)
    assert response.status_code == 400, response.text


def test_share_validation_errors(api_client, owner_and_friend):
    owner, friend = owner_and_friend
    missing = _share(api_client, owner, "00000000-0000-4000-8000-000000000000", friend.id)
    assert missing.status_code == 404
    assert missing.json()["error"] == "file_not_found"

    file_id = _upload(api_client, owner)
    unauthenticated = api_client.client.post(
        f"/api/v1/files/{file_id}/share",
        json={"shared_with": friend.id, "permission": "viewer", "shared_by": owner.id},
    )
    assert unauthenticated.status_code == 401

    no_share = api_client.client.delete(
        f"/api/v1/files/{file_id}/share/{friend.id}", headers=owner.auth_headers
    )
    assert no_share.status_code == 404
    assert no_share.json()["error"] == "share_not_found"


def test_revoke_share_removes_file_from_shared_with_me(api_client, owner_and_friend):
    owner, friend = owner_and_friend
    file_id = _upload(api_client, owner)
    assert _share(api_client, owner, file_id, friend.id).status_code == 201
    assert file_id in _shared_ids(api_client, friend)

    revoke = api_client.client.delete(
        f"/api/v1/files/{file_id}/share/{friend.id}", headers=owner.auth_headers
    )
    assert revoke.status_code == 204, revoke.text
    assert file_id not in _shared_ids(api_client, friend)
    detail = api_client.client.get(f"/api/v1/files/{file_id}", headers=owner.auth_headers).json()
    assert detail["shared_with"] == []


def test_trashing_shared_file_hides_it_from_recipient_and_restore_brings_it_back(
    api_client, owner_and_friend
):
    owner, friend = owner_and_friend
    file_id = _upload(api_client, owner)
    assert _share(api_client, owner, file_id, friend.id).status_code == 201

    trashed = api_client.client.post(f"/api/v1/files/{file_id}/trash", headers=owner.auth_headers)
    assert trashed.status_code == 200, trashed.text
    assert trashed.json()["is_trashed"] is True

    assert file_id not in _shared_ids(api_client, friend)
    assert file_id in _trash_ids(api_client, owner)
    assert file_id not in _trash_ids(api_client, friend)

    restored = api_client.client.post(f"/api/v1/files/{file_id}/restore", headers=owner.auth_headers)
    assert restored.status_code == 200, restored.text
    assert file_id in _shared_ids(api_client, friend)
    assert file_id not in _trash_ids(api_client, owner)


def test_permanently_deleted_shared_file_leaves_shared_with_me(api_client, owner_and_friend):
    owner, friend = owner_and_friend
    file_id = _upload(api_client, owner)
    assert _share(api_client, owner, file_id, friend.id).status_code == 201
    api_client.client.post(f"/api/v1/files/{file_id}/trash", headers=owner.auth_headers)
    deleted = api_client.client.delete(f"/api/v1/files/{file_id}", headers=owner.auth_headers)
    assert deleted.status_code == 204, deleted.text
    api_client.created_files.remove(file_id)
    assert file_id not in _shared_ids(api_client, friend)


def test_document_share_link_create_and_open(api_client, owner_and_friend):
    owner, friend = owner_and_friend
    document = api_client.create_document(owner, f"Shared doc {api_client.run_id}", "link body")

    minted = api_client.client.post(
        f"/api/v1/documents/{document['id']}/share", headers=owner.auth_headers
    )
    assert minted.status_code == 200, minted.text
    token = minted.json()["token"]
    assert minted.json()["document_id"] == document["id"]
    assert minted.json() == api_client.client.post(
        f"/api/v1/documents/{document['id']}/share", headers=owner.auth_headers
    ).json()

    direct = api_client.client.get(f"/api/v1/documents/{document['id']}", headers=friend.auth_headers)
    assert direct.status_code == 403

    opened = api_client.client.get(
        "/api/v1/documents/shared",
        params={"document_id": document["id"], "token": token},
        headers=friend.auth_headers,
    )
    assert opened.status_code == 200, opened.text
    assert opened.json()["content"] == "link body"

    wrong = api_client.client.get(
        "/api/v1/documents/shared",
        params={"document_id": document["id"], "token": "0" * len(token)},
        headers=friend.auth_headers,
    )
    assert wrong.status_code == 403


def test_only_owner_can_mint_document_share_link(api_client, owner_and_friend):
    owner, friend = owner_and_friend
    document = api_client.create_document(owner, "Owner only", "body")
    response = api_client.client.post(
        f"/api/v1/documents/{document['id']}/share", headers=friend.auth_headers
    )
    assert response.status_code == 403


def test_share_link_stops_working_after_document_is_deleted(api_client, owner_and_friend):
    owner, friend = owner_and_friend
    document = api_client.create_document(owner, "Delete me", "body")
    token = api_client.client.post(
        f"/api/v1/documents/{document['id']}/share", headers=owner.auth_headers
    ).json()["token"]
    assert api_client.client.delete(
        f"/api/v1/documents/{document['id']}", headers=owner.auth_headers
    ).status_code == 204
    api_client.created_documents.remove(document["id"])
    opened = api_client.client.get(
        "/api/v1/documents/shared",
        params={"document_id": document["id"], "token": token},
        headers=friend.auth_headers,
    )
    assert opened.status_code == 404


# ── Known defects: expected failures so the suite stays green ──────────────


@pytest.mark.gap_revealer
@pytest.mark.xfail(strict=True, reason="[REAL] file-service share_file trusts body shared_by and never checks ownership")
def test_non_owner_cannot_share_someone_elses_file(api_client, owner_and_friend):
    owner, _ = owner_and_friend
    intruder = api_client.register_user("share-intruder")
    file_id = _upload(api_client, owner)
    response = _share(api_client, intruder, file_id, intruder.id, "editor", shared_by=owner.id)
    assert response.status_code in {403, 404}, response.text


@pytest.mark.gap_revealer
@pytest.mark.xfail(strict=True, reason="[REAL] share records the client-supplied shared_by instead of the caller")
def test_share_records_authenticated_caller_as_sharer(api_client, owner_and_friend):
    owner, friend = owner_and_friend
    file_id = _upload(api_client, owner)
    spoofed = "00000000-0000-4000-8000-0000000000aa"
    response = _share(api_client, owner, file_id, friend.id, shared_by=spoofed)
    assert response.status_code == 201, response.text
    assert response.json()["share"]["shared_by"] == owner.id


@pytest.mark.gap_revealer
@pytest.mark.xfail(strict=True, reason="[REAL] remove_share has no authz: any user can revoke anyone's access")
def test_non_owner_cannot_revoke_a_share(api_client, owner_and_friend):
    owner, friend = owner_and_friend
    intruder = api_client.register_user("share-revoker")
    file_id = _upload(api_client, owner)
    assert _share(api_client, owner, file_id, friend.id).status_code == 201
    response = api_client.client.delete(
        f"/api/v1/files/{file_id}/share/{friend.id}", headers=intruder.auth_headers
    )
    assert response.status_code in {403, 404}, response.text


@pytest.mark.gap_revealer
@pytest.mark.xfail(strict=True, reason="[REAL] viewer permission is not enforced: a viewer can trash the owner's file")
def test_viewer_cannot_trash_shared_file(api_client, owner_and_friend):
    owner, friend = owner_and_friend
    file_id = _upload(api_client, owner)
    assert _share(api_client, owner, file_id, friend.id, "viewer").status_code == 201
    response = api_client.client.post(f"/api/v1/files/{file_id}/trash", headers=friend.auth_headers)
    api_client.client.post(f"/api/v1/files/{file_id}/restore", headers=owner.auth_headers)
    assert response.status_code == 403, response.text


@pytest.mark.gap_revealer
@pytest.mark.xfail(strict=True, reason="[REAL] share accepts recipients that are not registered users, and the owner themself")
def test_share_rejects_unknown_or_self_recipient(api_client, owner_and_friend):
    owner, _ = owner_and_friend
    file_id = _upload(api_client, owner)
    unknown = _share(api_client, owner, file_id, "00000000-0000-4000-8000-0000000000bb")
    self_share = _share(api_client, owner, file_id, owner.id)
    assert unknown.status_code in {400, 404, 422}, unknown.text
    assert self_share.status_code in {400, 422}, self_share.text


@pytest.mark.gap_revealer
@pytest.mark.xfail(strict=True, reason="[REAL] SHARE_LINK_SALT is never set, so share tokens are forgeable from the default salt (MD5 itself is planted OW-SEC-403)")
def test_share_link_token_is_not_forgeable_from_default_salt(api_client, owner_and_friend):
    owner, friend = owner_and_friend
    document = api_client.create_document(owner, "Forge target", "private body")
    # Reproduces the attacker's derivation from the source-visible default salt.
    forged = hashlib.md5(f"{document['id']}:otterworks-share".encode()).hexdigest()[:16]  # nosemgrep
    opened = api_client.client.get(
        "/api/v1/documents/shared",
        params={"document_id": document["id"], "token": forged},
        headers=friend.auth_headers,
    )
    assert opened.status_code == 403, opened.text


@pytest.mark.gap_revealer
@pytest.mark.xfail(strict=True, reason="[REAL] share links are stateless; there is no revoke endpoint")
def test_document_share_link_can_be_revoked(api_client, owner_and_friend):
    owner, friend = owner_and_friend
    document = api_client.create_document(owner, "Revoke me", "body")
    token = api_client.client.post(
        f"/api/v1/documents/{document['id']}/share", headers=owner.auth_headers
    ).json()["token"]
    revoke = api_client.client.delete(
        f"/api/v1/documents/{document['id']}/share", headers=owner.auth_headers
    )
    assert revoke.status_code in {200, 204}, revoke.text
    opened = api_client.client.get(
        "/api/v1/documents/shared",
        params={"document_id": document["id"], "token": token},
        headers=friend.auth_headers,
    )
    assert opened.status_code in {403, 404}


@pytest.mark.gap_revealer
@pytest.mark.xfail(strict=True, reason="[REAL] web 'Invite' posts {users} to /documents/{id}/share, which ignores the body and grants no access")
def test_document_invite_grants_recipient_access(api_client, owner_and_friend):
    owner, friend = owner_and_friend
    document = api_client.create_document(owner, "Invite target", "body")
    invite = api_client.client.post(
        f"/api/v1/documents/{document['id']}/share",
        headers=owner.auth_headers,
        json={"users": [{"userId": "", "name": "", "email": friend.email, "permission": "edit"}]},
    )
    assert invite.status_code == 200, invite.text
    direct = api_client.client.get(f"/api/v1/documents/{document['id']}", headers=friend.auth_headers)
    assert direct.status_code == 200, direct.text


@pytest.mark.gap_revealer
@pytest.mark.xfail(strict=True, reason="[REAL] file list responses omit shared_with, so the Files-page share dialog never shows existing collaborators")
def test_file_list_includes_share_recipients(api_client, owner_and_friend):
    owner, friend = owner_and_friend
    file_id = _upload(api_client, owner)
    assert _share(api_client, owner, file_id, friend.id).status_code == 201
    listing = api_client.client.get(
        "/api/v1/files", headers=owner.auth_headers, params={"page": 1, "page_size": 100}
    )
    assert listing.status_code == 200, listing.text
    item = next(f for f in listing.json()["files"] if f["id"] == file_id)
    assert [s["shared_with"] for s in item.get("shared_with", [])] == [friend.id]
