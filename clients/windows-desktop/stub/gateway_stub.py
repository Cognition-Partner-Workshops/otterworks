"""Local stand-in for the OtterWorks API gateway endpoints the desktop client calls.

Serves POST /auth/register, POST /auth/login, GET /documents, POST /documents and
GET /files under /api/v1 with the same JSON shapes as the real services (camelCase
for auth, snake_case for documents and files). State is in memory and resets on
restart. Extra read-only routes can be mounted from JSON files with --fixture, e.g.
--fixture /policies=policies.json, so an industry skin can add its own screens.

Every request and response is appended to --log as one JSON object per line, which
is what the before/after contract comparison reads.
"""

import argparse
import json
import secrets
import sys
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

PREFIX = "/api/v1"


class State:
    def __init__(self, fixtures, log_path):
        self.lock = threading.Lock()
        self.log_lock = threading.Lock()
        self.users = {}
        self.tokens = {}
        self.documents = {}
        self.fixtures = fixtures
        self.log_path = log_path


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def auth_payload(state, user):
    token = "stub." + secrets.token_urlsafe(24)
    state.tokens[token] = user["id"]
    return {
        "accessToken": token,
        "refreshToken": "stub-refresh." + secrets.token_urlsafe(16),
        "tokenType": "Bearer",
        "expiresIn": 3600,
        "user": {"id": user["id"], "email": user["email"], "displayName": user["displayName"]},
    }


def sample_files(owner_id):
    return [
        {"id": str(uuid.uuid5(uuid.NAMESPACE_URL, owner_id + "/f1")), "name": "quarterly-report.pdf",
         "size": 248113, "content_type": "application/pdf", "created_at": "2026-10-01T09:30:00Z"},
        {"id": str(uuid.uuid5(uuid.NAMESPACE_URL, owner_id + "/f2")), "name": "site-photo.jpg",
         "size": 1048576, "content_type": "image/jpeg", "created_at": "2026-10-02T14:05:12Z"},
    ]


class Handler(BaseHTTPRequestHandler):
    server_version = "OtterWorksGatewayStub/1.0"
    state = None

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.log_date_time_string(), fmt % args))

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            return raw.decode("utf-8"), (json.loads(raw) if raw else None)
        except ValueError:
            return raw.decode("utf-8", "replace"), None

    def _send(self, status, payload, request_record):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
        if self.state.log_path:
            request_record.update({"status": status, "response": payload})
            with self.state.log_lock, open(self.state.log_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(request_record) + "\n")

    def _user(self):
        header = self.headers.get("Authorization") or ""
        if not header.startswith("Bearer "):
            return None
        user_id = self.state.tokens.get(header[len("Bearer "):])
        if user_id is None:
            return None
        return next((u for u in self.state.users.values() if u["id"] == user_id), None)

    def _dispatch(self, method):
        url = urlsplit(self.path)
        query = {k: v[-1] for k, v in parse_qs(url.query).items()}
        raw, body = self._body() if method == "POST" else ("", None)
        record = {
            "method": method,
            "path": url.path,
            "query": query,
            "authorization": "Bearer <token>" if (self.headers.get("Authorization") or "").startswith("Bearer ") else None,
            "content_type": self.headers.get("Content-Type"),
            "body": body if body is not None else (raw or None),
        }
        if isinstance(body, dict) and "password" in body:
            record["body"] = dict(body, password="<redacted>")
        path = url.path
        if path == "/health":
            return self._send(200, {"status": "healthy", "service": "gateway-stub"}, record)
        if not path.startswith(PREFIX):
            return self._send(404, {"error": "not found"}, record)
        path = path[len(PREFIX):]
        st = self.state

        if method == "POST" and path == "/auth/register":
            if not isinstance(body, dict) or not all(body.get(k) for k in ("displayName", "email", "password")):
                return self._send(400, {"message": "displayName, email and password are required"}, record)
            if len(body["password"]) < 8:
                return self._send(400, {"message": "Password must be at least 8 characters"}, record)
            with st.lock:
                email = body["email"].strip().lower()
                if email in st.users:
                    return self._send(409, {"message": "An account with that email already exists"}, record)
                user = {"id": str(uuid.uuid4()), "email": email, "displayName": body["displayName"],
                        "password": body["password"]}
                st.users[email] = user
                return self._send(201, auth_payload(st, user), record)

        if method == "POST" and path == "/auth/login":
            if not isinstance(body, dict):
                return self._send(400, {"message": "email and password are required"}, record)
            with st.lock:
                user = st.users.get((body.get("email") or "").strip().lower())
                if user is None or user["password"] != body.get("password"):
                    return self._send(401, {"message": "Invalid email or password"}, record)
                return self._send(200, auth_payload(st, user), record)

        user = self._user()
        if user is None:
            return self._send(401, {"error": "missing or invalid bearer token"}, record)

        if method == "GET" and path == "/documents":
            page = max(int(query.get("page", 1)), 1)
            size = max(int(query.get("size", 20)), 1)
            with st.lock:
                docs = sorted((d for d in st.documents.values() if d["owner_id"] == user["id"]),
                              key=lambda d: d["updated_at"], reverse=True)
            items = docs[(page - 1) * size: page * size]
            pages = (len(docs) + size - 1) // size
            return self._send(200, {"items": items, "total": len(docs), "page": page, "size": size,
                                    "pages": pages}, record)

        if method == "POST" and path == "/documents":
            title = (body or {}).get("title") if isinstance(body, dict) else None
            if not title:
                return self._send(422, {"detail": "title is required"}, record)
            stamp = now_iso()
            doc = {"id": str(uuid.uuid4()), "title": title, "content": "", "content_type": "text/plain",
                   "owner_id": user["id"], "folder_id": None, "is_deleted": False, "word_count": 0,
                   "version": 1, "created_at": stamp, "updated_at": stamp}
            with st.lock:
                st.documents[doc["id"]] = doc
            return self._send(201, doc, record)

        if method == "GET" and path == "/files":
            page = max(int(query.get("page", 1)), 1)
            page_size = min(max(int(query.get("page_size", 50)), 1), 100)
            files = sample_files(user["id"])
            return self._send(200, {"files": files[(page - 1) * page_size: page * page_size],
                                    "total": len(files), "page": page, "page_size": page_size}, record)

        if method == "GET" and path in st.fixtures:
            return self._send(200, st.fixtures[path], record)

        return self._send(404, {"error": "not found"}, record)

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--log", help="append one JSON line per request/response")
    parser.add_argument("--fixture", action="append", default=[],
                        help="ROUTE=FILE: serve FILE as JSON at GET /api/v1ROUTE (bearer token required)")
    args = parser.parse_args()

    fixtures = {}
    for spec in args.fixture:
        route, _, file_name = spec.partition("=")
        with open(file_name, encoding="utf-8") as fh:
            fixtures["/" + route.strip("/")] = json.load(fh)

    Handler.state = State(fixtures, args.log)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print("gateway stub on http://%s:%d%s (fixtures: %s)" % (args.host, args.port, PREFIX,
          ", ".join(sorted(fixtures)) or "none"), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
