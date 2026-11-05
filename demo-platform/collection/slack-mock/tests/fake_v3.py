"""FAKE Devin v3 API for tests and local validation. It never talks to the real service."""

from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlsplit

_SESS = re.compile(r"^/v3/organizations/([^/]+)/sessions(?:/([^/]+)(?:/(messages|archive))?)?$")


@dataclass
class Recorded:
    method: str
    path: str
    headers: dict[str, str]
    body: Any


@dataclass
class FakeV3:
    api_key: str
    org_id: str
    requests: list[Recorded] = field(default_factory=list)
    sessions: dict[str, dict[str, Any]] = field(default_factory=dict)
    events: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    fail: dict[str, int] = field(default_factory=dict)
    delay: dict[str, float] = field(default_factory=dict)
    override_user_id: str | None = None
    override_mode: str | None = None
    create_delay: float = 0.0
    page_size: int = 2
    lock: threading.Lock = field(default_factory=threading.Lock)
    webhook_secret: str | None = None
    webhook_posts: list[Recorded] = field(default_factory=list)
    auto_reply: bool = False
    _server: ThreadingHTTPServer | None = None

    @property
    def base(self) -> str:
        assert self._server is not None
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def start(self) -> FakeV3:
        self._server = _QuietServer(("127.0.0.1", 0), _make_handler(self))
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        return self

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()

    def add_event(self, sid: str, source: str, message: str) -> None:
        with self.lock:
            evs = self.events[sid]
            evs.append(
                {
                    "event_id": f"evt-{sid[-6:]}-{len(evs)}",
                    "source": source,
                    "message": message,
                    "created_at": int(time.time()),
                }
            )

    def calls(self, method: str, suffix: str) -> list[Recorded]:
        with self.lock:
            return [r for r in self.requests if r.method == method and urlsplit(r.path).path.endswith(suffix)]


class _QuietServer(ThreadingHTTPServer):
    def handle_error(self, request: Any, client_address: Any) -> None:
        return  # client timeouts in failure tests close sockets early


def _make_handler(fake: FakeV3) -> type[BaseHTTPRequestHandler]:
    class H(BaseHTTPRequestHandler):
        def log_message(self, *_: Any) -> None:
            return

        def _reply(self, status: int, obj: Any) -> None:
            raw = json.dumps(obj).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _handle(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            body: Any = json.loads(raw) if raw else {}
            rec = Recorded(self.command, self.path, dict(self.headers.items()), body)
            path = urlsplit(self.path).path
            if path == "/webhook":
                fake.webhook_posts.append(rec)
                if self.headers.get("X-Webhook-Secret") != fake.webhook_secret:
                    return self._reply(401, {"detail": "bad secret"})
                return self._reply(fake.fail.get("webhook", 200), {"ok": True})
            with fake.lock:
                fake.requests.append(rec)
            if self.headers.get("Authorization") != f"Bearer {fake.api_key}":
                return self._reply(401, {"detail": "unauthorized"})
            m = _SESS.match(path)
            if not m or m.group(1) != fake.org_id:
                return self._reply(404, {"detail": "not found"})
            sid, sub = m.group(2), m.group(3)
            label = {
                ("POST", None, None): "create",
                ("GET", True, None): "get",
                ("POST", True, "messages"): "send",
                ("GET", True, "messages"): "list",
                ("POST", True, "archive"): "archive",
            }.get((self.command, True if sid else None, sub), "other")
            time.sleep(fake.delay.get(label, 0.0))
            if label in fake.fail:
                return self._reply(fake.fail[label], {"detail": "injected failure", "error_code": "fake_error"})
            if label == "create":
                with fake.lock:
                    n = len(fake.sessions) + 1
                    new_id = f"devin-{n:032x}"
                    fake.sessions[new_id] = {
                        "session_id": new_id,
                        "org_id": fake.org_id,
                        "user_id": body.get("create_as_user_id"),
                        "devin_mode": body.get("devin_mode"),
                        "acus_consumed": 0.5 * n,
                        "status": "running",
                        "url": f"https://fake-devin.invalid/sessions/{new_id}",
                    }
                    fake.events[new_id] = []
                if fake.auto_reply:
                    fake.add_event(new_id, "devin", f"FAKE v3 reply: fake session {new_id[-6:]} received the mention.")
                return self._reply(200, fake.sessions[new_id])
            if sid not in fake.sessions:
                return self._reply(404, {"detail": "no session"})
            if label == "get":
                data = dict(fake.sessions[sid])
                if fake.override_user_id is not None:
                    data["user_id"] = fake.override_user_id
                if fake.override_mode is not None:
                    data["devin_mode"] = fake.override_mode
                return self._reply(200, data)
            if label == "send":
                fake.add_event(sid, "user", body["message"])
                if fake.auto_reply:
                    fake.add_event(sid, "devin", f"FAKE v3 reply: received {body['message'][:120]!r}")
                return self._reply(200, fake.sessions[sid])
            if label == "archive":
                fake.sessions[sid]["status"] = "archived"
                return self._reply(200, fake.sessions[sid])
            if label == "list":
                q = parse_qs(urlsplit(self.path).query)
                start = int((q.get("after") or ["-1"])[0]) + 1
                first = min(int((q.get("first") or ["100"])[0]), fake.page_size)
                evs = fake.events[sid]
                items = evs[start : start + first]
                end = start + len(items) - 1
                return self._reply(
                    200,
                    {
                        "items": items,
                        "end_cursor": str(end) if items else None,
                        "has_next_page": end + 1 < len(evs),
                    },
                )
            return self._reply(404, {"detail": "unsupported"})

        do_GET = _handle  # noqa: N815
        do_POST = _handle  # noqa: N815

    return H


def main() -> int:
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Run the FAKE Devin v3 API on loopback (auto-replies, no real sessions).")
    parser.add_argument("--port", type=int, default=8781)
    args = parser.parse_args()
    fake = FakeV3(
        api_key=os.environ["FAKE_V3_API_KEY"],
        org_id=os.environ["FAKE_V3_ORG_ID"],
        auto_reply=True,
        page_size=50,
        webhook_secret=os.environ.get("FAKE_V3_WEBHOOK_SECRET"),
    )
    fake._server = _QuietServer(("127.0.0.1", args.port), _make_handler(fake))
    print(f"FAKE v3 API listening on http://127.0.0.1:{args.port} (not the real Devin API)", flush=True)
    try:
        fake._server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
