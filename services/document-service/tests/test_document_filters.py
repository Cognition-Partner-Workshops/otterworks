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
async def test_content_type_injection_does_not_cross_owners(
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
    assert resp.json()["total"] == 0
    assert resp.json()["items"] == []


@pytest.mark.asyncio
async def test_title_with_quote_is_matched_literally(client: AsyncClient, owner_id: uuid.UUID):
    await _create(client, owner_id, "Owner's Report")
    await _create(client, owner_id, "Quarterly Report")

    resp = await client.get("/api/v1/documents/", params={"title": "owner's"})

    assert resp.status_code == 200
    assert [item["title"] for item in resp.json()["items"]] == ["Owner's Report"]


@pytest.mark.asyncio
async def test_error_based_probe_leaks_no_sql(client: AsyncClient, owner_id: uuid.UUID):
    await _create(client, owner_id, "Quarterly Report")

    resp = await client.get("/api/v1/documents/", params={"title": "report'"})

    assert resp.status_code == 200
    assert "SELECT" not in resp.text
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("params", "detail"),
    [
        ({"sort": "title; DROP TABLE documents"}, "Invalid filter: Unsupported sort column"),
        ({"sort": "(SELECT 1)"}, "Invalid filter: Unsupported sort column"),
        (
            {"sort": "title", "direction": "asc; DROP TABLE documents"},
            "Invalid filter: Unsupported sort direction",
        ),
    ],
)
async def test_unsupported_sort_is_rejected_without_sql(
    client: AsyncClient, owner_id: uuid.UUID, params: dict[str, str], detail: str
):
    await _create(client, owner_id, "Quarterly Report")

    resp = await client.get("/api/v1/documents/", params={"title": "report", **params})

    assert resp.status_code == 400
    assert resp.json() == {"detail": detail}

    still_there = await client.get("/api/v1/documents/", params={"title": "report"})
    assert still_there.json()["total"] == 1


@pytest.mark.asyncio
async def test_sort_direction_is_case_insensitive(client: AsyncClient, owner_id: uuid.UUID):
    await _create(client, owner_id, "Beta plan")
    await _create(client, owner_id, "Alpha plan")

    resp = await client.get(
        "/api/v1/documents/",
        params={"title": "plan", "sort": "title", "direction": "DESC"},
    )

    assert resp.status_code == 200
    assert [item["title"] for item in resp.json()["items"]] == ["Beta plan", "Alpha plan"]
