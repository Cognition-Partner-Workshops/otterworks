#!/usr/bin/env python3
"""Local stand-in for the RDS Data API ExecuteStatement call, backed by a local PostgreSQL.

The context handlers in services/legacy-portal-lambda talk to Aurora through RdsDataClient. Pointing
the SDK at this server (AWS_ENDPOINT_URL_RDS_DATA) lets the unmodified handlers and repositories run
against a resettable local store. Only what the handlers send is implemented: POST /Execute with
named parameters, typeHint and autocommit statements.

SDK releases that predate service-specific endpoint variables (the feedback module pins one) still
call https://rds-data.<region>.amazonaws.com. On the internal compose network that name is an alias
of this container, which also serves HTTPS with a certificate from a throwaway per-run CA
(TLS_CERT/TLS_KEY); the functions trust only that CA, so no request can reach a real endpoint. Values come back as Data API Field objects:
string parameters are bound as varchar, like the Data API, so a timestamp column needs a CAST or a
typeHint; timestamps are returned as 'YYYY-MM-DD HH:MM:SS[.ffffff]' with trailing zeros trimmed.

Statements are never run as received: operations.py maps each exact statement the handlers send to
trusted static SQL and binds only checked parameter values; anything else is refused.

Every call must carry a SigV4 signature made with this run's key pair (LOCAL_CREDENTIALS_FILE, written
by the certs service and shared only with the function containers); anything else gets a 403 before
the body is parsed.
"""
import base64
import datetime as dt
import decimal
import json
import os
import ssl
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import psycopg

import operations
import sigv4

PG_DSN = os.environ.get("PG_DSN", "host=lambda-db user=lp_dataapi password=lp_dataapi")
CLUSTER_ARN = os.environ["LOCAL_CLUSTER_ARN"]
SECRET_ARN = os.environ["LOCAL_SECRET_ARN"]
KEY_ID, KEY_SECRET = sigv4.load_credentials(os.environ["LOCAL_CREDENTIALS_FILE"])
DB_NAME = os.environ.get("LOCAL_DB_NAME", "legacyportal")
DSN = f"{PG_DSN} dbname={DB_NAME}"


class DataApiError(Exception):
    def __init__(self, status, kind, message):
        super().__init__(message)
        self.status, self.kind = status, kind


def field(value):
    if value is None:
        return {"isNull": True}
    if isinstance(value, bool):
        return {"booleanValue": value}
    if isinstance(value, int):
        return {"longValue": value}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, dt.datetime):
        # %Y does not zero-pad years before 1000 on glibc; the Data API format is YYYY-MM-DD.
        text = f"{value.year:04d}-" + value.strftime("%m-%d %H:%M:%S")
        if value.microsecond:
            text += ("." + f"{value.microsecond:06d}").rstrip("0")
        return {"stringValue": text}
    if isinstance(value, (bytes, memoryview)):
        return {"blobValue": base64.b64encode(bytes(value)).decode()}
    if isinstance(value, (decimal.Decimal, dt.date, dt.time, uuid.UUID)):
        return {"stringValue": str(value)}
    if isinstance(value, (dict, list)):
        return {"stringValue": json.dumps(value)}
    return {"stringValue": str(value)}


def execute(req):
    if req.get("resourceArn") != CLUSTER_ARN or req.get("secretArn") != SECRET_ARN:
        raise DataApiError(403, "AccessDeniedException", "resourceArn/secretArn do not match the local cluster")
    if req.get("database") not in (None, DB_NAME):
        raise DataApiError(400, "BadRequestException", "unknown database")
    if req.get("transactionId"):
        raise DataApiError(400, "BadRequestException", "transactions are not supported by the local Data API")
    try:
        op, values = operations.resolve(req.get("sql"), req.get("parameters"))
    except operations.OperationError as e:
        raise DataApiError(400, "BadRequestException", str(e)) from e
    try:
        with psycopg.connect(DSN, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(op.sql, values)
            out = {"numberOfRecordsUpdated": max(cur.rowcount, 0) if cur.description is None else 0}
            if cur.description is not None:
                out["records"] = [[field(v) for v in row] for row in cur.fetchall()]
            return op.name, out
    except psycopg.Error as e:
        raise DataApiError(400, "BadRequestException", str(e).strip()) from e


class Handler(BaseHTTPRequestHandler):
    server_version = "local-data-api"

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length)
        try:
            sigv4.verify("POST", self.path, self.headers, raw, KEY_ID, KEY_SECRET)
        except sigv4.AuthError as e:
            self._reply(403, {"message": str(e)}, e.kind)
            print(f"Execute denied {e.kind}: {e}", flush=True)
            return
        try:
            if self.path.split("?")[0] != "/Execute":
                raise DataApiError(400, "BadRequestException", f"{self.path} is not supported by the local Data API")
            req = json.loads(raw or b"{}")
            name, body = execute(req)
            status = 200
            print(f"Execute ok {name} rows={len(body.get('records', []))}", flush=True)
        except DataApiError as e:
            body, status = {"message": str(e)}, e.status
            self._reply(status, body, e.kind)
            print(f"Execute {e.kind}: {e}", flush=True)
            return
        self._reply(status, body)

    def do_GET(self):
        self._reply(200 if self.path == "/ping" else 404, {"status": "ok"})

    def _reply(self, status, body, error_type=None):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("x-amzn-RequestId", str(uuid.uuid4()))
        if error_type:
            self.send_header("x-amzn-ErrorType", error_type)
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        pass


def serve_tls(port, cert, key):
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(cert, key)
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    print(f"local Data API (TLS) on :{port}", file=sys.stderr, flush=True)
    server.serve_forever()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    if os.environ.get("TLS_CERT"):
        threading.Thread(target=serve_tls, daemon=True,
                         args=(int(os.environ.get("TLS_PORT", "443")), os.environ["TLS_CERT"],
                               os.environ["TLS_KEY"])).start()
    print(f"local Data API on :{port} for {CLUSTER_ARN}", file=sys.stderr, flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
