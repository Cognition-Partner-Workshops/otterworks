"""HTTP server for the mock workspace (stdlib only).

The browser authenticates with a server-held access token exchanged for an HMAC cookie.
It can only choose a channel, a thread, a local display persona and message text; org ids,
Devin user ids and API payloads are server configuration.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import signal
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from typing import Any
from urllib.parse import parse_qs, urlsplit

from .bridge import Bridge
from .config import MAX_BODY_BYTES, MAX_MESSAGE_CHARS, Config, ConfigError, load_config
from .db import Store

log = logging.getLogger("collection_slack.server")

COOKIE = "collection_slack"
CLIENT_ID_RE = re.compile(r"^[A-Za-z0-9\-]{8,64}$")
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}
STATIC = {"app.js": "text/javascript", "app.css": "text/css"}


class RedactingFilter(logging.Filter):
    def __init__(self, secrets_: list[str]) -> None:
        super().__init__()
        self._secrets = [s for s in secrets_ if s]

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        for s in self._secrets:
            msg = msg.replace(s, "[redacted]")
        record.msg, record.args = msg, None
        return True


def _static(name: str) -> bytes:
    return resources.files("collection_slack").joinpath("static", name).read_bytes()


class App:
    def __init__(self, config: Config, bridge: Bridge | None = None) -> None:
        self.config = config
        self.store = Store(config.db_path)
        self.bridge = bridge or Bridge(config, self.store)
        self.bridge.store = self.store

    def make_cookie(self) -> str:
        nonce = secrets.token_urlsafe(18)
        sig = hmac.new(self.config.cookie_secret, nonce.encode(), hashlib.sha256).digest()
        return f"{nonce}.{base64.urlsafe_b64encode(sig).decode().rstrip('=')}"

    def cookie_ok(self, value: str | None) -> bool:
        if not value or "." not in value:
            return False
        nonce, _, sig = value.partition(".")
        want = (
            base64.urlsafe_b64encode(hmac.new(self.config.cookie_secret, nonce.encode(), hashlib.sha256).digest())
            .decode()
            .rstrip("=")
        )
        return hmac.compare_digest(sig, want)

    def token_ok(self, candidate: str) -> bool:
        return hmac.compare_digest(candidate.encode(), self.config.access_token.encode())


class ApiError(Exception):
    def __init__(self, status: int, message: str) -> None:
        self.status = status
        super().__init__(message)


def _validate(body: Any, allowed: set[str], required: set[str]) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise ApiError(400, "expected a JSON object")
    extra = set(body) - allowed
    if extra:
        raise ApiError(400, "unsupported fields: " + ", ".join(sorted(extra)))
    missing = required - set(body)
    if missing:
        raise ApiError(400, "missing fields: " + ", ".join(sorted(missing)))
    return body


def make_handler(app: App) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "collection-slack"
        sys_version = ""

        def log_message(self, fmt: str, *args: Any) -> None:
            log.info("%s %s", self.command, urlsplit(self.path).path)

        # ---- helpers ------------------------------------------------------
        def _send(self, status: int, body: bytes, ctype: str, extra: dict[str, str] | None = None) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            for k, v in {**SECURITY_HEADERS, **(extra or {})}.items():
                self.send_header(k, v)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, status: int, obj: Any) -> None:
            self._send(status, json.dumps(obj).encode(), "application/json")

        def _cookie(self) -> str | None:
            for part in (self.headers.get("Cookie") or "").split(";"):
                k, _, v = part.strip().partition("=")
                if k == COOKIE:
                    return v
            return None

        def _authed(self) -> bool:
            return app.cookie_ok(self._cookie())

        def _same_origin(self) -> bool:
            origin = self.headers.get("Origin")
            if origin is None:
                return True
            return urlsplit(origin).netloc == self.headers.get("Host")

        def _read_body(self) -> bytes:
            try:
                length = int(self.headers.get("Content-Length") or "0")
            except ValueError as exc:
                raise ApiError(400, "bad length") from exc
            if length > MAX_BODY_BYTES:
                raise ApiError(413, "request too large")
            return self.rfile.read(length) if length else b""

        def _read_json(self) -> Any:
            if (self.headers.get("Content-Type") or "").split(";")[0].strip() != "application/json":
                raise ApiError(415, "expected application/json")
            if self.headers.get("X-Collection-Client") != "1" or not self._same_origin():
                raise ApiError(403, "cross-site request refused")
            try:
                return json.loads(self._read_body() or b"null")
            except ValueError as exc:
                raise ApiError(400, "invalid JSON") from exc

        # ---- routing ------------------------------------------------------
        def do_HEAD(self) -> None:  # noqa: N802
            self.do_GET()

        def do_GET(self) -> None:  # noqa: N802
            path = urlsplit(self.path).path
            try:
                if path == "/healthz":
                    return self._json(200, health(app))
                if path == "/metrics":
                    return self._send(200, metrics(app).encode(), "text/plain; version=0.0.4")
                if path == "/login":
                    return self._send(200, _static("login.html"), "text/html; charset=utf-8")
                if path.startswith("/static/"):
                    name = path.removeprefix("/static/")
                    if name not in STATIC:
                        raise ApiError(404, "not found")
                    return self._send(200, _static(name), STATIC[name])
                if not self._authed():
                    if path.startswith("/api/"):
                        raise ApiError(401, "login required")
                    return self._send(303, b"", "text/plain", {"Location": "/login"})
                if path == "/":
                    return self._send(200, _static("index.html"), "text/html; charset=utf-8")
                return self._json(200, api_get(app, path, urlsplit(self.path).query))
            except ApiError as exc:
                self._json(exc.status, {"error": str(exc)})

        def do_POST(self) -> None:  # noqa: N802
            path = urlsplit(self.path).path
            try:
                if path == "/login":
                    if not self._same_origin():
                        raise ApiError(403, "cross-site request refused")
                    form = parse_qs(self._read_body().decode("utf-8", "replace"))
                    token = (form.get("token") or [""])[0]
                    if not app.token_ok(token):
                        return self._send(303, b"", "text/plain", {"Location": "/login?error=1"})
                    cookie = f"{COOKIE}={app.make_cookie()}; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200"
                    return self._send(303, b"", "text/plain", {"Location": "/", "Set-Cookie": cookie})
                if path == "/logout":
                    cookie = f"{COOKIE}=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0"
                    return self._send(303, b"", "text/plain", {"Location": "/login", "Set-Cookie": cookie})
                if not self._authed():
                    raise ApiError(401, "login required")
                status, obj = api_post(app, path, self._read_json())
                self._json(status, obj)
            except ApiError as exc:
                self._json(exc.status, {"error": str(exc)})

    return Handler


_CH_THREADS = re.compile(r"^/api/channels/(\d+)/threads$")
_THREAD = re.compile(r"^/api/threads/(\d+)$")
_THREAD_MSGS = re.compile(r"^/api/threads/(\d+)/messages$")


def health(app: App) -> dict[str, Any]:
    try:
        app.store.one("SELECT 1")
        db = "ok"
    except Exception:  # noqa: BLE001
        db = "error"
    return {
        "status": "ok" if db == "ok" else "degraded",
        "db": db,
        "mode": app.config.mode,
        "api_target": app.config.api_target,
        "automation": "configured" if app.config.automation_enabled else "off",
    }


def metrics(app: App) -> str:
    lines = [f'collection_slack_up{{mode="{app.config.mode}"}} 1']
    for name in sorted(
        {
            "messages_total",
            "sessions_created_total",
            "forwards_total",
            "devin_messages_total",
            "automation_posts_total",
            "http_failures_total",
            "verification_failures_total",
            "stub_replies_total",
        }
        | set(app.bridge.metrics)
    ):
        lines.append(f"collection_slack_{name} {app.bridge.metrics.get(name, 0)}")
    return "\n".join(lines) + "\n"


def _session_view(app: App, thread_id: int) -> dict[str, Any] | None:
    s = app.store.session_for(thread_id)
    if s is None:
        return None
    out: dict[str, Any] = {"state": s["state"]}
    if s["state"] == "active" and app.config.live:
        out["url"] = s["session_url"]
    if s["state"] in ("failed", "rejected", "interrupted"):
        out["detail"] = s["detail"]
    return out


def api_get(app: App, path: str, query: str) -> dict[str, Any]:
    if path == "/api/bootstrap":
        return {
            "mode": app.config.mode,
            "api_target": app.config.api_target,
            "users": app.store.users(),
            "channels": app.store.channels(),
            "max_message_chars": MAX_MESSAGE_CHARS,
        }
    if m := _CH_THREADS.match(path):
        cid = int(m.group(1))
        if app.store.channel(cid) is None:
            raise ApiError(404, "no such channel")
        return {"threads": app.store.thread_summaries(cid)}
    if m := _THREAD.match(path):
        tid = int(m.group(1))
        if app.store.thread(tid) is None:
            raise ApiError(404, "no such thread")
        after = (parse_qs(query).get("after") or ["0"])[0]
        return {
            "thread_id": tid,
            "messages": app.store.messages(tid, int(after) if after.isdigit() else 0),
            "session": _session_view(app, tid),
        }
    raise ApiError(404, "not found")


def _clean_post(app: App, body: Any) -> tuple[str, str, str]:
    data = _validate(body, {"author", "text", "client_msg_id"}, {"author", "text", "client_msg_id"})
    author, text, cid = data["author"], data["text"], data["client_msg_id"]
    if not isinstance(author, str) or author not in app.store.human_handles():
        raise ApiError(400, "unknown author")
    if not isinstance(text, str) or not text.strip():
        raise ApiError(400, "text required")
    if len(text) > MAX_MESSAGE_CHARS:
        raise ApiError(413, f"message longer than {MAX_MESSAGE_CHARS} characters")
    if not isinstance(cid, str) or not CLIENT_ID_RE.match(cid):
        raise ApiError(400, "bad client_msg_id")
    return author, text.strip(), cid


def api_post(app: App, path: str, body: Any) -> tuple[int, dict[str, Any]]:
    if m := _CH_THREADS.match(path):
        cid = int(m.group(1))
        ch = app.store.channel(cid)
        if ch is None:
            raise ApiError(404, "no such channel")
        author, text, client_id = _clean_post(app, body)
        tid, mid, created = app.store.create_thread(cid, author, text, client_id)
        route = app.bridge.on_user_message(tid, mid, ch["name"], text) if created else "replay"
        return (201 if created else 200), {"thread_id": tid, "message_id": mid, "route": route}
    if m := _THREAD_MSGS.match(path):
        tid = int(m.group(1))
        thread = app.store.thread(tid)
        if thread is None:
            raise ApiError(404, "no such thread")
        ch = app.store.channel(thread["channel_id"])
        author, text, client_id = _clean_post(app, body)
        mid, created = app.store.add_user_message(tid, author, text, client_id)
        route = app.bridge.on_user_message(tid, mid, ch["name"] if ch else "", text) if created else "replay"
        return (201 if created else 200), {"thread_id": tid, "message_id": mid, "route": route}
    raise ApiError(404, "not found")


def build_server(app: App) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((app.config.bind_host, app.config.port), make_handler(app))
    server.daemon_threads = True
    return server


def configure_logging(config: Config) -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    handler.addFilter(RedactingFilter([config.devin_api_key or "", config.access_token, config.automation_secret or ""]))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(os.environ.get("COLLECTION_LOG_LEVEL", "INFO"))


def main() -> int:
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2
    configure_logging(config)
    app = App(config)
    app.bridge.start()
    server = build_server(app)
    stop = threading.Event()

    def _shutdown(*_: object) -> None:
        if not stop.is_set():
            stop.set()
            threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)
    log.info("listening on %s:%s mode=%s", config.bind_host, server.server_address[1], config.mode)
    server.serve_forever()
    app.bridge.stop()
    app.store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
