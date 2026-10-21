"""The service reports how much database work each request cost."""

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_reports_query_count(
    client: AsyncClient, owner_id: uuid.UUID, owner_headers: dict[str, str]
):
    for i in range(3):
        await client.post(
            "/api/v1/documents/",
            json={"title": f"Doc {i}", "content": "", "owner_id": str(owner_id)},
        )
    resp = await client.get(
        "/api/v1/documents/", params={"owner_id": str(owner_id)}, headers=owner_headers
    )
    assert resp.status_code == 200
    assert int(resp.headers["X-DB-Queries"]) >= 2


@pytest.mark.asyncio
async def test_metrics_expose_query_fanout(
    client: AsyncClient, owner_id: uuid.UUID, owner_headers: dict[str, str]
):
    await client.get(
        "/api/v1/documents/", params={"owner_id": str(owner_id)}, headers=owner_headers
    )
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "otterworks_db_queries_per_request_bucket" in resp.text
    assert 'handler="/api/v1/documents/"' in resp.text
    assert "http_request_duration_seconds_bucket" in resp.text
