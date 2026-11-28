#!/usr/bin/env python3
"""Local stand-in for the legacy-portal-serverless HTTP API (API Gateway, payload format 2.0).

Routes mirror infrastructure/terraform/legacy-portal-serverless/api.tf: `ANY <prefix>` and
`ANY <prefix>/{proxy+}` per context, and `$default` to LP_DEFAULT_ROUTE. Each request becomes a
payload 2.0 proxy event and is invoked on that context's function container, which runs the real
Java handler under the AWS Lambda Runtime Interface Emulator. The proxy response is mapped back to
HTTP the way API Gateway does it. x-lp-local-function names the function that answered.

  LP_ROUTES="announcements=/api/announcements=http://fn-announcements:8080;..."
  LP_DEFAULT_ROUTE=announcements
"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

INVOKE_PATH = "/2015-03-31/functions/function/invocations"
TIMEOUT = float(os.environ.get("LP_INTEGRATION_TIMEOUT", "29"))
TEXT_TYPES = ("application/json", "application/xml", "application/javascript",
              "application/x-www-form-urlencoded")


def load_routes():
    routes = []
    for item in filter(None, os.environ["LP_ROUTES"].split(";")):
        name, prefix, url = item.split("=", 2)
        routes.append((name.strip(), prefix.strip().rstrip("/"), url.strip().rstrip("/")))
    return routes


ROUTES = load_routes()
FUNCTIONS = {name: url for name, _, url in ROUTES}
DEFAULT = os.environ.get("LP_DEFAULT_ROUTE", ROUTES[0][0])


def match(path):
    for name, prefix, _ in ROUTES:
        if path == prefix:
            return name, f"ANY {prefix}", None
        if path.startswith(prefix + "/") and len(path) > len(prefix) + 1:
            return name, f"ANY {prefix}/{{proxy+}}", {"proxy": path[len(prefix) + 1:]}
    return DEFAULT, "$default", None


def is_text(content_type):
    media = (content_type or "").split(";")[0].strip().lower()
    return media.startswith("text/") or media in TEXT_TYPES or media.endswith("+json") or media.endswith("+xml")


def build_event(method, target, headers, body, route_key, path_params, source_ip):
    split = urllib.parse.urlsplit(target)
    raw_path, raw_query = split.path, split.query
    hdrs = {}
    for k, v in headers.items():
        k = k.lower()
        hdrs[k] = f"{hdrs[k]},{v}" if k in hdrs else v
    now = datetime.now(timezone.utc)
    event = {
        "version": "2.0",
        "routeKey": route_key,
        "rawPath": raw_path,
        "rawQueryString": raw_query,
        "headers": hdrs,
        "requestContext": {
            "accountId": "000000000000",
            "apiId": "local",
            "domainName": hdrs.get("host", "localhost"),
            "domainPrefix": hdrs.get("host", "localhost").split(".")[0],
            "http": {"method": method, "path": raw_path, "protocol": "HTTP/1.1",
                     "sourceIp": source_ip, "userAgent": hdrs.get("user-agent", "")},
            "requestId": str(uuid.uuid4()),
            "routeKey": route_key,
            "stage": "$default",
            "time": now.strftime("%d/%b/%Y:%H:%M:%S +0000"),
            "timeEpoch": int(now.timestamp() * 1000),
        },
        "isBase64Encoded": False,
    }
    if "cookie" in hdrs:
        event["cookies"] = [c.strip() for c in hdrs["cookie"].split(";")]
    if raw_query:
        params = {}
        for k, v in urllib.parse.parse_qsl(raw_query, keep_blank_values=True):
            params[k] = f"{params[k]},{v}" if k in params else v
        event["queryStringParameters"] = params
    if path_params:
        event["pathParameters"] = path_params
    if body:
        try:
            text = body.decode("utf-8") if is_text(hdrs.get("content-type")) else None
        except UnicodeDecodeError:
            text = None
        if text is None:
            event["body"], event["isBase64Encoded"] = base64.b64encode(body).decode(), True
        else:
            event["body"] = text
    return event


def invoke(function, event):
    req = urllib.request.Request(FUNCTIONS[function] + INVOKE_PATH, data=json.dumps(event).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read() or b"null")


def to_http(output):
    """API Gateway's mapping of a payload 2.0 function result."""
    if isinstance(output, dict) and "errorType" in output and "statusCode" not in output:
        return 500, {"Content-Type": "application/json"}, b'{"message":"Internal Server Error"}', []
    if not isinstance(output, dict) or "statusCode" not in output:
        return 200, {"Content-Type": "application/json"}, json.dumps(output).encode(), []
    body = output.get("body") or ""
    data = base64.b64decode(body) if output.get("isBase64Encoded") else body.encode("utf-8")
    return int(output["statusCode"]), dict(output.get("headers") or {}), data, output.get("cookies") or []


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "lp-local-gateway"

    def _handle(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        path = urllib.parse.urlsplit(self.path).path
        if path == "/__lp_local/identity" and self.command == "GET":
            return self._send(200, {"Content-Type": "application/json"}, json.dumps({
                "endpoint": "lambda-local", "runToken": os.environ.get("RUN_TOKEN", ""),
                "routes": [{"function": n, "prefix": p} for n, p, _ in ROUTES], "default": DEFAULT,
            }).encode(), [], "-")
        function, route_key, path_params = match(path)
        event = build_event(self.command, self.path, dict(self.headers.items()), body, route_key, path_params,
                            self.client_address[0])
        started = time.monotonic()
        try:
            status, headers, data, cookies = to_http(invoke(function, event))
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            print(f"integration error {function}: {e}", file=sys.stderr, flush=True)
            status, headers, data, cookies = 500, {"Content-Type": "application/json"}, \
                b'{"message":"Internal Server Error"}', []
        headers["apigw-requestid"] = event["requestContext"]["requestId"]
        print(f"{self.command} {self.path[:100]} -> {function} ({route_key}) {status} "
              f"{round((time.monotonic() - started) * 1000)}ms", flush=True)
        self._send(status, headers, data, cookies, function)

    def _send(self, status, headers, data, cookies, function):
        self.send_response(status)
        for k, v in headers.items():
            if k.lower() not in ("content-length", "connection", "transfer-encoding"):
                self.send_header(k, v)
        for c in cookies:
            self.send_header("Set-Cookie", c)
        self.send_header("x-lp-local-function", function)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = do_HEAD = do_OPTIONS = _handle

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    print(f"lp-local gateway on :{port}; routes {ROUTES}; $default -> {DEFAULT}", file=sys.stderr, flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
