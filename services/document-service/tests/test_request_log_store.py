"""The request-log file store and the streamed-response capture path."""

import json

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.responses import StreamingResponse

from app.chaos import FLAG_REQUEST_LOG
from app.middleware import request_log as request_log_module
from app.middleware.request_log import RequestLog, declared_length


def test_append_creates_directory_and_tracks_bytes(tmp_path) -> None:
    directory = tmp_path / "nested" / "logs"
    log = RequestLog(str(directory))
    assert log._bytes == 0

    log.append({"path": "/a"})
    log.append({"path": "/b"})

    with open(log.path, encoding="utf-8") as fh:
        lines = [json.loads(line) for line in fh]
    assert lines == [{"path": "/a"}, {"path": "/b"}]
    assert log._bytes == (directory / log.path.rsplit("/", 1)[-1]).stat().st_size


def test_existing_files_are_counted_on_startup(tmp_path) -> None:
    (tmp_path / "old.jsonl").write_text("x" * 10)
    assert RequestLog(str(tmp_path))._bytes == 10


def test_purge_removes_files_and_resets_byte_count(tmp_path) -> None:
    log = RequestLog(str(tmp_path))
    log.append({"path": "/a"})
    (tmp_path / "subdir").mkdir()

    log.purge()

    assert [p.name for p in tmp_path.iterdir()] == ["subdir"]
    assert log._bytes == 0


def test_purge_of_missing_directory_is_harmless(tmp_path) -> None:
    log = RequestLog(str(tmp_path / "never-created"))
    log.purge()
    assert log._bytes == 0


@pytest.mark.parametrize(("header", "expected"), [("12", 12), ("", None), ("abc", None)])
def test_declared_length(header: str, expected: int | None) -> None:
    from starlette.responses import Response

    response = Response()
    if header:
        response.headers["content-length"] = header
    else:
        del response.headers["content-length"]
    assert declared_length(response) == expected


def _streaming_app() -> FastAPI:
    app = FastAPI()
    request_log_module.install(app)

    @app.get("/stream")
    async def stream() -> StreamingResponse:
        async def gen():
            yield "text-"
            yield b"bytes"

        return StreamingResponse(gen(), media_type="text/plain")

    @app.get("/health")
    async def health() -> dict:
        return {"ok": True}

    return app


@pytest.mark.asyncio
async def test_streamed_text_chunks_are_logged(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(request_log_module, "flag_active", lambda key: key == FLAG_REQUEST_LOG)
    monkeypatch.setattr(request_log_module, "request_log", RequestLog(str(tmp_path)))

    async with AsyncClient(
        transport=ASGITransport(app=_streaming_app()), base_url="http://t"
    ) as ac:
        resp = await ac.get("/stream", params={"token": "secret", "q": "1"})

    assert resp.text == "text-bytes"
    (log_file,) = tmp_path.iterdir()
    record = json.loads(log_file.read_text())
    assert record["response"] == "text-bytes"
    assert record["response_truncated"] is False
    assert record["query"] == "token=[redacted]&q=1"
    assert record["method"] == "GET"
    assert record["status"] == 200


@pytest.mark.asyncio
async def test_streamed_response_survives_log_write_failure(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FailingLog(RequestLog):
        def append(self, record: dict) -> None:
            raise OSError("disk full")

    monkeypatch.setattr(request_log_module, "flag_active", lambda key: key == FLAG_REQUEST_LOG)
    monkeypatch.setattr(request_log_module, "request_log", FailingLog(str(tmp_path)))

    async with AsyncClient(
        transport=ASGITransport(app=_streaming_app()), base_url="http://t"
    ) as ac:
        resp = await ac.get("/stream")

    assert resp.status_code == 200
    assert resp.text == "text-bytes"


@pytest.mark.asyncio
async def test_skipped_paths_and_disabled_flag_are_not_logged(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(request_log_module, "request_log", RequestLog(str(tmp_path)))
    app = _streaming_app()

    monkeypatch.setattr(request_log_module, "flag_active", lambda key: True)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        assert (await ac.get("/health")).status_code == 200

    monkeypatch.setattr(request_log_module, "flag_active", lambda key: False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        assert (await ac.get("/stream")).status_code == 200

    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_chunks_encodes_text_and_passes_bytes_through() -> None:
    from starlette.responses import Response

    from app.middleware.request_log import _chunks

    async def gen():
        yield "text-"
        yield b"bytes"

    streamed = [chunk async for chunk in _chunks(StreamingResponse(gen()))]
    assert streamed == [b"text-", b"bytes"]
    assert [chunk async for chunk in _chunks(Response(content=b"whole"))] == [b"whole"]
