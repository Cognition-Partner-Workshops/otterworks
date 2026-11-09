"""Owner scoping: list/search/comments/access are bound to the authenticated user."""

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers


async def _create(client: AsyncClient, owner_id: uuid.UUID, title: str) -> str:
    resp = await client.post(
        "/api/v1/documents/",
        json={"title": title, "content": f"body of {title}"},
        headers=auth_headers(owner_id),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/api/v1/documents/", "/api/v1/documents"])
async def test_list_requires_authentication(client: AsyncClient, owner_id: uuid.UUID, path: str):
    await _create(client, owner_id, "Private")

    resp = await client.get(path)
    assert resp.status_code == 401

    resp = await client.get(path, params={"owner_id": str(owner_id)})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_search_requires_authentication(client: AsyncClient, owner_id: uuid.UUID):
    await _create(client, owner_id, "Private")
    resp = await client.get("/api/v1/documents/search", params={"q": "Private"})
    assert resp.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "params",
    [{}, {"title": "secret"}, {"sort": "title", "direction": "asc"}],
    ids=["default", "filtered", "sorted"],
)
async def test_list_is_scoped_to_caller(client: AsyncClient, owner_id: uuid.UUID, params: dict):
    victim = uuid.uuid4()
    await _create(client, victim, "Victim secret plan")
    mine = await _create(client, owner_id, "My secret notes")

    resp = await client.get("/api/v1/documents/", params=params, headers=auth_headers(owner_id))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert [item["id"] for item in body["items"]] == [mine]
    assert {item["owner_id"] for item in body["items"]} == {str(owner_id)}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "params",
    [{}, {"title": "secret"}],
    ids=["default", "filtered"],
)
async def test_list_rejects_foreign_owner_id(
    client: AsyncClient, owner_id: uuid.UUID, params: dict
):
    victim = uuid.uuid4()
    await _create(client, victim, "Victim secret plan")

    resp = await client.get(
        "/api/v1/documents/",
        params={"owner_id": str(victim), **params},
        headers=auth_headers(owner_id),
    )
    assert resp.status_code == 403
    assert "Victim" not in resp.text


@pytest.mark.asyncio
async def test_list_accepts_own_owner_id(client: AsyncClient, owner_id: uuid.UUID):
    mine = await _create(client, owner_id, "Mine")
    resp = await client.get(
        "/api/v1/documents/", params={"owner_id": str(owner_id)}, headers=auth_headers(owner_id)
    )
    assert resp.status_code == 200
    assert [item["id"] for item in resp.json()["items"]] == [mine]


@pytest.mark.asyncio
async def test_search_is_scoped_to_caller(client: AsyncClient, owner_id: uuid.UUID):
    victim = uuid.uuid4()
    await _create(client, victim, "Quarterly revenue")
    mine = await _create(client, owner_id, "Quarterly notes")

    resp = await client.get(
        "/api/v1/documents/search", params={"q": "Quarterly"}, headers=auth_headers(owner_id)
    )
    assert resp.status_code == 200
    assert [item["id"] for item in resp.json()["items"]] == [mine]


@pytest.mark.asyncio
async def test_access_check(client: AsyncClient, owner_id: uuid.UUID):
    attacker = uuid.uuid4()
    doc_id = await _create(client, owner_id, "Shared?")

    resp = await client.get(f"/api/v1/documents/{doc_id}/access")
    assert resp.status_code == 401

    resp = await client.get(f"/api/v1/documents/{doc_id}/access", headers=auth_headers(owner_id))
    assert resp.status_code == 200
    assert resp.json() == {"document_id": doc_id, "user_id": str(owner_id), "allowed": True}

    resp = await client.get(f"/api/v1/documents/{doc_id}/access", headers=auth_headers(attacker))
    assert resp.status_code == 200
    assert resp.json()["allowed"] is False

    resp = await client.get(
        f"/api/v1/documents/{uuid.uuid4()}/access", headers=auth_headers(owner_id)
    )
    assert resp.status_code == 200
    assert resp.json()["allowed"] is False


@pytest.mark.asyncio
async def test_foreign_document_routes_are_denied(client: AsyncClient, owner_id: uuid.UUID):
    attacker = uuid.uuid4()
    doc_id = await _create(client, owner_id, "Owned")
    headers = auth_headers(attacker)

    assert (await client.get(f"/api/v1/documents/{doc_id}", headers=headers)).status_code == 403
    assert (
        await client.get(f"/api/v1/documents/{doc_id}/versions", headers=headers)
    ).status_code == 403
    assert (
        await client.get(f"/api/v1/documents/{doc_id}/comments", headers=headers)
    ).status_code == 403
    assert (
        await client.post(
            f"/api/v1/documents/{doc_id}/comments",
            json={"author_id": str(attacker), "content": "hi"},
            headers=headers,
        )
    ).status_code == 403
    assert (await client.delete(f"/api/v1/documents/{doc_id}", headers=headers)).status_code == 403

    still_there = await client.get(f"/api/v1/documents/{doc_id}", headers=auth_headers(owner_id))
    assert still_there.status_code == 200
