"""Tests for comment API endpoints."""

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import auth_header


@pytest.mark.asyncio
async def test_add_comment(client: AsyncClient, owner_id: uuid.UUID):
    create_resp = await client.post(
        "/api/v1/documents/",
        json={"title": "Commented Doc", "content": "", "owner_id": str(owner_id)},
        headers=auth_header(owner_id),
    )
    doc_id = create_resp.json()["id"]
    author_id = str(owner_id)

    resp = await client.post(
        f"/api/v1/documents/{doc_id}/comments",
        json={"author_id": author_id, "content": "Great document!"},
        headers=auth_header(owner_id),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["content"] == "Great document!"
    assert data["author_id"] == author_id
    assert data["document_id"] == doc_id


@pytest.mark.asyncio
async def test_add_comment_document_not_found(client: AsyncClient, owner_id: uuid.UUID):
    resp = await client.post(
        f"/api/v1/documents/{uuid.uuid4()}/comments",
        json={"content": "Orphan comment"},
        headers=auth_header(owner_id),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_comments(client: AsyncClient, owner_id: uuid.UUID):
    create_resp = await client.post(
        "/api/v1/documents/",
        json={"title": "Doc", "content": "", "owner_id": str(owner_id)},
        headers=auth_header(owner_id),
    )
    doc_id = create_resp.json()["id"]

    for i in range(3):
        await client.post(
            f"/api/v1/documents/{doc_id}/comments",
            json={"content": f"Comment {i}"},
            headers=auth_header(owner_id),
        )

    resp = await client.get(f"/api/v1/documents/{doc_id}/comments", headers=auth_header(owner_id))
    assert resp.status_code == 200
    assert len(resp.json()) == 3


@pytest.mark.asyncio
async def test_delete_comment(client: AsyncClient, owner_id: uuid.UUID):
    create_resp = await client.post(
        "/api/v1/documents/",
        json={"title": "Doc", "content": "", "owner_id": str(owner_id)},
        headers=auth_header(owner_id),
    )
    doc_id = create_resp.json()["id"]

    comment_resp = await client.post(
        f"/api/v1/documents/{doc_id}/comments",
        json={"content": "To delete"},
        headers=auth_header(owner_id),
    )
    comment_id = comment_resp.json()["id"]

    resp = await client.delete(
        f"/api/v1/documents/{doc_id}/comments/{comment_id}", headers=auth_header(owner_id)
    )
    assert resp.status_code == 204

    list_resp = await client.get(
        f"/api/v1/documents/{doc_id}/comments", headers=auth_header(owner_id)
    )
    assert len(list_resp.json()) == 0


@pytest.mark.asyncio
async def test_delete_comment_not_found(client: AsyncClient, owner_id: uuid.UUID):
    create_resp = await client.post(
        "/api/v1/documents/",
        json={"title": "Doc", "content": "", "owner_id": str(owner_id)},
        headers=auth_header(owner_id),
    )
    doc_id = create_resp.json()["id"]

    resp = await client.delete(
        f"/api/v1/documents/{doc_id}/comments/{uuid.uuid4()}", headers=auth_header(owner_id)
    )
    assert resp.status_code == 404
