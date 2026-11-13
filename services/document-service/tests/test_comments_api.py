"""Tests for comment API endpoints."""

import uuid

import jwt
import pytest
from httpx import AsyncClient

TEST_JWT_SECRET = "test-jwt-secret-for-unit-tests-pad32"  # noqa: S105


@pytest.fixture(autouse=True)
def _jwt_secret(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)


def _auth(user_id: uuid.UUID) -> dict[str, str]:
    token = jwt.encode({"user_id": str(user_id)}, TEST_JWT_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


async def _create_doc(client: AsyncClient, owner_id: uuid.UUID) -> str:
    resp = await client.post(
        "/api/v1/documents/",
        json={"title": "Commented Doc", "content": "", "owner_id": str(owner_id)},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def _add_comment(
    client: AsyncClient, doc_id: str, user_id: uuid.UUID, content: str = "Hi"
) -> dict:
    resp = await client.post(
        f"/api/v1/documents/{doc_id}/comments",
        json={"content": content},
        headers=_auth(user_id),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_add_comment(client: AsyncClient, owner_id: uuid.UUID):
    doc_id = await _create_doc(client, owner_id)

    resp = await client.post(
        f"/api/v1/documents/{doc_id}/comments",
        json={"content": "Great document!"},
        headers=_auth(owner_id),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["content"] == "Great document!"
    assert data["author_id"] == str(owner_id)
    assert data["document_id"] == doc_id


@pytest.mark.asyncio
async def test_add_comment_ignores_body_author_id(
    client: AsyncClient, owner_id: uuid.UUID
):
    doc_id = await _create_doc(client, owner_id)
    spoofed = uuid.uuid4()

    resp = await client.post(
        f"/api/v1/documents/{doc_id}/comments",
        json={"author_id": str(spoofed), "content": "Forged?"},
        headers=_auth(owner_id),
    )
    assert resp.status_code == 201
    assert resp.json()["author_id"] == str(owner_id)


@pytest.mark.asyncio
async def test_add_comment_document_not_found(client: AsyncClient):
    resp = await client.post(
        f"/api/v1/documents/{uuid.uuid4()}/comments",
        json={"content": "Orphan comment"},
        headers=_auth(uuid.uuid4()),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_comments(client: AsyncClient, owner_id: uuid.UUID):
    doc_id = await _create_doc(client, owner_id)
    for i in range(3):
        await _add_comment(client, doc_id, owner_id, f"Comment {i}")

    resp = await client.get(
        f"/api/v1/documents/{doc_id}/comments", headers=_auth(owner_id)
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 3


@pytest.mark.asyncio
async def test_list_comments_document_not_found(client: AsyncClient):
    resp = await client.get(
        f"/api/v1/documents/{uuid.uuid4()}/comments", headers=_auth(uuid.uuid4())
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_comment(client: AsyncClient, owner_id: uuid.UUID):
    doc_id = await _create_doc(client, owner_id)
    comment = await _add_comment(client, doc_id, owner_id, "To delete")

    resp = await client.delete(
        f"/api/v1/documents/{doc_id}/comments/{comment['id']}",
        headers=_auth(owner_id),
    )
    assert resp.status_code == 204

    list_resp = await client.get(
        f"/api/v1/documents/{doc_id}/comments", headers=_auth(owner_id)
    )
    assert len(list_resp.json()) == 0


@pytest.mark.asyncio
async def test_delete_comment_not_found(client: AsyncClient, owner_id: uuid.UUID):
    doc_id = await _create_doc(client, owner_id)

    resp = await client.delete(
        f"/api/v1/documents/{doc_id}/comments/{uuid.uuid4()}",
        headers=_auth(owner_id),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["GET", "POST", "DELETE"])
async def test_comment_routes_require_authentication(
    client: AsyncClient, owner_id: uuid.UUID, method: str
):
    doc_id = await _create_doc(client, owner_id)
    comment = await _add_comment(client, doc_id, owner_id)
    url = f"/api/v1/documents/{doc_id}/comments"
    if method == "DELETE":
        url = f"{url}/{comment['id']}"
    kwargs = {"json": {"content": "x"}} if method == "POST" else {}

    resp = await client.request(method, url, **kwargs)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_other_user_cannot_list_comments(
    client: AsyncClient, owner_id: uuid.UUID
):
    doc_id = await _create_doc(client, owner_id)
    await _add_comment(client, doc_id, owner_id, "Confidential")

    resp = await client.get(
        f"/api/v1/documents/{doc_id}/comments", headers=_auth(uuid.uuid4())
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_other_user_cannot_add_comment(
    client: AsyncClient, owner_id: uuid.UUID
):
    doc_id = await _create_doc(client, owner_id)

    resp = await client.post(
        f"/api/v1/documents/{doc_id}/comments",
        json={"author_id": str(owner_id), "content": "Forged"},
        headers=_auth(uuid.uuid4()),
    )
    assert resp.status_code == 403

    list_resp = await client.get(
        f"/api/v1/documents/{doc_id}/comments", headers=_auth(owner_id)
    )
    assert list_resp.json() == []


@pytest.mark.asyncio
async def test_other_user_cannot_delete_comment(
    client: AsyncClient, owner_id: uuid.UUID
):
    doc_id = await _create_doc(client, owner_id)
    comment = await _add_comment(client, doc_id, owner_id, "Keep me")

    resp = await client.delete(
        f"/api/v1/documents/{doc_id}/comments/{comment['id']}",
        headers=_auth(uuid.uuid4()),
    )
    assert resp.status_code == 403

    list_resp = await client.get(
        f"/api/v1/documents/{doc_id}/comments", headers=_auth(owner_id)
    )
    assert [c["id"] for c in list_resp.json()] == [comment["id"]]
