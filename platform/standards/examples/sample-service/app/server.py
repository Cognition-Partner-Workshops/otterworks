"""Smallest service that meets the platform standard: /health, stdout logs, config from env."""
import json
import logging
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

logging.basicConfig(stream=sys.stdout, level=os.environ.get("LOG_LEVEL", "INFO"),
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("sample-service")
GREETING = os.environ.get("GREETING", "hello")


def route(path):
    if path == "/health":
        return 200, {"status": "UP"}
    if path == "/":
        return 200, {"message": GREETING}
    return 404, {"error": "not found"}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        status, body = route(self.path)
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        log.info("%s %s", self.address_string(), fmt % args)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    log.info("listening on %d", port)
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
