"""Local stand-in for the OtterWorks API gateway, covering only the endpoints the desktop
client calls. Response bodies and error shapes mirror the real services:

- auth-service: 201/200 AuthResponse; validation and bad credentials -> 400
  {timestamp, status, error, message}
- api-gateway JWT middleware: 401 {"error": "..."} for missing/invalid/expired tokens
- document-service: {items,total,page,size,pages}; validation -> 422 {"detail": [...]}
- file-service: {files,total,page,page_size} with mime_type/size_bytes fields

Control endpoints (not part of the real API):
  POST /__stub/expire-tokens   tokens issued so far are rejected as expired
  POST /__stub/seed-files      adds sample files for every user
  POST /__stub/reset           clears all state

Usage: python stub_gateway.py [--port 8080]
"""

import argparse
import json
import math
import secrets
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PREFIX = "/api/v1"

state = {"users": {}, "tokens": {}, "documents": [], "files": [], "expired_tokens": set()}


def is_well_formed_email(email):
    if email.count("@") != 1 or any(c.isspace() for c in email):
        return False
    local, domain = email.split("@")
    return bool(local) and "." in domain[1:-1]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def auth_error(status, reason, message):
    return status, {"timestamp": now_iso(), "status": status, "error": reason, "message": message}


def issue_tokens(user):
    token = "stub." + secrets.token_urlsafe(24)
    state["tokens"][token] = user["id"]
    return {
        "accessToken": token,
        "refreshToken": "refresh." + secrets.token_urlsafe(24),
        "tokenType": "Bearer",
        "expiresIn": 3600,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "displayName": user["displayName"],
            "avatarUrl": None,
        },
    }


def register(body):
    errors = []
    email = (body.get("email") or "").strip()
    password = body.get("password") or ""
    display = (body.get("displayName") or "").strip()
    if not email:
        errors.append("email: must not be blank")
    elif not is_well_formed_email(email):
        errors.append("email: must be a well-formed email address")
    if not password:
        errors.append("password: must not be blank")
    elif not 8 <= len(password) <= 128:
        errors.append("password: size must be between 8 and 128")
    if not display:
        errors.append("displayName: must not be blank")
    elif len(display) > 100:
        errors.append("displayName: size must be between 1 and 100")
    if errors:
        return auth_error(400, "Bad Request", ", ".join(errors))
    if email.lower() in state["users"]:
        return auth_error(400, "Bad Request", "Email already registered")
    user = {"id": str(uuid.uuid4()), "email": email, "password": password, "displayName": display}
    state["users"][email.lower()] = user
    return 201, issue_tokens(user)


def login(body):
    email = (body.get("email") or "").strip()
    password = body.get("password") or ""
    if not email or not is_well_formed_email(email) or not password:
        return auth_error(400, "Bad Request", "email: must be a well-formed email address")
    user = state["users"].get(email.lower())
    if not user or user["password"] != password:
        return auth_error(400, "Bad Request", "Invalid credentials")
    return 200, issue_tokens(user)


def require_user(headers):
    auth = headers.get("Authorization") or ""
    if not auth.startswith("Bearer "):
        return None, (401, {"error": "missing or invalid authorization header"})
    token = auth[len("Bearer "):]
    if token in state["expired_tokens"] or token not in state["tokens"]:
        return None, (401, {"error": "invalid token: token has invalid claims: token is expired"})
    return state["tokens"][token], None


def list_documents(user_id, query):
    page = max(int(query.get("page", ["1"])[0]), 1)
    size = min(max(int(query.get("size", ["20"])[0]), 1), 100)
    mine = [d for d in state["documents"] if d["owner_id"] == user_id and not d["is_deleted"]]
    mine.sort(key=lambda d: d["updated_at"], reverse=True)
    start = (page - 1) * size
    return 200, {
        "items": mine[start:start + size],
        "total": len(mine),
        "page": page,
        "size": size,
        "pages": max(math.ceil(len(mine) / size), 1),
    }


def create_document(user_id, body):
    title = body.get("title")
    if not isinstance(title, str) or len(title) < 1:
        return 422, {"detail": [{"type": "string_too_short", "loc": ["body", "title"],
                                 "msg": "String should have at least 1 character",
                                 "input": title, "ctx": {"min_length": 1}}]}
    if len(title) > 500:
        return 422, {"detail": [{"type": "string_too_long", "loc": ["body", "title"],
                                 "msg": "String should have at most 500 characters",
                                 "input": title, "ctx": {"max_length": 500}}]}
    ts = now_iso()
    doc = {
        "id": str(uuid.uuid4()), "title": title, "content": "", "content_type": "text/markdown",
        "owner_id": user_id, "folder_id": None, "is_deleted": False, "is_template": False,
        "word_count": 0, "version": 1, "created_at": ts, "updated_at": ts,
    }
    state["documents"].append(doc)
    return 201, doc


def list_files(user_id, query):
    page = max(int(query.get("page", ["1"])[0]), 1)
    page_size = min(int(query.get("page_size", ["50"])[0]), 100)
    mine = [f for f in state["files"] if f["owner_id"] == user_id and not f["is_trashed"]]
    start = (page - 1) * page_size
    return 200, {"files": mine[start:start + page_size], "total": len(mine),
                 "page": page, "page_size": page_size}


def seed_files():
    samples = [("Quarterly report.pdf", "application/pdf", 482113),
               ("Team photo.png", "image/png", 1830442),
               ("Budget.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 23011)]
    for user in state["users"].values():
        for name, mime, size in samples:
            ts = now_iso()
            state["files"].append({
                "id": str(uuid.uuid4()), "name": name, "mime_type": mime, "size_bytes": size,
                "s3_key": f"{user['id']}/{name}", "folder_id": None, "owner_id": user["id"],
                "version": 1, "is_trashed": False, "created_at": ts, "updated_at": ts,
            })
    return 200, {"seeded": len(state["files"])}


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, payload):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except ValueError:
            return {}

    def _route(self, method):
        url = urlparse(self.path)
        path, query = url.path.rstrip("/"), parse_qs(url.query)
        if method == "GET" and path == "/health":
            return 200, {"status": "healthy", "service": "gateway-stub"}
        if method == "POST" and path == "/__stub/expire-tokens":
            state["expired_tokens"].update(state["tokens"])
            return 200, {"expired": len(state["expired_tokens"])}
        if method == "POST" and path == "/__stub/seed-files":
            return seed_files()
        if method == "POST" and path == "/__stub/reset":
            state.update(users={}, tokens={}, documents=[], files=[], expired_tokens=set())
            return 200, {"reset": True}
        if method == "POST" and path == PREFIX + "/auth/register":
            return register(self._body())
        if method == "POST" and path == PREFIX + "/auth/login":
            return login(self._body())
        if path in (PREFIX + "/documents", PREFIX + "/files"):
            user_id, err = require_user(self.headers)
            if err:
                return err
            if path.endswith("/documents"):
                return list_documents(user_id, query) if method == "GET" \
                    else create_document(user_id, self._body())
            if method == "GET":
                return list_files(user_id, query)
        return 404, {"error": "not found"}

    def do_GET(self):
        self._send(*self._route("GET"))

    def do_POST(self):
        self._send(*self._route("POST"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"gateway stub listening on http://127.0.0.1:{args.port}{PREFIX}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
