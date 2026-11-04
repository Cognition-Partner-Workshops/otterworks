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

    resp = await client.get("/api/v1/documents/", params={"title": "plan", "size": 2, "page": 2})

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
async def test_title_injection_is_not_a_tautology(client: AsyncClient, owner_id: uuid.UUID):
    await _create(client, owner_id, "Quarterly Report")

    resp = await client.get("/api/v1/documents/", params={"title": "x') OR true --"})

    assert resp.status_code == 200
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_content_type_injection_is_not_a_tautology(client: AsyncClient, owner_id: uuid.UUID):
    await _create(client, owner_id, "Plan", content_type="text/markdown")

    resp = await client.get("/api/v1/documents/", params={"content_type": "text/html' OR '1'='1"})

    assert resp.status_code == 200
    assert resp.json()["items"] == []


@pytest.mark.asyncio
async def test_title_quote_is_matched_literally(client: AsyncClient, owner_id: uuid.UUID):
    await _create(client, owner_id, "Otter's report")
    await _create(client, owner_id, "Quarterly report")

    resp = await client.get("/api/v1/documents/", params={"title": "otter's"})

    assert resp.status_code == 200
    assert [item["title"] for item in resp.json()["items"]] == ["Otter's report"]


@pytest.mark.asyncio
async def test_title_like_wildcards_are_literal(client: AsyncClient, owner_id: uuid.UUID):
    await _create(client, owner_id, "100% done")
    await _create(client, owner_id, "Plan_A")
    await _create(client, owner_id, "Plan B")

    percent = await client.get("/api/v1/documents/", params={"title": "%"})
    underscore = await client.get("/api/v1/documents/", params={"title": "plan_"})

    assert [item["title"] for item in percent.json()["items"]] == ["100% done"]
    assert [item["title"] for item in underscore.json()["items"]] == ["Plan_A"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "params",
    [
        {"sort": "id;select 1"},
        {"sort": "title; DROP TABLE documents"},
        {"sort": "(select 1)"},
        {"direction": "asc, (select 1 from pg_sleep(3))"},
        {"direction": "sideways"},
    ],
)
async def test_unsupported_ordering_is_rejected_without_sql(
    client: AsyncClient, owner_id: uuid.UUID, params: dict
):
    await _create(client, owner_id, "Quarterly Report")

    resp = await client.get("/api/v1/documents/", params={**params})

    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert "SELECT" not in detail
    assert "documents" not in detail
    assert "[SQL" not in detail


@pytest.mark.asyncio
async def test_direction_is_case_insensitive(client: AsyncClient, owner_id: uuid.UUID):
    await _create(client, owner_id, "Beta plan")
    await _create(client, owner_id, "Alpha plan")

    resp = await client.get(
        "/api/v1/documents/",
        params={"sort": "title", "direction": "ASC"},
    )

    assert resp.status_code == 200
    assert [item["title"] for item in resp.json()["items"]] == ["Alpha plan", "Beta plan"]
