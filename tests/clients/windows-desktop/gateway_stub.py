"""In-memory stub of the OtterWorks API gateway endpoints used by the Windows desktop client.

Serves ``POST /auth/register``, ``POST /auth/login``, ``GET /documents``, ``POST /documents``
and ``GET /files`` under ``/api/v1`` with the same JSON shapes as auth-service (camelCase),
document-service (snake_case, pydantic timestamps) and file-service (snake_case, chrono
timestamps). Every request is recorded so tests can pin exactly what the client sends.

Run standalone: ``python gateway_stub.py --port 8080``.
"""

from __future__ import annotations

import argparse
import json
import threading
import uuid
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlsplit

API_PREFIX = "/api/v1"
FIXED_EPOCH = datetime(2026, 10, 7, 12, 0, 0, 123456, tzinfo=UTC)


def _pydantic_ts(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _chrono_ts(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%S.%f") + "789Z"


class StubState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.users: dict[str, dict[str, Any]] = {}
        self.tokens: dict[str, str] = {}
        self.documents: list[dict[str, Any]] = []
        self.requests: list[dict[str, Any]] = []
        self.issued_tokens: list[str] = []
        self._tick = 0

    def next_time(self) -> datetime:
        self._tick += 1
        return FIXED_EPOCH + timedelta(minutes=self._tick)

    def issue(self, user: dict[str, Any]) -> dict[str, Any]:
        access = f"stub-access-{uuid.uuid4().hex}"
        refresh = f"stub-refresh-{uuid.uuid4().hex}"
        self.tokens[access] = user["email"]
        self.issued_tokens.append(access)
        return {
            "accessToken": access,
            "refreshToken": refresh,
            "tokenType": "Bearer",
            "expiresIn": 900,
            "user": {
                "id": user["id"],
                "email": user["email"],
                "displayName": user["displayName"],
                "avatarUrl": None,
            },
        }


def _error(status: int, reason: str, message: str) -> tuple[int, dict[str, Any]]:
    """auth-service GlobalExceptionHandler error body."""
    return status, {
        "timestamp": _pydantic_ts(FIXED_EPOCH),
        "status": status,
        "error": reason,
        "message": message,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "OtterWorksGatewayStub/1.0"
    state: StubState

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        pass

    def do_GET(self) -> None:  # noqa: N802
        self._handle("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._handle("POST")

    def _handle(self, method: str) -> None:
        parts = urlsplit(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""

        if parts.path.startswith("/__stub/"):
            self._send(*self._control(parts.path))
            return

        body: Any = None
        if raw:
            try:
                body = json.loads(raw)
            except ValueError:
                body = raw.decode("utf-8", "replace")

        with self.state.lock:
            self.state.requests.append(
                {
                    "method": method,
                    "path": parts.path,
                    "query": parse_qs(parts.query),
                    "headers": {k: v for k, v in self.headers.items()},
                    "body": body,
                }
            )
            status, payload = self._route(method, parts.path, parse_qs(parts.query), body)
        self._send(status, payload)

    def _control(self, path: str) -> tuple[int, Any]:
        with self.state.lock:
            if path == "/__stub/requests":
                return 200, self.state.requests
            if path == "/__stub/tokens":
                return 200, self.state.issued_tokens
        return 404, {"detail": "Not Found"}

    def _current_user(self) -> dict[str, Any] | None:
        auth = self.headers.get("Authorization") or ""
        if not auth.startswith("Bearer "):
            return None
        email = self.state.tokens.get(auth[len("Bearer ") :])
        return self.state.users.get(email) if email else None

    def _route(self, method: str, path: str, query: dict[str, list[str]], body: Any) -> tuple[int, Any]:
        if not path.startswith(API_PREFIX):
            return 404, {"error": "not found"}
        route = path[len(API_PREFIX) :]
        state = self.state

        if (method, route) == ("POST", "/auth/register"):
            if not isinstance(body, dict):
                return _error(400, "Bad Request", "Malformed request body")
            email = (body.get("email") or "").strip().lower()
            password = body.get("password") or ""
            display_name = body.get("displayName") or ""
            if not email or len(password) < 8 or not display_name:
                return _error(400, "Bad Request", "password: size must be between 8 and 128")
            if email in state.users:
                return _error(400, "Bad Request", "Email already registered")
            user = {"id": str(uuid.uuid4()), "email": email, "password": password, "displayName": display_name}
            state.users[email] = user
            return 201, state.issue(user)

        if (method, route) == ("POST", "/auth/login"):
            if not isinstance(body, dict):
                return _error(400, "Bad Request", "Malformed request body")
            user = state.users.get((body.get("email") or "").strip().lower())
            if user is None or user["password"] != body.get("password"):
                return _error(400, "Bad Request", "Invalid credentials")
            return 200, state.issue(user)

        if route in ("/documents", "/files"):
            user = self._current_user()
            if user is None:
                return 401, {"error": "missing or invalid authorization"}

            if (method, route) == ("GET", "/documents"):
                page = int(query.get("page", ["1"])[0])
                size = int(query.get("size", ["20"])[0])
                owned = [d for d in state.documents if d["owner_id"] == user["id"]]
                owned.sort(key=lambda d: d["updated_at"], reverse=True)
                start = (page - 1) * size
                return 200, {
                    "items": owned[start : start + size],
                    "total": len(owned),
                    "page": page,
                    "size": size,
                    "pages": max(1, -(-len(owned) // size)),
                }

            if (method, route) == ("POST", "/documents"):
                title = body.get("title") if isinstance(body, dict) else None
                if not title:
                    return 422, {"detail": [{"loc": ["body", "title"], "msg": "Field required", "type": "missing"}]}
                now = _pydantic_ts(state.next_time())
                doc = {
                    "id": str(uuid.uuid4()),
                    "title": title,
                    "content": body.get("content", ""),
                    "content_type": body.get("content_type", "text/markdown"),
                    "owner_id": user["id"],
                    "folder_id": None,
                    "is_deleted": False,
                    "is_template": False,
                    "word_count": 0,
                    "version": 1,
                    "created_at": now,
                    "updated_at": now,
                }
                state.documents.append(doc)
                return 201, doc

            if (method, route) == ("GET", "/files"):
                page = int(query.get("page", ["1"])[0])
                page_size = int(query.get("page_size", ["50"])[0])
                files = [
                    {
                        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, user["id"])),
                        "name": "welcome.txt",
                        "mime_type": "text/plain",
                        "size_bytes": 42,
                        "s3_key": f"{user['id']}/welcome.txt",
                        "folder_id": None,
                        "owner_id": user["id"],
                        "version": 1,
                        "is_trashed": False,
                        "created_at": _chrono_ts(FIXED_EPOCH),
                        "updated_at": _chrono_ts(FIXED_EPOCH),
                    }
                ]
                return 200, {"files": files, "total": len(files), "page": page, "page_size": page_size}

        return 404, {"error": "not found"}

    def _send(self, status: int, payload: Any) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class GatewayStub:
    """Runs the stub on a background thread; ``base_url`` is the client's ``apiBaseUrl``."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        self.state = StubState()
        handler = type("BoundHandler", (Handler,), {"state": self.state})
        self.server = ThreadingHTTPServer((host, port), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self.server.server_address[:2]
        return f"http://{host}:{port}{API_PREFIX}"

    @property
    def requests(self) -> list[dict[str, Any]]:
        with self.state.lock:
            return [dict(r) for r in self.state.requests]

    @property
    def issued_tokens(self) -> list[str]:
        with self.state.lock:
            return list(self.state.issued_tokens)

    def __enter__(self) -> GatewayStub:
        self.thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.server.shutdown()
        self.server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    stub = GatewayStub(args.host, args.port)
    print(f"gateway stub listening on {stub.base_url}", flush=True)
    stub.server.serve_forever()


if __name__ == "__main__":
    main()
