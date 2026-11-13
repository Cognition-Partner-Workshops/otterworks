"""List and search must only return the authenticated caller's documents."""

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


@pytest.fixture
def alice() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mallory() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
async def alice_doc(client: AsyncClient, alice: uuid.UUID) -> dict:
    resp = await client.post(
        "/api/v1/documents/",
        json={"title": "Alice private plan", "content": "secret roadmap"},
        headers=_auth(alice),
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_search_excludes_other_users_documents(
    client: AsyncClient, alice: uuid.UUID, mallory: uuid.UUID, alice_doc: dict
):
    resp = await client.get("/api/v1/documents/search", params={"q": "e"}, headers=_auth(mallory))
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
    assert resp.json()["items"] == []


@pytest.mark.asyncio
async def test_search_returns_callers_own_documents(
    client: AsyncClient, alice: uuid.UUID, alice_doc: dict
):
    resp = await client.get(
        "/api/v1/documents/search", params={"q": "roadmap"}, headers=_auth(alice)
    )
    assert resp.status_code == 200
    assert [item["id"] for item in resp.json()["items"]] == [alice_doc["id"]]


@pytest.mark.asyncio
async def test_search_requires_authentication(client: AsyncClient, alice_doc: dict):
    resp = await client.get("/api/v1/documents/search", params={"q": "e"})
    assert resp.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/api/v1/documents/", "/api/v1/documents"])
@pytest.mark.parametrize("extra", [{}, {"title": "plan"}, {"sort": "title"}])
async def test_list_rejects_other_users_owner_id(
    client: AsyncClient,
    alice: uuid.UUID,
    mallory: uuid.UUID,
    alice_doc: dict,
    path: str,
    extra: dict,
):
    resp = await client.get(path, params={"owner_id": str(alice), **extra}, headers=_auth(mallory))
    assert resp.status_code == 403
    assert "secret roadmap" not in resp.text


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/api/v1/documents/", "/api/v1/documents"])
@pytest.mark.parametrize("extra", [{}, {"title": "plan"}])
async def test_list_requires_authentication(
    client: AsyncClient, alice: uuid.UUID, alice_doc: dict, path: str, extra: dict
):
    resp = await client.get(path, params={"owner_id": str(alice), **extra})
    assert resp.status_code == 401
    assert "secret roadmap" not in resp.text


@pytest.mark.asyncio
@pytest.mark.parametrize("extra", [{}, {"title": "plan"}])
async def test_list_without_owner_id_is_scoped_to_caller(
    client: AsyncClient, mallory: uuid.UUID, alice_doc: dict, extra: dict
):
    resp = await client.get("/api/v1/documents/", params=extra, headers=_auth(mallory))
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("extra", [{}, {"title": "plan"}])
async def test_list_with_own_owner_id_still_works(
    client: AsyncClient, alice: uuid.UUID, alice_doc: dict, extra: dict
):
    resp = await client.get(
        "/api/v1/documents/", params={"owner_id": str(alice), **extra}, headers=_auth(alice)
    )
    assert resp.status_code == 200
    assert [item["id"] for item in resp.json()["items"]] == [alice_doc["id"]]
