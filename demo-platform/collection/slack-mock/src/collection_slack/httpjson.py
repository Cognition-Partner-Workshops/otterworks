"""Minimal JSON-over-HTTPS client on http.client with explicit timeouts.

Errors carry only the method, path template, status and the API's error_code;
request headers and bodies are never logged or included in exceptions.
"""

from __future__ import annotations

import http.client
import json
import logging
import ssl
from typing import Any
from urllib.parse import urlsplit

log = logging.getLogger("collection_slack.http")

MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class HTTPFailure(Exception):
    def __init__(self, label: str, status: int | None, error_code: str | None = None, reason: str = "") -> None:
        self.label = label
        self.status = status
        self.error_code = error_code
        self.reason = reason
        super().__init__(f"{label}: status={status} error_code={error_code} {reason}".strip())

    @property
    def timed_out(self) -> bool:
        return self.reason == "timeout"


def request_json(
    method: str,
    url: str,
    *,
    label: str,
    headers: dict[str, str],
    body: dict[str, Any] | None = None,
    timeout: float,
) -> Any:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise HTTPFailure(label, None, reason="bad-url")
    path = parts.path or "/"
    if parts.query:
        path += "?" + parts.query
    conn: http.client.HTTPConnection
    if parts.scheme == "https":
        conn = http.client.HTTPSConnection(parts.hostname, parts.port, timeout=timeout, context=ssl.create_default_context())
    else:
        conn = http.client.HTTPConnection(parts.hostname, parts.port, timeout=timeout)
    payload = None if body is None else json.dumps(body).encode()
    send_headers = {"Accept": "application/json", **headers}
    if payload is not None:
        send_headers["Content-Type"] = "application/json"
    try:
        conn.request(method, path, body=payload, headers=send_headers)
        resp = conn.getresponse()
        raw = resp.read(MAX_RESPONSE_BYTES + 1)
    except TimeoutError as exc:
        log.warning("%s timed out after %.1fs", label, timeout)
        raise HTTPFailure(label, None, reason="timeout") from exc
    except (OSError, http.client.HTTPException) as exc:
        log.warning("%s transport error: %s", label, type(exc).__name__)
        raise HTTPFailure(label, None, reason="transport") from exc
    finally:
        conn.close()
    if len(raw) > MAX_RESPONSE_BYTES:
        raise HTTPFailure(label, resp.status, reason="response-too-large")
    data: Any = None
    if raw:
        try:
            data = json.loads(raw)
        except ValueError:
            data = None
    if not 200 <= resp.status < 300:
        code = data.get("error_code") if isinstance(data, dict) else None
        log.warning("%s failed: status=%s error_code=%s", label, resp.status, code)
        raise HTTPFailure(label, resp.status, error_code=code if isinstance(code, str) else None)
    log.info("%s ok: status=%s", label, resp.status)
    return data
