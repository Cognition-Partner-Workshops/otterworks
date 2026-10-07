"""In-process stand-in for document-service and file-service.

search_reindex_weekly.py pages through GET {document_service_url}/api/v1/documents
and GET {file_service_url}/api/v1/files with ?page=&size=. The stub serves the
scenario's seed.http lists with the same paging so the script runs unchanged.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROUTES = {
    "/document-service/api/v1/documents": "documents",
    "/file-service/api/v1/files": "files",
}


class ServiceStub:
    def __init__(self, data: dict | None):
        self.data = data or {}
        self.requests: list[str] = []
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802 - http.server API
                stub.requests.append(self.path)
                parsed = urlparse(self.path)
                kind = ROUTES.get(parsed.path)
                if kind is None:
                    self.send_error(404)
                    return
                query = parse_qs(parsed.query)
                page = int(query.get("page", ["1"])[0])
                size = int(query.get("size", ["100"])[0])
                items = stub.data.get(kind, [])
                chunk = items[(page - 1) * size : page * size]
                body = json.dumps(
                    {kind: chunk, "total": len(items), "page": page}
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        host, port = self.server.server_address[:2]
        return "http://%s:%d" % (host, port)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_exc):
        self.server.shutdown()
        self.server.server_close()
