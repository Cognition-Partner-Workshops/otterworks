"""Per-request debug log.

When the ``request_log`` flag is on, every API request is appended to a JSONL
file under ``settings.request_log_dir``. Only request metadata is recorded
(method, path, status, duration, response size and an allow-listed subset of
query parameters and headers): response bodies carry customer document text and
are never written, and anything outside the allow-lists (search terms, titles,
owner and user ids, credentials) is masked.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import socket
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from urllib.parse import parse_qsl, urlencode

import structlog
from fastapi import FastAPI, Request, Response
from starlette.responses import StreamingResponse

from app.chaos import FLAG_REQUEST_LOG, flag_active
from app.config import settings
from app.telemetry import REQUEST_LOG_BYTES, REQUEST_LOG_CAPACITY_BYTES, SERVICE

logger = structlog.get_logger()

SKIP_PATHS = ("/health", "/metrics", "/ready")
LOGGED_HEADERS = frozenset(
    {
        "accept",
        "accept-encoding",
        "content-length",
        "content-type",
        "host",
        "traceparent",
        "user-agent",
        "x-request-id",
    }
)
LOGGED_QUERY_PARAMS = frozenset({"content_type", "direction", "format", "page", "size", "sort"})
REDACTED = "[redacted]"


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    """Copy of the request headers with every value outside the allow-list masked."""
    return {k: (v if k.lower() in LOGGED_HEADERS else REDACTED) for k, v in headers.items()}


def redact_query(query: str) -> str:
    """The query string with every parameter outside the allow-list masked."""
    pairs = parse_qsl(query, keep_blank_values=True)
    return urlencode(
        [(k, v if k.lower() in LOGGED_QUERY_PARAMS else REDACTED) for k, v in pairs],
        safe="[]",
    )


class RequestLog:
    def __init__(self, directory: str) -> None:
        self.directory = directory
        self.path = os.path.join(directory, f"requests-{socket.gethostname()}.jsonl")
        self._bytes = self._scan()

    def _scan(self) -> int:
        try:
            with os.scandir(self.directory) as it:
                total = sum(e.stat().st_size for e in it if e.is_file())
        except OSError:
            total = 0
        self._publish(total)
        return total

    def _publish(self, total: int) -> None:
        REQUEST_LOG_BYTES.labels(SERVICE).set(total)
        with contextlib.suppress(OSError):
            REQUEST_LOG_CAPACITY_BYTES.labels(SERVICE).set(shutil.disk_usage(self.directory).total)

    def append(self, record: dict) -> None:
        os.makedirs(self.directory, exist_ok=True)
        line = json.dumps(record, default=str) + "\n"
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(line)
        self._bytes += len(line)
        self._publish(self._bytes)

    def purge(self) -> None:
        try:
            with os.scandir(self.directory) as it:
                for entry in it:
                    if entry.is_file():
                        os.unlink(entry.path)
        except OSError:
            pass
        self._bytes = self._scan()


request_log = RequestLog(settings.request_log_dir)


def declared_length(response: Response) -> int | None:
    raw = response.headers.get("content-length", "")
    return int(raw) if raw.isdigit() else None


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def _request_log(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path in SKIP_PATHS or not flag_active(FLAG_REQUEST_LOG):
            return await call_next(request)

        started = time.perf_counter()
        response = await call_next(request)
        record = {
            "ts": time.time(),
            "method": request.method,
            "path": request.url.path,
            "query": redact_query(str(request.url.query)),
            "status": response.status_code,
            "headers": redact_headers(dict(request.headers)),
        }
        length = declared_length(response)

        if length is not None or not isinstance(response, StreamingResponse):
            record["duration_ms"] = round((time.perf_counter() - started) * 1000, 2)
            record["response_bytes"] = length if length is not None else len(response.body)
            request_log.append(record)
            return response

        async def counted() -> AsyncIterator[bytes]:
            size = 0
            async for chunk in response.body_iterator:
                data = chunk if isinstance(chunk, bytes) else chunk.encode()
                size += len(data)
                yield data
            record["duration_ms"] = round((time.perf_counter() - started) * 1000, 2)
            record["response_bytes"] = size
            # The body is already with the client; a failed write cannot fail it.
            try:
                request_log.append(record)
            except OSError:
                logger.exception("request_log_append_failed", path=request.url.path)

        return StreamingResponse(
            counted(),
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )
