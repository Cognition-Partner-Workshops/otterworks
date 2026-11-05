"""Tests for comment API endpoints."""

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_add_comment(authed_client: AsyncClient, owner_id: uuid.UUID):
    create_resp = await authed_client.post(
        "/api/v1/documents/",
        json={"title": "Commented Doc", "content": "", "owner_id": str(owner_id)},
    )
    doc_id = create_resp.json()["id"]
    author_id = str(uuid.uuid4())

    resp = await authed_client.post(
        f"/api/v1/documents/{doc_id}/comments",
        json={"author_id": author_id, "content": "Great document!"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["content"] == "Great document!"
    assert data["author_id"] == author_id
    assert data["document_id"] == doc_id


@pytest.mark.asyncio
async def test_add_comment_document_not_found(client: AsyncClient):
    resp = await client.post(
        f"/api/v1/documents/{uuid.uuid4()}/comments",
        json={"author_id": str(uuid.uuid4()), "content": "Orphan comment"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_comments(authed_client: AsyncClient, owner_id: uuid.UUID):
    create_resp = await authed_client.post(
        "/api/v1/documents/",
        json={"title": "Doc", "content": "", "owner_id": str(owner_id)},
    )
    doc_id = create_resp.json()["id"]

    for i in range(3):
        await authed_client.post(
            f"/api/v1/documents/{doc_id}/comments",
            json={"author_id": str(uuid.uuid4()), "content": f"Comment {i}"},
        )

    resp = await authed_client.get(f"/api/v1/documents/{doc_id}/comments")
    assert resp.status_code == 200
    assert len(resp.json()) == 3


@pytest.mark.asyncio
async def test_delete_comment(authed_client: AsyncClient, owner_id: uuid.UUID):
    create_resp = await authed_client.post(
        "/api/v1/documents/",
        json={"title": "Doc", "content": "", "owner_id": str(owner_id)},
    )
    doc_id = create_resp.json()["id"]

    comment_resp = await authed_client.post(
        f"/api/v1/documents/{doc_id}/comments",
        json={"author_id": str(uuid.uuid4()), "content": "To delete"},
    )
    comment_id = comment_resp.json()["id"]

    resp = await authed_client.delete(f"/api/v1/documents/{doc_id}/comments/{comment_id}")
    assert resp.status_code == 204

    list_resp = await authed_client.get(f"/api/v1/documents/{doc_id}/comments")
    assert len(list_resp.json()) == 0


@pytest.mark.asyncio
async def test_delete_comment_not_found(authed_client: AsyncClient, owner_id: uuid.UUID):
    create_resp = await authed_client.post(
        "/api/v1/documents/",
        json={"title": "Doc", "content": "", "owner_id": str(owner_id)},
    )
    doc_id = create_resp.json()["id"]

    resp = await authed_client.delete(
        f"/api/v1/documents/{doc_id}/comments/{uuid.uuid4()}"
    )
    assert resp.status_code == 404
