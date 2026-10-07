"""In-process stand-in for document-service and file-service.

search_reindex_weekly.py pages through GET {document_service_url}/api/v1/documents
(?page=&size=) and GET {file_service_url}/api/v1/files (?page=&page_size=). The
stub serves the scenario's seed.http lists with the same paging so the script
runs unchanged. seed.http.errors maps {kind: {page: status}} to make a page
answer with that HTTP status instead.

Standalone, for the local cutover rehearsal (etl/RUNBOOK.md §8), serving one
committed scenario's seed.http to the cron container and the Airflow Connections:

  python -m harness.stub_http --scenario search_reindex_weekly/smoke --host 0.0.0.0 --port 8089
"""

from __future__ import annotations

import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

GOLDEN_DIR = Path(__file__).resolve().parent.parent

ROUTES = {
    "/document-service/api/v1/documents": "documents",
    "/file-service/api/v1/files": "files",
}


class ServiceStub:
    def __init__(self, data: dict | None, host: str = "127.0.0.1", port: int = 0):
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
                size = int(query.get("page_size", query.get("size", ["100"]))[0])
                status = stub.data.get("errors", {}).get(kind, {}).get(str(page))
                if status is not None:
                    self.send_error(int(status))
                    return
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

        self.server = ThreadingHTTPServer((host, port), Handler)
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


def scenario_http(name: str) -> dict:
    """seed.http of <script>/<scenario>/scenario.json under the golden directory."""
    path = (GOLDEN_DIR / name / "scenario.json").resolve()
    if not path.is_relative_to(GOLDEN_DIR) or len(Path(name).parts) != 2:
        raise ValueError(
            "scenario must be <script>/<scenario> under %s: %r" % (GOLDEN_DIR, name)
        )
    return json.loads(path.read_text())["seed"].get("http") or {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m harness.stub_http")
    parser.add_argument("--scenario", required=True, help="<script>/<scenario>")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8089)
    args = parser.parse_args(argv)
    data = scenario_http(args.scenario)
    stub = ServiceStub(data, args.host, args.port)
    print(
        "stub_http: %s on %s:%d (%d documents, %d files)"
        % (
            args.scenario,
            args.host,
            stub.server.server_address[1],
            len(data.get("documents", [])),
            len(data.get("files", [])),
        ),
        flush=True,
    )
    try:
        stub.server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stub.server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
