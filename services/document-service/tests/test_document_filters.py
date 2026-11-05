"""Tests for the document list endpoint's metadata filters."""

import uuid

import pytest
from httpx import AsyncClient


async def _create(client: AsyncClient, owner_id: uuid.UUID, title: str, **kwargs):
    payload = {"title": title, "content": "body", "owner_id": str(owner_id)}
    payload.update(kwargs)
    resp = await client.post("/api/v1/documents/", json=payload)
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_filter_by_title_fragment(client: AsyncClient, owner_id: uuid.UUID):
    await _create(client, owner_id, "Quarterly Report")
    await _create(client, owner_id, "Meeting Notes")

    resp = await client.get("/api/v1/documents/", params={"title": "report"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert [item["title"] for item in body["items"]] == ["Quarterly Report"]


@pytest.mark.asyncio
async def test_filter_by_content_type(client: AsyncClient, owner_id: uuid.UUID):
    await _create(client, owner_id, "Plan", content_type="text/markdown")
    await _create(client, owner_id, "Page", content_type="text/html")

    resp = await client.get("/api/v1/documents/", params={"content_type": "text/html"})

    assert resp.status_code == 200
    assert [item["title"] for item in resp.json()["items"]] == ["Page"]


@pytest.mark.asyncio
async def test_filter_orders_by_title_ascending(client: AsyncClient, owner_id: uuid.UUID):
    await _create(client, owner_id, "Beta plan")
    await _create(client, owner_id, "Alpha plan")

    resp = await client.get(
        "/api/v1/documents/",
        params={"title": "plan", "sort": "title", "direction": "asc"},
    )

    assert resp.status_code == 200
    assert [item["title"] for item in resp.json()["items"]] == ["Alpha plan", "Beta plan"]


@pytest.mark.asyncio
async def test_filter_paginates(client: AsyncClient, owner_id: uuid.UUID):
    for index in range(3):
        await _create(client, owner_id, f"Plan {index}")

    resp = await client.get(
        "/api/v1/documents/", params={"title": "plan", "size": 2, "page": 2}
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert body["pages"] == 2
    assert len(body["items"]) == 1


@pytest.mark.asyncio
async def test_filter_no_match_returns_empty(client: AsyncClient, owner_id: uuid.UUID):
    await _create(client, owner_id, "Quarterly Report")

    resp = await client.get("/api/v1/documents/", params={"title": "nothing"})

    assert resp.status_code == 200
    assert resp.json() == {"items": [], "total": 0, "page": 1, "size": 20, "pages": 1}


@pytest.mark.asyncio
async def test_unfiltered_list_is_unchanged(client: AsyncClient, owner_id: uuid.UUID):
    await _create(client, owner_id, "Quarterly Report")

    resp = await client.get("/api/v1/documents/", params={"owner_id": str(owner_id)})

    assert resp.status_code == 200
    assert resp.json()["total"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/api/v1/documents/", "/api/v1/documents"])
@pytest.mark.parametrize("field", ["title", "content_type"])
@pytest.mark.parametrize("payload", ["'", "' OR 1=1 --", "'; SELECT 1 --"])
async def test_filter_binds_injected_values(
    client: AsyncClient, owner_id: uuid.UUID, path: str, field: str, payload: str
):
    await _create(client, owner_id, "Unrelated document")
    values = {field: payload}
    if field == "title":
        await _create(client, owner_id, payload)
    else:
        await _create(client, owner_id, "Matching document", **values)

    resp = await client.get(path, params=values)

    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0][field] == payload


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/api/v1/documents/", "/api/v1/documents"])
@pytest.mark.parametrize(
    "ordering",
    [
        {"sort": "title; SELECT 1 --"},
        {"sort": "not_a_column"},
        {"direction": "desc; SELECT 1 --"},
        {"direction": "invalid"},
    ],
)
async def test_filter_rejects_invalid_ordering(client: AsyncClient, path: str, ordering: dict):
    resp = await client.get(path, params=ordering)
    assert resp.status_code == 400
    assert resp.json() == {"detail": "Invalid filter"}


@pytest.mark.asyncio
async def test_filter_preserves_folder_scope(client: AsyncClient, owner_id: uuid.UUID):
    folder = uuid.uuid4()
    await _create(client, owner_id, "Plan in folder", folder_id=str(folder))
    await _create(client, owner_id, "Plan outside folder")

    resp = await client.get(
        "/api/v1/documents/", params={"title": "Plan", "folder_id": str(folder)}
    )
    assert resp.status_code == 200
    assert [item["title"] for item in resp.json()["items"]] == ["Plan in folder"]


@pytest.mark.asyncio
async def test_filter_does_not_expose_database_errors(client: AsyncClient, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError

    from app.services.document_query_repository import DocumentQueryRepository

    async def fail(*args, **kwargs):
        raise SQLAlchemyError("private database connection detail")

    monkeypatch.setattr(DocumentQueryRepository, "count_documents", fail)
    resp = await client.get("/api/v1/documents/", params={"title": "Plan"})
    assert resp.status_code == 400
    assert resp.json() == {"detail": "Invalid filter"}
