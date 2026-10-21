"""Stand-in for the platform's oauth2-proxy auth endpoint, for the kind check in run.sh only.

Models what ingress-nginx relies on: GET /oauth2/auth answers 401 without a session, 403 when the session's
groups miss allowed_groups (split on commas, as oauth2-proxy's extractAllowedEntities does) and 202 with
X-Auth-Request-User otherwise. The "session" is a test cookie _oauth2_proxy=<user>|<group>[;<group>...].
"""
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == "/oauth2/start":
            return self._reply(200, b"sign-in page\n")
        if url.path != "/oauth2/auth":
            return self._reply(404, b"")
        cookie = SimpleCookie(self.headers.get("Cookie", "")).get("_oauth2_proxy")
        if cookie is None:
            return self._reply(401, b"")
        user, _, groups = cookie.value.partition("|")
        allowed = {g for v in parse_qs(url.query).get("allowed_groups", []) for g in v.split(",") if g}
        if allowed and not allowed & set(groups.split(";")):
            return self._reply(403, b"")
        self._reply(202, b"", {"X-Auth-Request-User": user})

    def _reply(self, status, body, headers=None):
        self.send_response(status)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


ThreadingHTTPServer(("", 4180), Handler).serve_forever()
