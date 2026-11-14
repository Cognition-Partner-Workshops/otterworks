"""Regression tests: document list/search are scoped to the authenticated caller."""

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import TEST_JWT_SECRET, auth_headers_for

LIST_PATHS = ["/api/v1/documents/", "/api/v1/documents"]


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)


@pytest.fixture
def victim_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def attacker_id() -> uuid.UUID:
    return uuid.uuid4()


async def _create(client: AsyncClient, owner: uuid.UUID, title: str, content: str = "body"):
    resp = await client.post(
        "/api/v1/documents/",
        json={"title": title, "content": content},
        headers=auth_headers_for(owner),
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def seeded(client: AsyncClient, victim_id: uuid.UUID, attacker_id: uuid.UUID):
    victim_doc = await _create(client, victim_id, "Victim payroll report", "salary secrets")
    attacker_doc = await _create(client, attacker_id, "Attacker notes report", "my notes")
    return victim_doc, attacker_doc


@pytest.mark.asyncio
@pytest.mark.parametrize("path", LIST_PATHS)
async def test_unauthenticated_list_is_rejected(client: AsyncClient, seeded, path: str):
    resp = await client.get(path)
    assert resp.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("path", LIST_PATHS)
async def test_unauthenticated_list_with_owner_id_is_rejected(
    client: AsyncClient, seeded, victim_id: uuid.UUID, path: str
):
    resp = await client.get(path, params={"owner_id": str(victim_id)})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_filtered_list_is_rejected(client: AsyncClient, seeded):
    resp = await client.get("/api/v1/documents/", params={"title": "report"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_spoofed_identity_header_alone_is_rejected(
    client: AsyncClient, seeded, victim_id: uuid.UUID
):
    resp = await client.get("/api/v1/documents/", headers={"X-User-ID": str(victim_id)})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_search_is_rejected(client: AsyncClient, seeded):
    resp = await client.get("/api/v1/documents/search", params={"q": "report"})
    assert resp.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("path", LIST_PATHS)
async def test_owner_id_param_cannot_read_another_users_documents(
    client: AsyncClient, seeded, victim_id: uuid.UUID, attacker_id: uuid.UUID, path: str
):
    _, attacker_doc = seeded
    resp = await client.get(
        path, params={"owner_id": str(victim_id)}, headers=auth_headers_for(attacker_id)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert [item["id"] for item in body["items"]] == [attacker_doc["id"]]
    assert all(item["owner_id"] == str(attacker_id) for item in body["items"])


@pytest.mark.asyncio
async def test_owner_id_param_cannot_read_another_users_documents_on_filter_path(
    client: AsyncClient, seeded, victim_id: uuid.UUID, attacker_id: uuid.UUID
):
    _, attacker_doc = seeded
    resp = await client.get(
        "/api/v1/documents/",
        params={"owner_id": str(victim_id), "title": "report"},
        headers=auth_headers_for(attacker_id),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert [item["id"] for item in body["items"]] == [attacker_doc["id"]]


@pytest.mark.asyncio
async def test_search_does_not_return_other_users_documents(
    client: AsyncClient, seeded, attacker_id: uuid.UUID
):
    resp = await client.get(
        "/api/v1/documents/search",
        params={"q": "salary"},
        headers=auth_headers_for(attacker_id),
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
    assert resp.json()["items"] == []


@pytest.mark.asyncio
async def test_owner_still_lists_and_searches_own_documents(
    client: AsyncClient, seeded, victim_id: uuid.UUID
):
    victim_doc, _ = seeded
    headers = auth_headers_for(victim_id)

    listed = await client.get("/api/v1/documents/", headers=headers)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [victim_doc["id"]]

    searched = await client.get("/api/v1/documents/search", params={"q": "report"}, headers=headers)
    assert searched.status_code == 200
    assert [item["id"] for item in searched.json()["items"]] == [victim_doc["id"]]
