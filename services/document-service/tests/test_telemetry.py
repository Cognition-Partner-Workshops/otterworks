"""The service reports how much database work each request cost."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentVersion
from app.services.document_service import DocumentService


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
async def test_list_query_count_does_not_grow_with_page_size(
    client: AsyncClient, db_session: AsyncSession, owner_id: uuid.UUID
):
    for i in range(12):
        doc = Document(title=f"Doc {i}", content="", owner_id=owner_id, version=7)
        db_session.add(doc)
        await db_session.flush()
        for n in range(1, 8):
            db_session.add(
                DocumentVersion(
                    document_id=doc.id,
                    version_number=n,
                    title=doc.title,
                    content="",
                    created_by=owner_id,
                )
            )
    await db_session.commit()

    resp = await client.get("/api/v1/documents/", params={"owner_id": str(owner_id), "size": 12})
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 12
    assert int(resp.headers["X-DB-Queries"]) <= 5

    docs, _ = await DocumentService(db_session).list_documents(owner_id=owner_id, size=12)
    for doc in docs:
        assert [v.version_number for v in doc.recent_versions] == [7, 6, 5, 4, 3]
