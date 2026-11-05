"""The service reports how much database work each request cost."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentVersion


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
async def test_list_query_count_is_bounded_across_page_sizes(
    client: AsyncClient, db_session: AsyncSession, owner_id: uuid.UUID
):
    for i in range(6):
        doc = Document(id=uuid.uuid4(), title=f"Doc {i}", content="", owner_id=owner_id)
        db_session.add(doc)
        for number in range(1, 9):
            db_session.add(DocumentVersion(
                document_id=doc.id, version_number=number, title=doc.title,
                content="body", created_by=owner_id,
            ))
    await db_session.commit()
    counts = []
    for size in (1, 3, 6):
        db_session.expunge_all()
        response = await client.get(
            "/api/v1/documents/", params={"owner_id": str(owner_id), "size": size}
        )
        assert response.status_code == 200
        assert len(response.json()["items"]) == size
        counts.append(int(response.headers["X-DB-Queries"]))
    assert len(set(counts)) == 1, counts
    assert counts[0] <= 5

    response = await client.get(
        "/api/v1/documents/", params={"owner_id": str(uuid.uuid4())}
    )
    assert response.status_code == 200
    assert response.json()["items"] == []
    assert int(response.headers["X-DB-Queries"]) <= 5
