"""Tests for comment API endpoints."""

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import make_auth_headers


async def _create_doc(client: AsyncClient, owner_id: uuid.UUID) -> str:
    resp = await client.post(
        "/api/v1/documents/",
        json={"title": "Commented Doc", "content": "", "owner_id": str(owner_id)},
    )
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_add_comment(client: AsyncClient, owner_id: uuid.UUID):
    doc_id = await _create_doc(client, owner_id)

    resp = await client.post(
        f"/api/v1/documents/{doc_id}/comments",
        json={"author_id": str(uuid.uuid4()), "content": "Great document!"},
        headers=make_auth_headers(owner_id),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["content"] == "Great document!"
    assert data["author_id"] == str(owner_id)
    assert data["document_id"] == doc_id


@pytest.mark.asyncio
async def test_add_comment_document_not_found(client: AsyncClient, owner_id: uuid.UUID):
    resp = await client.post(
        f"/api/v1/documents/{uuid.uuid4()}/comments",
        json={"content": "Orphan comment"},
        headers=make_auth_headers(owner_id),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_comments(client: AsyncClient, owner_id: uuid.UUID):
    doc_id = await _create_doc(client, owner_id)
    headers = make_auth_headers(owner_id)

    for i in range(3):
        await client.post(
            f"/api/v1/documents/{doc_id}/comments",
            json={"content": f"Comment {i}"},
            headers=headers,
        )

    resp = await client.get(f"/api/v1/documents/{doc_id}/comments", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 3


@pytest.mark.asyncio
async def test_delete_comment(client: AsyncClient, owner_id: uuid.UUID):
    doc_id = await _create_doc(client, owner_id)
    headers = make_auth_headers(owner_id)

    comment_resp = await client.post(
        f"/api/v1/documents/{doc_id}/comments",
        json={"content": "To delete"},
        headers=headers,
    )
    comment_id = comment_resp.json()["id"]

    resp = await client.delete(
        f"/api/v1/documents/{doc_id}/comments/{comment_id}", headers=headers
    )
    assert resp.status_code == 204

    list_resp = await client.get(f"/api/v1/documents/{doc_id}/comments", headers=headers)
    assert len(list_resp.json()) == 0


@pytest.mark.asyncio
async def test_delete_comment_not_found(client: AsyncClient, owner_id: uuid.UUID):
    doc_id = await _create_doc(client, owner_id)

    resp = await client.delete(
        f"/api/v1/documents/{doc_id}/comments/{uuid.uuid4()}",
        headers=make_auth_headers(owner_id),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_comments_require_identity(client: AsyncClient, owner_id: uuid.UUID):
    doc_id = await _create_doc(client, owner_id)

    assert (await client.get(f"/api/v1/documents/{doc_id}/comments")).status_code == 401
    added = await client.post(
        f"/api/v1/documents/{doc_id}/comments", json={"content": "anon"}
    )
    assert added.status_code == 401


@pytest.mark.asyncio
async def test_other_user_cannot_read_add_or_delete_comments(
    client: AsyncClient, owner_id: uuid.UUID
):
    doc_id = await _create_doc(client, owner_id)
    created = await client.post(
        f"/api/v1/documents/{doc_id}/comments",
        json={"content": "Owner only"},
        headers=make_auth_headers(owner_id),
    )
    comment_id = created.json()["id"]
    intruder = make_auth_headers(uuid.uuid4())

    listed = await client.get(f"/api/v1/documents/{doc_id}/comments", headers=intruder)
    added = await client.post(
        f"/api/v1/documents/{doc_id}/comments",
        json={"author_id": str(owner_id), "content": "forged"},
        headers=intruder,
    )
    deleted = await client.delete(
        f"/api/v1/documents/{doc_id}/comments/{comment_id}", headers=intruder
    )

    assert (listed.status_code, added.status_code, deleted.status_code) == (403, 403, 403)
