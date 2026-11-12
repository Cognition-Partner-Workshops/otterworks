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
async def test_filter_content_type_tautology_stays_owner_scoped(
    client: AsyncClient, owner_id: uuid.UUID
):
    other_owner = uuid.uuid4()
    await _create(client, owner_id, "Mine", content_type="text/markdown")
    await _create(client, other_owner, "Theirs", content_type="text/markdown")

    resp = await client.get(
        "/api/v1/documents/",
        params={"owner_id": str(owner_id), "content_type": "text/markdown' OR '1'='1"},
    )

    assert resp.status_code == 200
    assert resp.json() == {"items": [], "total": 0, "page": 1, "size": 20, "pages": 1}


@pytest.mark.asyncio
async def test_filter_title_quote_is_a_literal(client: AsyncClient, owner_id: uuid.UUID):
    await _create(client, owner_id, "Quarterly Report")
    await _create(client, owner_id, "Bob's Report")

    resp = await client.get("/api/v1/documents/", params={"title": "x' OR '1'='1"})
    assert resp.status_code == 200
    assert resp.json()["total"] == 0

    resp = await client.get("/api/v1/documents/", params={"title": "bob's"})
    assert resp.status_code == 200
    assert [item["title"] for item in resp.json()["items"]] == ["Bob's Report"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("sort", "direction"),
    [
        ("(select 1)", "desc"),
        ("title; DROP TABLE documents", "desc"),
        ("updated_at", "desc; DROP TABLE documents"),
        ("content", "asc"),
        ("", "asc"),
    ],
)
async def test_filter_rejects_sort_outside_allowlist(
    client: AsyncClient, owner_id: uuid.UUID, sort: str, direction: str
):
    await _create(client, owner_id, "Quarterly Report")

    resp = await client.get(
        "/api/v1/documents/", params={"sort": sort, "direction": direction}
    )

    assert resp.status_code == 400
    assert resp.json() == {"detail": "Invalid sort or direction"}

    resp = await client.get("/api/v1/documents/", params={"owner_id": str(owner_id)})
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


@pytest.mark.asyncio
async def test_filter_sort_direction_is_case_insensitive(client: AsyncClient, owner_id: uuid.UUID):
    await _create(client, owner_id, "Beta plan")
    await _create(client, owner_id, "Alpha plan")

    resp = await client.get(
        "/api/v1/documents/", params={"title": "plan", "sort": "Title", "direction": "ASC"}
    )

    assert resp.status_code == 200
    assert [item["title"] for item in resp.json()["items"]] == ["Alpha plan", "Beta plan"]


@pytest.mark.asyncio
async def test_filter_error_does_not_leak_database_text(
    client: AsyncClient, owner_id: uuid.UUID, monkeypatch: pytest.MonkeyPatch
):
    from sqlalchemy.exc import OperationalError

    from app.api import documents as documents_api

    async def _boom(self, **kwargs):
        raise OperationalError("SELECT secret FROM documents", {}, Exception("boom"))

    monkeypatch.setattr(documents_api.DocumentQueryRepository, "count_documents", _boom)

    resp = await client.get("/api/v1/documents/", params={"title": "report"})

    assert resp.status_code == 400
    assert resp.json() == {"detail": "Invalid filter"}
    assert "SELECT" not in resp.text
    assert "documents" not in resp.json()["detail"]
