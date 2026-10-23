"""Deterministic stand-in for analytics-service, audit-service and auth-service.

Every row echoes the from/to query parameters the report-service sent, so the outgoing
ReportDateUtils.toIsoString format is pinned through the generated files. metric=upstream-error
makes the analytics endpoint answer 500 to pin the failure path; metric=empty returns no rows.
"""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse


def analytics(q):
    base = {"window_from": q.get("from"), "window_to": q.get("to"), "metric": q.get("metric")}
    return {"events": [
        dict({"event_id": "evt-0001", "event_type": "doc_edit", "user_id": "user-001",
              "timestamp": "2026-01-15T03:45:00Z", "duration_ms": 250, "status": "success",
              "note": "plain"}, **base),
        dict({"event_id": "evt-0002", "event_type": "file_upload", "user_id": "user-002",
              "timestamp": "2026-01-15T04:00:00Z", "duration_ms": 1234.5, "status": None,
              "note": "comma, \"quote\" and caf\u00e9"}, **base),
        dict({"event_id": "evt-0003", "event_type": "search_query", "user_id": "user-003",
              "timestamp": "2026-01-16T23:59:59Z", "duration_ms": 0, "status": "error",
              "note": "line\nbreak"}, **base),
    ]}


def audit(q):
    return {"events": [
        {"audit_id": "aud-0001", "action": "LOGIN", "actor": "user-001", "result": "SUCCESS",
         "ip_address": "10.0.0.1", "timestamp": "2026-01-15T03:31:00Z", "resource": "/auth",
         "window_from": q.get("from"), "window_to": q.get("to")},
        {"audit_id": "aud-0002", "action": "PERMISSION_CHANGE", "actor": "admin", "result": "DENIED",
         "ip_address": "10.0.0.2", "timestamp": "2026-01-15T05:00:00Z", "resource": "/files/doc-1",
         "window_from": q.get("from"), "window_to": q.get("to")},
    ]}


def activity(q):
    return {"activities": [
        {"user_id": "user-001", "email": "user1@otterworks.example.com", "files_uploaded": 13,
         "storage_used_mb": 150.25, "active": True, "window_from": q.get("from"), "window_to": q.get("to")},
        {"user_id": "user-002", "email": "user2@otterworks.example.com", "files_uploaded": 0,
         "storage_used_mb": 0, "active": False, "window_from": q.get("from"), "window_to": q.get("to")},
    ]}


ROUTES = {
    "/api/v1/analytics/events": analytics,
    "/api/v1/audit/events": audit,
    "/api/v1/users/activity": activity,
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        url = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(url.query, keep_blank_values=True).items()}
        route = ROUTES.get(url.path)
        if route is None:
            return self._send(404, {"error": "not found"})
        if q.get("metric") == "upstream-error":
            return self._send(500, {"error": "stubbed upstream failure"})
        if q.get("metric") == "empty":
            return self._send(200, {"events": []})
        return self._send(200, route(q))

    def _send(self, status, body):
        data = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
