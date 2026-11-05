"""The per-request debug log never retains request credentials."""

import json
import uuid
from collections import namedtuple

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.responses import StreamingResponse

from app.chaos import FLAG_REQUEST_LOG
from app.middleware import request_log as request_log_module
from app.middleware.request_log import (
    REDACTED,
    RESPONSE_CAPTURE_BYTES,
    RequestLog,
    redact_body,
    redact_headers,
    redact_query,
)
from app.telemetry import REQUEST_LOG_BYTES, SERVICE


def test_request_log_rotation_stays_bounded(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(request_log_module, "REQUEST_LOG_FILE_BYTES", 256)
    log = RequestLog(str(tmp_path))
    for index in range(100):
        log.append({"index": index, "response": "x" * 100})
        files = list(tmp_path.iterdir())
        total = sum(path.stat().st_size for path in files)
        assert len(files) <= request_log_module.REQUEST_LOG_BACKUPS + 1
        assert all(path.stat().st_size <= 256 for path in files)
        assert total <= 1024
        assert REQUEST_LOG_BYTES.labels(SERVICE)._value.get() == total
    assert {path.name for path in files} == {
        log.path.rsplit("/", 1)[-1] + suffix for suffix in ("", ".1", ".2", ".3")
    }
    log.purge()
    assert list(tmp_path.iterdir()) == []
    assert REQUEST_LOG_BYTES.labels(SERVICE)._value.get() == 0


def test_request_log_respects_capacity_and_skips_oversized_records(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    usage = namedtuple("Usage", "total used free")
    monkeypatch.setattr(request_log_module.shutil, "disk_usage", lambda _: usage(4096, 0, 4096))
    log = RequestLog(str(tmp_path))
    log.append({"response": "x" * 200})
    assert list(tmp_path.iterdir()) == []
    for _ in range(100):
        log.append({"response": "x" * 50})
    assert sum(path.stat().st_size for path in tmp_path.iterdir()) <= 4096 // 8
    assert all(path.stat().st_size <= 128 for path in tmp_path.iterdir())


def test_request_log_discards_oversized_existing_files(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(request_log_module, "REQUEST_LOG_FILE_BYTES", 128)
    log = RequestLog(str(tmp_path))
    for suffix in ("", ".1", ".2", ".3"):
        (tmp_path / (log.path.rsplit("/", 1)[-1] + suffix)).write_bytes(b"x" * 256)
    log.append({})
    assert [path.read_bytes() for path in tmp_path.iterdir()] == [b"{}\n"]
    assert REQUEST_LOG_BYTES.labels(SERVICE)._value.get() == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
async def test_failed_log_write_does_not_fail_request(
    tmp_path, monkeypatch: pytest.MonkeyPatch, streaming: bool
) -> None:
    monkeypatch.setattr(request_log_module, "flag_active", lambda _: True)
    log = RequestLog(str(tmp_path))
    monkeypatch.setattr(request_log_module, "request_log", log)

    def fail_open(*args, **kwargs):
        raise OSError("No space left on device")

    monkeypatch.setattr(request_log_module, "open", fail_open, raising=False)
    app = FastAPI()
    request_log_module.install(app)

    @app.get("/example")
    async def example():
        if streaming:
            return StreamingResponse(iter([b"ok"]))
        return {"message": "ok"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/example")
    assert response.status_code == 200
    assert response.content == (b"ok" if streaming else b'{"message":"ok"}')
    assert REQUEST_LOG_BYTES.labels(SERVICE)._value.get() == 0


def test_redact_headers_masks_credentials_only() -> None:
    redacted = redact_headers(
        {
            "Authorization": "Bearer secret",
            "Cookie": "session=abc",
            "Proxy-Authorization": "Basic xyz",
            "X-API-Key": "k",
            "Accept": "application/json",
        }
    )
    assert redacted["Authorization"] == REDACTED
    assert redacted["Cookie"] == REDACTED
    assert redacted["Proxy-Authorization"] == REDACTED
    assert redacted["X-API-Key"] == REDACTED
    assert redacted["Accept"] == "application/json"


def test_redact_query_masks_share_tokens_only() -> None:
    assert redact_query("token=s3cret&format=html") == f"token={REDACTED}&format=html"
    assert redact_query("owner_id=u1&size=100") == "owner_id=u1&size=100"
    assert redact_query("") == ""


def test_redact_body_masks_minted_tokens_only() -> None:
    body = json.dumps({"document_id": "d1", "token": 's3"cret', "title": "token"})
    redacted = json.loads(redact_body(body))
    assert redacted == {"document_id": "d1", "token": REDACTED, "title": "token"}
    assert redact_body('{"items": [], "total": 0}') == '{"items": [], "total": 0}'


@pytest.mark.asyncio
async def test_logged_request_keeps_body_but_not_bearer_token(
    client: AsyncClient,
    owner_id: uuid.UUID,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(request_log_module, "flag_active", lambda key: key == FLAG_REQUEST_LOG)
    monkeypatch.setattr(request_log_module, "request_log", RequestLog(str(tmp_path)))

    resp = await client.get(
        "/api/v1/documents/",
        params={"owner_id": str(owner_id)},
        headers={"Authorization": "Bearer top-secret", "Cookie": "sid=1"},
    )
    assert resp.status_code == 200

    files = list(tmp_path.iterdir())
    assert len(files) == 1
    raw = files[0].read_text()
    assert "top-secret" not in raw
    assert "sid=1" not in raw
    record = json.loads(raw.splitlines()[-1])
    assert record["headers"]["authorization"] == REDACTED
    assert record["headers"]["cookie"] == REDACTED
    assert json.loads(record["response"])["total"] == 0


@pytest.mark.asyncio
async def test_large_stream_is_delivered_whole_but_only_a_prefix_is_logged(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(request_log_module, "flag_active", lambda key: key == FLAG_REQUEST_LOG)
    monkeypatch.setattr(request_log_module, "request_log", RequestLog(str(tmp_path)))

    chunk = b"x" * 65536
    chunks = 3 * RESPONSE_CAPTURE_BYTES // len(chunk)
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

    (log_file,) = tmp_path.iterdir()
    record = json.loads(log_file.read_text())
    assert len(record["response"]) == RESPONSE_CAPTURE_BYTES
    assert record["response_truncated"] is True
