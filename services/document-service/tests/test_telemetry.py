"""The service reports how much database work each request cost."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from prometheus_client import REGISTRY

from app.main import app
from app.middleware import request_log


@pytest.mark.asyncio
async def test_list_reports_query_count(client: AsyncClient, owner_id: uuid.UUID):
    for i in range(3):
        await client.post(
            "/api/v1/documents/",
            json={"title": f"Doc {i}", "content": "", "owner_id": str(owner_id)},
        )
    resp = await client.get("/api/v1/documents/", params={"owner_id": str(owner_id)})
    assert resp.status_code == 200
    assert int(resp.headers["X-DB-Queries"]) >= 2


@pytest.mark.asyncio
async def test_metrics_expose_query_fanout(client: AsyncClient, owner_id: uuid.UUID):
    await client.get("/api/v1/documents/", params={"owner_id": str(owner_id)})
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "otterworks_db_queries_per_request_bucket" in resp.text
    assert 'handler="/api/v1/documents/"' in resp.text
    assert "http_request_duration_seconds_bucket" in resp.text


@pytest.mark.asyncio
async def test_request_log_exception_is_counted_as_500(
    client: AsyncClient, owner_id: uuid.UUID, monkeypatch: pytest.MonkeyPatch
):
    labels = {"method": "GET", "handler": "/api/v1/documents/", "status": "500"}
    before = REGISTRY.get_sample_value("http_requests_total", labels) or 0
    monkeypatch.setattr(request_log, "flag_active", lambda _: True)

    def fail_append(record):
        raise RuntimeError("request log failed")

    monkeypatch.setattr(request_log.request_log, "append", fail_append)
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/documents/", params={"owner_id": str(owner_id)})

    assert response.status_code == 500
    assert REGISTRY.get_sample_value("http_requests_total", labels) == before + 1
