#!/usr/bin/env python3
"""Stand-in for the analytics / audit / auth services used by report-service.

Serves the three endpoints ReportDataFetcher calls, each answering with `rows` synthetic rows
after sleeping `delay_ms` (simulated upstream latency). Threaded, so concurrent requests are
served in parallel exactly like real upstreams would.

Usage: scripts/fake-upstreams.py [port=9099] [delay_ms=200] [rows=200]
Point the app at it with ANALYTICS_SERVICE_URL / AUDIT_SERVICE_URL / AUTH_SERVICE_URL=http://localhost:9099
"""
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 9099
DELAY_S = (int(sys.argv[2]) if len(sys.argv) > 2 else 200) / 1000.0
ROWS = int(sys.argv[3]) if len(sys.argv) > 3 else 200

ROUTES = {
    "/api/v1/analytics/events": ("events", lambda i: {
        "id": i, "eventType": "upload", "userId": f"user-{i % 20}", "count": i * 3}),
    "/api/v1/audit/events": ("events", lambda i: {
        "id": i, "action": "LOGIN", "actor": f"user-{i % 20}", "ipAddress": "10.0.0.1"}),
    "/api/v1/users/activity": ("activities", lambda i: {
        "userId": f"user-{i % 20}", "logins": i, "lastSeen": "2024-01-15T10:00:00Z"}),
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        route = ROUTES.get(path)
        if route is None:
            self.send_response(404)
            self.end_headers()
            return
        key, make_row = route
        time.sleep(DELAY_S)
        body = json.dumps({key: [make_row(i) for i in range(ROWS)]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    print(f"fake upstreams on :{PORT} delay={DELAY_S * 1000:.0f}ms rows={ROWS}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
