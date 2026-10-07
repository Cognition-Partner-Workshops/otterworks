"""Tests for POST /api/v1/documents/{id}/copy."""

import os
import uuid

import jwt
import pytest
from httpx import AsyncClient

TEST_JWT_SECRET = "test-jwt-secret-for-unit-tests-pad32"  # noqa: S105
os.environ.setdefault("JWT_SECRET", TEST_JWT_SECRET)


def _auth(user_id: uuid.UUID) -> dict[str, str]:
    token = jwt.encode({"user_id": str(user_id)}, TEST_JWT_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


async def _create_edited_document(client: AsyncClient, owner_id: uuid.UUID) -> dict:
    create = await client.post(
        "/api/v1/documents/",
        json={"title": "Quarterly plan", "content": "first draft"},
        headers=_auth(owner_id),
    )
    assert create.status_code == 201
    doc_id = create.json()["id"]
    patch = await client.patch(
        f"/api/v1/documents/{doc_id}",
        json={"content": "final draft with more words"},
        headers=_auth(owner_id),
    )
    assert patch.status_code == 200
    assert patch.json()["version"] == 2
    return patch.json()


@pytest.mark.asyncio
async def test_owner_can_copy_document(client: AsyncClient, owner_id: uuid.UUID):
    original = await _create_edited_document(client, owner_id)

    resp = await client.post(f"/api/v1/documents/{original['id']}/copy", headers=_auth(owner_id))

    assert resp.status_code == 201
    copy = resp.json()
    assert copy["id"] != original["id"]
    assert copy["title"] == "Copy of Quarterly plan"
    assert copy["content"] == "final draft with more words"
    assert copy["content_type"] == original["content_type"]
    assert copy["owner_id"] == str(owner_id)
    assert copy["version"] == 1
    assert copy["word_count"] == 5

    fetched = await client.get(f"/api/v1/documents/{copy['id']}", headers=_auth(owner_id))
    assert fetched.status_code == 200
    assert fetched.json() == copy


@pytest.mark.asyncio
async def test_copy_has_single_version_and_original_is_untouched(
    client: AsyncClient, owner_id: uuid.UUID
):
    original = await _create_edited_document(client, owner_id)

    copy = (
        await client.post(f"/api/v1/documents/{original['id']}/copy", headers=_auth(owner_id))
    ).json()

    copy_versions = await client.get(
        f"/api/v1/documents/{copy['id']}/versions", headers=_auth(owner_id)
    )
    assert copy_versions.status_code == 200
    assert [v["version_number"] for v in copy_versions.json()] == [1]
    assert copy_versions.json()[0]["content"] == "final draft with more words"

    original_versions = await client.get(
        f"/api/v1/documents/{original['id']}/versions", headers=_auth(owner_id)
    )
    assert len(original_versions.json()) == 2
    still_original = await client.get(
        f"/api/v1/documents/{original['id']}", headers=_auth(owner_id)
    )
    assert still_original.json()["title"] == "Quarterly plan"
    assert still_original.json()["version"] == 2


@pytest.mark.asyncio
async def test_copy_appears_first_in_callers_list(client: AsyncClient, owner_id: uuid.UUID):
    original = await _create_edited_document(client, owner_id)

    copy = (
        await client.post(f"/api/v1/documents/{original['id']}/copy", headers=_auth(owner_id))
    ).json()

    listing = await client.get("/api/v1/documents/", headers=_auth(owner_id))
    assert listing.status_code == 200
    items = listing.json()["items"]
    assert [item["id"] for item in items] == [copy["id"], original["id"]]


@pytest.mark.asyncio
async def test_stranger_gets_404(client: AsyncClient, owner_id: uuid.UUID):
    original = await _create_edited_document(client, owner_id)
    stranger = uuid.uuid4()

    resp = await client.post(f"/api/v1/documents/{original['id']}/copy", headers=_auth(stranger))

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Document not found"
    stranger_list = await client.get("/api/v1/documents/", headers=_auth(stranger))
    assert stranger_list.json()["total"] == 0


@pytest.mark.asyncio
async def test_missing_document_gets_404(client: AsyncClient, owner_id: uuid.UUID):
    resp = await client.post(f"/api/v1/documents/{uuid.uuid4()}/copy", headers=_auth(owner_id))
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Document not found"


@pytest.mark.asyncio
async def test_deleted_document_gets_404(client: AsyncClient, owner_id: uuid.UUID):
    original = await _create_edited_document(client, owner_id)
    await client.delete(f"/api/v1/documents/{original['id']}", headers=_auth(owner_id))

    resp = await client.post(f"/api/v1/documents/{original['id']}/copy", headers=_auth(owner_id))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_copy_requires_authentication(client: AsyncClient, owner_id: uuid.UUID):
    original = await _create_edited_document(client, owner_id)
    resp = await client.post(f"/api/v1/documents/{original['id']}/copy")
    assert resp.status_code == 401
