import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def issue_key(body):
    try:
        key = json.loads(body)["issue"]["key"]
    except (ValueError, KeyError, TypeError):
        return "-"
    return key if isinstance(key, str) and re.fullmatch(r"[A-Z0-9_]+-[0-9]+", key) else "-"


class Relay(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def reply(self, status):
        self.send_response(status)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        self.reply(200 if self.path == "/health" else 404)

    def do_POST(self):
        if self.path != "/webhook":
            self.reply(404)
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self.reply(411)
            return
        if not 0 <= length <= 4 * 1024 * 1024:
            self.reply(413)
            return
        try:
            self.connection.settimeout(10)
            body = self.rfile.read(length)
        except TimeoutError:
            self.reply(408)
            return
        if len(body) != length:
            self.reply(400)
            return
        request = Request(self.server.upstream_url, data=body, headers={
            "Content-Type": self.headers.get("Content-Type", "application/json"),
            "X-Webhook-Secret": self.server.upstream_secret,
        })
        try:
            with build_opener(NoRedirect()).open(request, timeout=10) as response:
                status = response.status
        except HTTPError as error:
            status = error.code
            error.close()
        except (URLError, OSError, ValueError):
            status = None
        print(f"issue={issue_key(body)} upstream_status={status if status is not None else 'unavailable'}",
              flush=True)
        self.reply(status if status is not None and 200 <= status < 300 else 502)


def main():
    url = os.environ.get("DEVIN_JIRA_WEBHOOK_URL", "")
    secret = os.environ.get("DEVIN_JIRA_WEBHOOK_SECRET", "")
    try:
        target = urlsplit(url)
        valid = target.scheme == "https" and target.hostname and secret and "\r" not in secret and "\n" not in secret
    except ValueError:
        valid = False
    if not valid:
        raise SystemExit("An HTTPS upstream URL and webhook secret are required")
    with ThreadingHTTPServer(("", 8080), Relay) as server:
        server.upstream_url = url
        server.upstream_secret = secret
        server.serve_forever()


if __name__ == "__main__":
    main()
