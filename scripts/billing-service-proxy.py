#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["boto3==1.35.99"]
# ///
"""Serve the in-VPC billing-service function on a local port.

``otterworks-postgres-dev`` only accepts connections from inside its VPC, so the
billing-data Terraform root runs billing-service as the function
``<token>-billing-service`` in the instance's private subnets, with no inbound
path. This proxy listens on 127.0.0.1 only and turns every HTTP request into an
API Gateway HTTP API (2.0) event sent with ``lambda:Invoke``, so the procs
harness can treat it like any other ``BILLING_SVC_URL``:

    source <(cloudworker/assume.sh engineer devin-<session>)
    uv run scripts/billing-service-proxy.py --token lp-20261006-bd --port 18097 \\
        --allow-internal-reset &
    make procs-parity NS=dev MODULE=rating BILLING_SVC_URL=http://127.0.0.1:18097

The run's login credentials (``otterworks-<token>/billing-db``) are read once at
start and travel only in the invocation payload; they are never printed.
``--allow-internal-reset`` lets ``POST /internal/reset`` rewrite the run
database (the harness needs it); rerun ``scripts/billing-to-rds.py`` afterwards.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import boto3


def event_for(method: str, target: str, headers: dict[str, str], body: bytes) -> dict:
    parts = urlsplit(target)
    return {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": parts.path or "/",
        "rawQueryString": parts.query,
        "headers": {key.lower(): value for key, value in headers.items()},
        "requestContext": {
            "http": {"method": method, "path": parts.path or "/", "protocol": "HTTP/1.1",
                     "sourceIp": "127.0.0.1", "userAgent": headers.get("User-Agent", "")},
            "requestId": str(uuid.uuid4()),
            "routeKey": "$default",
            "stage": "$default",
        },
        "body": base64.b64encode(body).decode() if body else None,
        "isBase64Encoded": bool(body),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--token", required=True, help="run token, e.g. lp-20261006-bd")
    parser.add_argument("--function", help="function name (default: <token>-billing-service)")
    parser.add_argument("--port", type=int, default=18097)
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--allow-internal-reset", action="store_true",
                        help="let POST /internal/reset rewrite the run database")
    args = parser.parse_args()
    function = args.function or f"{args.token}-billing-service"

    session = boto3.Session(region_name=args.region)
    db = json.loads(session.client("secretsmanager").get_secret_value(
        SecretId=f"otterworks-{args.token}/billing-db")["SecretString"])
    lam = session.client("lambda")

    def invoke(method: str, target: str, headers: dict[str, str], body: bytes) -> tuple[int, dict, bytes]:
        payload = {"db": db, "allow_internal_reset": args.allow_internal_reset,
                   "http": event_for(method, target, headers, body)}
        response = lam.invoke(FunctionName=function, Payload=json.dumps(payload).encode())
        result = json.loads(response["Payload"].read() or b"null")
        if response.get("FunctionError") or not isinstance(result, dict):
            message = result.get("errorMessage") if isinstance(result, dict) else "no response"
            return 502, {"content-type": "application/json"}, json.dumps(
                {"detail": f"function error: {message}"}).encode()
        raw = result.get("body") or ""
        data = base64.b64decode(raw) if result.get("isBase64Encoded") else raw.encode()
        return int(result.get("statusCode", 502)), result.get("headers") or {}, data

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _forward(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b""
            try:
                status, headers, data = invoke(self.command, self.path, dict(self.headers), body)
            except Exception as error:  # noqa: BLE001 - surfaced to the caller as 502
                status, headers = 502, {"content-type": "application/json"}
                data = json.dumps({"detail": f"invoke failed: {type(error).__name__}"}).encode()
            self.send_response(status)
            for key, value in headers.items():
                if key.lower() not in {"content-length", "connection", "transfer-encoding"}:
                    self.send_header(key, value)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = _forward

        def log_message(self, fmt: str, *fargs) -> None:
            sys.stderr.write(f"proxy: {self.command} {self.path} -> {fargs[1] if len(fargs) > 1 else ''}\n")

    status, _, data = invoke("GET", "/health", {}, b"")  # warm the function before serving
    print(f"proxy: {function} /health -> {status} {data.decode(errors='replace')}", file=sys.stderr)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"proxy: serving {function} on http://127.0.0.1:{args.port}"
          f" (internal reset {'allowed' if args.allow_internal_reset else 'disabled'})", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
