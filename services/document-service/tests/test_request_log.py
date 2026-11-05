"""The per-request debug log records metadata only: never document content,
owner/user identifiers, or request credentials."""

import json
import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.responses import StreamingResponse

from app.chaos import FLAG_REQUEST_LOG
from app.middleware import request_log as request_log_module
from app.middleware.request_log import REDACTED, RequestLog, redact_headers, redact_query


@pytest.fixture
def log_dir(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(request_log_module, "flag_active", lambda key: key == FLAG_REQUEST_LOG)
    monkeypatch.setattr(request_log_module, "request_log", RequestLog(str(tmp_path)))
    return tmp_path


def _records(log_dir) -> tuple[str, list[dict]]:
    (log_file,) = log_dir.iterdir()
    raw = log_file.read_text()
    return raw, [json.loads(line) for line in raw.splitlines()]


def test_redact_headers_keeps_only_allow_listed_values() -> None:
    redacted = redact_headers(
        {
            "Authorization": "Bearer secret",
            "Cookie": "session=abc",
            "Proxy-Authorization": "Basic xyz",
            "X-API-Key": "k",
            "X-User-ID": "11111111-1111-4111-8111-111111111111",
            "X-Anything-Else": "v",
            "Accept": "application/json",
        }
    )
    assert redacted["Authorization"] == REDACTED
    assert redacted["Cookie"] == REDACTED
    assert redacted["Proxy-Authorization"] == REDACTED
    assert redacted["X-API-Key"] == REDACTED
    assert redacted["X-User-ID"] == REDACTED
    assert redacted["X-Anything-Else"] == REDACTED
    assert redacted["Accept"] == "application/json"


def test_redact_query_keeps_only_allow_listed_values() -> None:
    assert redact_query("token=s3cret&format=html") == f"token={REDACTED}&format=html"
    assert redact_query("owner_id=u1&size=100") == f"owner_id={REDACTED}&size=100"
    assert redact_query("q=quarterly+results&page=2") == f"q={REDACTED}&page=2"
    assert redact_query("title=Payroll&name=../../etc/passwd") == (
        f"title={REDACTED}&name={REDACTED}"
    )
    assert redact_query("") == ""


@pytest.mark.asyncio
async def test_document_routes_leave_no_document_content_in_the_log(
    client: AsyncClient,
    owner_id: uuid.UUID,
    log_dir,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Same identity path as test_share_link: X-User-ID fallback with no JWT secret.
    monkeypatch.delenv("JWT_SECRET", raising=False)
    title = "Merger-Plan-Title-7f3a"
    content = "CONFIDENTIAL-BODY-9c41 acquisition terms"
    headers = {"Authorization": "Bearer top-secret", "Cookie": "sid=1", "X-User-ID": str(owner_id)}

    created = await client.post(
        "/api/v1/documents/",
        json={"title": title, "content": content, "owner_id": str(owner_id)},
        headers=headers,
    )
    assert created.status_code == 201
    doc_id = created.json()["id"]

    got = await client.get(f"/api/v1/documents/{doc_id}", headers=headers)
    assert got.status_code == 200
    assert got.json()["content"] == content
    listed = await client.get(
        "/api/v1/documents/", params={"owner_id": str(owner_id), "title": title}, headers=headers
    )
    assert listed.status_code == 200
    searched = await client.get(
        "/api/v1/documents/search", params={"q": "CONFIDENTIAL-BODY-9c41"}, headers=headers
    )
    assert searched.status_code == 200
    exported = await client.get(
        f"/api/v1/documents/{doc_id}/export", params={"format": "markdown"}, headers=headers
    )
    assert exported.status_code == 200
    assert content in exported.text

    raw, records = _records(log_dir)
    for secret in (title, content, "CONFIDENTIAL-BODY-9c41", str(owner_id), "top-secret", "sid=1"):
        assert secret not in raw
    assert len(records) == 5
    for record in records:
        assert "response" not in record
        assert isinstance(record["response_bytes"], int)
        assert record["headers"]["authorization"] == REDACTED
        assert record["headers"]["x-user-id"] == REDACTED
    get_record = next(r for r in records if r["path"] == f"/api/v1/documents/{doc_id}")
    assert get_record["status"] == 200
    assert get_record["response_bytes"] == len(got.content)


@pytest.mark.asyncio
async def test_large_stream_is_delivered_whole_and_only_its_size_is_logged(log_dir) -> None:
    chunk = b"x" * 65536
    chunks = 48
    app = FastAPI()
    request_log_module.install(app)

    @app.get("/export")
    async def export() -> StreamingResponse:
        async def gen():
            for _ in range(chunks):
                yield chunk

        return StreamingResponse(gen(), media_type="application/octet-stream")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/export")
    assert resp.status_code == 200
    assert len(resp.content) == chunks * len(chunk)

    raw, (record,) = _records(log_dir)
    assert "xxxx" not in raw
    assert "response" not in record
    assert record["response_bytes"] == chunks * len(chunk)
