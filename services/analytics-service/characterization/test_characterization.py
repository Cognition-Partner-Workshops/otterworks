"""Characterization tests for analytics-service, run against the RUNNING module.

Pins the current HTTP behaviour (status codes, content types, JSON shapes and
deterministic values, error responses) so the same file can be rerun unchanged
after a runtime/toolchain upgrade. Stdlib only (Python 3.8+).

    BASE_URL=http://localhost:18088 python3 characterization/test_characterization.py

Expects a freshly started module backed by an empty PostgreSQL database (see
start-module.sh): the market tests assert the synthetic-seed state before they
POST a manual observation. Event tests use per-run unique ids, so they are
independent of any events already stored.

SNAPSHOT_DIR (optional): directory to write normalized responses of the
deterministic endpoints to, so two runs (before/after) can be diffed.
"""

import datetime
import http.client
import json
import os
import re
import sys
import unittest
import urllib.parse
import uuid

BASE_URL = os.environ.get("BASE_URL", "http://localhost:18088").rstrip("/")
_BASE = urllib.parse.urlsplit(BASE_URL)
if _BASE.scheme not in ("http", "https") or not _BASE.netloc:
    sys.exit(f"BASE_URL must be an http(s) URL, got {BASE_URL!r}")
SNAPSHOT_DIR = os.environ.get("SNAPSHOT_DIR")
RUN = uuid.uuid4().hex[:10]
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
ISO_INSTANT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,9})?Z$")
SERVER_HEADER = "akka-http/10.5.3"

SERIES_CODES = [
    "COTTON_USD_KG", "DREWRY_WCI_USD_FEU", "SALMON_NOK_KG", "SHRIMP_USD_KG",
    "SOYBEAN_OIL_USD_KG", "SUGAR_USD_KG", "USD_NOK",
]


class Resp:
    def __init__(self, status, headers, body):
        self.status = status
        self.headers = headers
        self.body = body

    @property
    def text(self):
        return self.body.decode("utf-8")

    def json(self):
        return json.loads(self.body)

    def header(self, name):
        return self.headers.get(name)


def call(method, path, body=None, content_type="application/json"):
    data = None
    headers = {}
    if body is not None:
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        headers["Content-Type"] = content_type
    headers["Connection"] = "close"
    conn_cls = http.client.HTTPSConnection if _BASE.scheme == "https" else http.client.HTTPConnection
    conn = conn_cls(_BASE.netloc, timeout=30)
    try:
        conn.request(method, _BASE.path + path, body=data, headers=headers)
        r = conn.getresponse()
        return Resp(r.status, r.headers, r.read())
    finally:
        conn.close()


def snapshot(name, value):
    if not SNAPSHOT_DIR:
        return
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    with open(os.path.join(SNAPSHOT_DIR, name), "w") as f:
        if isinstance(value, str):
            f.write(value)
        else:
            json.dump(value, f, indent=2, sort_keys=True)
            f.write("\n")


def track(event_type, user, resource, resource_type, metadata=None):
    body = {"eventType": event_type, "userId": user, "resourceId": resource, "resourceType": resource_type}
    if metadata is not None:
        body["metadata"] = metadata
    r = call("POST", "/api/v1/analytics/events", body)
    assert r.status == 202, (r.status, r.text)
    return r.json()["eventId"]


def today_utc():
    return datetime.datetime.now(datetime.timezone.utc).date().isoformat()


class T1HealthAndMetrics(unittest.TestCase):
    def test_01_health(self):
        r = call("GET", "/health")
        self.assertEqual(r.status, 200)
        self.assertEqual(r.header("Content-Type"), "application/json")
        self.assertEqual(r.header("Server"), SERVER_HEADER)
        body = r.json()
        self.assertEqual(set(body), {"status", "service", "eventsProcessed"})
        self.assertEqual(body["status"], "healthy")
        self.assertEqual(body["service"], "analytics-service")
        self.assertIsInstance(body["eventsProcessed"], int)
        # Field order is part of the hand-written body.
        self.assertTrue(r.text.startswith('{"status":"healthy","service":"analytics-service","eventsProcessed":'))

    def test_02_health_counts_events(self):
        before = call("GET", "/health").json()["eventsProcessed"]
        track("document.viewed", f"health-{RUN}", f"doc-health-{RUN}", "document")
        after = call("GET", "/health").json()["eventsProcessed"]
        self.assertEqual(after, before + 1)

    def test_03_metrics(self):
        # Pinned as-is: the Prometheus collectors live in the HealthRoutes
        # companion object, which nothing initialises, and no JVM (hotspot)
        # collectors are registered, so /metrics answers 200 with an empty body.
        r = call("GET", "/metrics")
        self.assertEqual(r.status, 200)
        self.assertEqual(r.header("Content-Type"), "text/plain; charset=UTF-8")
        self.assertEqual(r.header("Content-Length"), "0")
        self.assertEqual(r.text, "")
        snapshot("metrics_body.txt", r.text)

    def test_03b_head_health_not_allowed(self):
        r = call("HEAD", "/health")
        self.assertEqual(r.status, 405)
        self.assertEqual(r.header("Allow"), "GET")

    def test_04_unknown_route(self):
        r = call("GET", "/does-not-exist")
        self.assertEqual(r.status, 404)
        self.assertEqual(r.text, "The requested resource could not be found.")

    def test_05_wrong_method_on_health(self):
        r = call("POST", "/health", {})
        self.assertEqual(r.status, 405)
        self.assertEqual(r.text, "HTTP method not allowed, supported methods: GET")


class T2Events(unittest.TestCase):
    def test_01_track_event_accepted(self):
        r = call("POST", "/api/v1/analytics/events", {
            "eventType": "document.created", "userId": f"u-{RUN}", "resourceId": f"d-{RUN}",
            "resourceType": "document", "metadata": {"title": "Char"},
        })
        self.assertEqual(r.status, 202)
        self.assertEqual(r.header("Content-Type"), "application/json")
        body = r.json()
        self.assertEqual(set(body), {"status", "eventId"})
        self.assertEqual(body["status"], "accepted")
        self.assertRegex(body["eventId"], UUID_RE)

    def test_02_metadata_optional(self):
        r = call("POST", "/api/v1/analytics/events", {
            "eventType": "file.uploaded", "userId": f"u-{RUN}", "resourceId": f"f-{RUN}", "resourceType": "file",
        })
        self.assertEqual(r.status, 202)

    def test_03_unknown_event_type_is_accepted(self):
        r = call("POST", "/api/v1/analytics/events", {
            "eventType": "totally.unknown", "userId": f"u-{RUN}", "resourceId": "x", "resourceType": "other",
        })
        self.assertEqual(r.status, 202)

    def test_04_missing_field(self):
        r = call("POST", "/api/v1/analytics/events", {"eventType": "document.created"})
        self.assertEqual(r.status, 400)
        self.assertEqual(r.header("Content-Type"), "text/plain; charset=UTF-8")
        self.assertTrue(r.text.startswith("The request content was malformed:"), r.text)
        self.assertIn("userId", r.text)

    def test_05_invalid_json(self):
        r = call("POST", "/api/v1/analytics/events", b"{not json")
        self.assertEqual(r.status, 400)
        self.assertTrue(r.text.startswith("The request content was malformed:"), r.text)

    def test_06_wrong_content_type(self):
        r = call("POST", "/api/v1/analytics/events", b"hello", content_type="text/plain")
        self.assertEqual(r.status, 415)
        self.assertEqual(
            r.text, "The request's Content-Type [text/plain] is not supported. Expected:\napplication/json")

    def test_07_get_not_allowed(self):
        r = call("GET", "/api/v1/analytics/events")
        self.assertEqual(r.status, 405)
        self.assertEqual(r.text, "HTTP method not allowed, supported methods: POST")


class T3Queries(unittest.TestCase):
    user = f"char-user-{RUN}"
    doc = f"char-doc-{RUN}"
    file = f"char-file-{RUN}"

    @classmethod
    def setUpClass(cls):
        cls.dash_before = call("GET", "/api/v1/analytics/dashboard").json()
        u, d, f = cls.user, cls.doc, cls.file
        track("document.created", u, d, "document", {"title": "Characterization Doc"})
        track("document.viewed", u, d, "document")
        track("document.viewed", u, d, "document")
        track("document.viewed", f"{u}-2", d, "document")
        track("document.edited", u, d, "document")
        track("document.shared", u, d, "document")
        track("file.uploaded", u, f, "file", {"title": "Characterization File"})
        track("file.downloaded", u, f, "file")
        track("storage.allocated", u, d, "document", {"bytes": "1000"})
        track("storage.allocated", u, f, "file", {"bytes": "250"})
        track("storage.released", u, d, "document", {"bytes": "300"})
        track("collab.session_started", u, d, "document")

    def test_01_user_activity(self):
        r = call("GET", f"/api/v1/analytics/users/{self.user}/activity")
        self.assertEqual(r.status, 200)
        self.assertEqual(r.header("Content-Type"), "application/json")
        b = r.json()
        self.assertEqual(set(b), {
            "userId", "totalEvents", "documentsCreated", "documentsViewed", "documentsEdited",
            "filesUploaded", "filesDownloaded", "lastActiveAt", "recentEvents"})
        self.assertEqual(b["userId"], self.user)
        self.assertEqual(
            (b["totalEvents"], b["documentsCreated"], b["documentsViewed"], b["documentsEdited"],
             b["filesUploaded"], b["filesDownloaded"]),
            (11, 1, 2, 1, 1, 1))
        self.assertRegex(b["lastActiveAt"], ISO_INSTANT_RE)
        self.assertEqual(len(b["recentEvents"]), 11)
        self.assertEqual(set(b["recentEvents"][0]), {"eventId", "eventType", "resourceId", "resourceType", "timestamp"})
        ts = [e["timestamp"] for e in b["recentEvents"]]
        self.assertEqual(ts, sorted(ts, reverse=True))
        self.assertEqual(b["recentEvents"][0]["timestamp"], b["lastActiveAt"])

    def test_02_user_activity_unknown_user(self):
        r = call("GET", f"/api/v1/analytics/users/nobody-{RUN}/activity")
        self.assertEqual(r.status, 200)
        self.assertEqual(r.json(), {
            "userId": f"nobody-{RUN}", "totalEvents": 0, "documentsCreated": 0, "documentsViewed": 0,
            "documentsEdited": 0, "filesUploaded": 0, "filesDownloaded": 0, "recentEvents": []})

    def test_03_document_stats(self):
        b = call("GET", f"/api/v1/analytics/documents/{self.doc}/stats").json()
        self.assertEqual(set(b), {"documentId", "views", "edits", "shares", "uniqueViewers", "lastViewedAt", "lastEditedAt"})
        self.assertEqual((b["documentId"], b["views"], b["edits"], b["shares"], b["uniqueViewers"]),
                         (self.doc, 3, 1, 1, 2))
        self.assertRegex(b["lastViewedAt"], ISO_INSTANT_RE)
        self.assertRegex(b["lastEditedAt"], ISO_INSTANT_RE)

    def test_04_document_stats_unknown(self):
        b = call("GET", f"/api/v1/analytics/documents/none-{RUN}/stats").json()
        self.assertEqual(b, {"documentId": f"none-{RUN}", "views": 0, "edits": 0, "shares": 0, "uniqueViewers": 0})

    def test_05_dashboard(self):
        r = call("GET", "/api/v1/analytics/dashboard")
        self.assertEqual(r.status, 200)
        b = r.json()
        self.assertEqual(set(b), {"period", "dailyActiveUsers", "documentsCreated", "filesUploaded",
                                  "storageUsedBytes", "collabSessions", "totalEvents"})
        self.assertEqual(b["period"], "7d")
        a = self.dash_before
        self.assertGreaterEqual(b["totalEvents"] - a["totalEvents"], 12)
        self.assertGreaterEqual(b["documentsCreated"] - a["documentsCreated"], 1)
        self.assertGreaterEqual(b["filesUploaded"] - a["filesUploaded"], 1)
        self.assertGreaterEqual(b["collabSessions"] - a["collabSessions"], 1)
        self.assertGreaterEqual(b["storageUsedBytes"] - a["storageUsedBytes"], 950)

    def test_06_dashboard_period_echo(self):
        for p in ("30d", "90d", "daily", "bogus"):
            self.assertEqual(call("GET", f"/api/v1/analytics/dashboard?period={p}").json()["period"], p)

    def test_07_top_content(self):
        b = call("GET", "/api/v1/analytics/top-content").json()
        self.assertEqual(set(b), {"period", "contentType", "items"})
        self.assertEqual((b["period"], b["contentType"]), ("7d", "documents"))
        self.assertTrue(all(i["resourceType"] == "document" for i in b["items"]))
        self.assertLessEqual(len(b["items"]), 10)
        counts = [i["eventCount"] for i in b["items"]]
        self.assertEqual(counts, sorted(counts, reverse=True))
        files = call("GET", "/api/v1/analytics/top-content?type=files&limit=100").json()
        mine = [i for i in files["items"] if i["resourceId"] == self.file]
        self.assertEqual(mine, [{"resourceId": self.file, "resourceType": "file", "title": "Characterization File",
                                 "eventCount": 3, "uniqueUsers": 1}])
        docs = call("GET", "/api/v1/analytics/top-content?type=documents&limit=1000").json()
        mine = [i for i in docs["items"] if i["resourceId"] == self.doc]
        self.assertEqual(mine, [{"resourceId": self.doc, "resourceType": "document", "title": "Characterization Doc",
                                 "eventCount": 9, "uniqueUsers": 2}])

    def test_08_top_content_limit(self):
        b = call("GET", "/api/v1/analytics/top-content?type=all&limit=1").json()
        self.assertEqual(b["contentType"], "all")
        self.assertEqual(len(b["items"]), 1)

    def test_09_top_content_bad_limit(self):
        r = call("GET", "/api/v1/analytics/top-content?limit=abc")
        self.assertEqual(r.status, 400)
        self.assertTrue(r.text.startswith("The query parameter 'limit' was malformed:"), r.text)

    def test_10_active_users(self):
        b = call("GET", "/api/v1/analytics/active-users").json()
        self.assertEqual(set(b), {"period", "count", "users"})
        self.assertEqual(b["period"], "daily")
        self.assertEqual(b["count"], len(b["users"]))
        mine = [u for u in b["users"] if u["userId"] == self.user]
        self.assertEqual(len(mine), 1)
        self.assertEqual(mine[0]["eventCount"], 11)
        self.assertRegex(mine[0]["lastActiveAt"], ISO_INSTANT_RE)

    def test_11_storage_for_user(self):
        b = call("GET", f"/api/v1/analytics/storage?user_id={self.user}").json()
        self.assertEqual(b, {"userId": self.user, "totalStorageBytes": 950, "filesCount": 1, "documentsCount": 1,
                             "breakdownByType": {"document": 1000, "file": 250}})

    def test_12_storage_global(self):
        b = call("GET", "/api/v1/analytics/storage").json()
        self.assertEqual(set(b), {"totalStorageBytes", "filesCount", "documentsCount", "breakdownByType"})
        self.assertNotIn("userId", b)

    def test_13_export_json(self):
        r = call("GET", "/api/v1/analytics/export")
        self.assertEqual(r.status, 200)
        self.assertEqual(r.header("Content-Type"), "application/json")
        b = r.json()
        self.assertEqual(set(b), {"format", "period", "generatedAt", "recordCount", "data"})
        self.assertEqual((b["format"], b["period"]), ("json", "7d"))
        self.assertRegex(b["generatedAt"], ISO_INSTANT_RE)
        self.assertEqual(b["recordCount"], len(b["data"]))
        self.assertEqual(set(b["data"][0]),
                         {"event_id", "event_type", "user_id", "resource_id", "resource_type", "timestamp"})
        ts = [d["timestamp"] for d in b["data"]]
        self.assertEqual(ts, sorted(ts, reverse=True))

    def test_14_export_unknown_format_is_json(self):
        b = call("GET", "/api/v1/analytics/export?format=xml&period=30d").json()
        self.assertEqual((b["format"], b["period"]), ("json", "30d"))

    def test_15_export_csv(self):
        r = call("GET", "/api/v1/analytics/export?format=csv")
        self.assertEqual(r.status, 200)
        self.assertEqual(r.header("Content-Type"), "text/plain; charset=UTF-8")
        lines = r.text.split("\n")
        self.assertEqual(lines[0], "event_id,event_type,user_id,resource_id,resource_type,timestamp")
        self.assertEqual(lines[-1], "")
        mine = [l for l in lines if f",{self.user}," in l]
        self.assertEqual(len(mine), 11)


class T4Market(unittest.TestCase):
    def test_01_series(self):
        r = call("GET", "/api/v1/analytics/market/series")
        self.assertEqual(r.status, 200)
        self.assertEqual(r.header("Content-Type"), "application/json")
        b = r.json()
        self.assertEqual(list(b), ["series"])
        self.assertEqual(sorted(s["series_code"] for s in b["series"]), SERIES_CODES)
        self.assertEqual(set(b["series"][0]), {"series_code", "name", "unit", "currency", "category"})
        salmon = [s for s in b["series"] if s["series_code"] == "SALMON_NOK_KG"][0]
        self.assertEqual(salmon, {"series_code": "SALMON_NOK_KG", "name": "NASDAQ Salmon Index",
                                  "unit": "NOK/kg", "currency": "NOK", "category": "commodity"})
        snapshot("market_series.json", b)

    def test_02_prices_baseline(self):
        r = call("GET", "/api/v1/analytics/market/prices?series_code=SALMON_NOK_KG&from=2024-08-01&to=2024-08-04")
        self.assertEqual(r.status, 200)
        b = r.json()
        self.assertEqual(b, {"prices": [
            {"series_code": "SALMON_NOK_KG", "price_date": "2024-08-01", "value": 86.950439, "source": "synthetic"},
            {"series_code": "SALMON_NOK_KG", "price_date": "2024-08-02", "value": 87.221778, "source": "synthetic"},
            {"series_code": "SALMON_NOK_KG", "price_date": "2024-08-03", "value": 86.511142, "source": "synthetic"},
            {"series_code": "SALMON_NOK_KG", "price_date": "2024-08-04", "value": 86.375959, "source": "synthetic"},
        ]})
        self.assertIn('"value":86.950439', r.text.replace(" ", ""))

    def test_03_prices_extend_to_today(self):
        b = call("GET", "/api/v1/analytics/market/prices?series_code=USD_NOK").json()
        dates = [p["price_date"] for p in b["prices"]]
        self.assertEqual(dates, sorted(dates))
        self.assertEqual(dates[-1], today_utc())
        snapshot("market_prices_all_series.json", {
            code: call("GET", f"/api/v1/analytics/market/prices?series_code={code}").json()
            for code in SERIES_CODES})

    def test_04_prices_unknown_series(self):
        r = call("GET", "/api/v1/analytics/market/prices?series_code=NOPE")
        self.assertEqual((r.status, r.json()), (200, {"prices": []}))

    def test_05_prices_missing_param(self):
        r = call("GET", "/api/v1/analytics/market/prices")
        self.assertEqual(r.status, 404)
        self.assertEqual(r.text, "Request is missing required query parameter 'series_code'")

    def test_06_status_after_seed(self):
        b = call("GET", "/api/v1/analytics/market/status").json()
        self.assertEqual(set(b), {"source", "last_run_type", "last_completed_at", "observations_count", "as_of_date"})
        self.assertEqual(b["source"], "synthetic")
        self.assertEqual(b["last_run_type"], "baseline_seed")
        self.assertRegex(b["last_completed_at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        self.assertGreaterEqual(b["observations_count"], 4893)
        self.assertEqual(b["as_of_date"], today_utc())
        snapshot("market_status_after_seed.json", {k: v for k, v in b.items() if k != "last_completed_at"})

    def test_07_margins_dashboard(self):
        r = call("GET", "/api/v1/analytics/margins")
        self.assertEqual(r.status, 200)
        self.assertEqual(r.header("Content-Type"), "application/json")
        b = r.json()
        self.assertEqual(set(b), {"as_of_date", "source", "last_sync_at", "kpis", "rows"})
        self.assertEqual(b["as_of_date"], today_utc())
        self.assertEqual(b["source"], "synthetic")
        self.assertEqual(set(b["kpis"]), {"gross_margin_pct", "avg_cogs_usd", "salmon_index", "freight_index"})
        self.assertEqual(len(b["rows"]), 40)
        self.assertEqual(set(b["rows"][0]), {
            "sku", "name", "category", "supplier", "list_price_usd", "commodity_cost_usd",
            "freight_cost_usd", "overhead_cost_usd", "cogs_usd", "margin_pct"})
        skus = [row["sku"] for row in b["rows"]]
        self.assertEqual(skus, sorted(skus))
        self.assertEqual(call("GET", "/api/v1/analytics/margins/").json()["rows"], b["rows"])
        snapshot("margins_dashboard.json", {k: v for k, v in b.items() if k != "last_sync_at"})

    def test_08_margin_series_by_sku(self):
        b = call("GET", "/api/v1/analytics/margins/series?sku=SLM-001&from=2024-08-01&to=2024-08-10").json()
        self.assertEqual(b["sku"], "SLM-001")
        self.assertNotIn("category", b)
        self.assertEqual(len(b["points"]), 10)
        self.assertEqual(set(b["points"][0]), {"margin_date", "margin_pct"})
        self.assertEqual(b["points"][0]["margin_date"], "2024-08-01")
        snapshot("margin_series_sku.json", b)

    def test_09_margin_series_by_category_and_all(self):
        cat = call("GET", "/api/v1/analytics/margins/series?category=Seafood&from=2024-08-01&to=2024-08-10").json()
        self.assertEqual(cat["category"], "Seafood")
        self.assertNotIn("sku", cat)
        self.assertEqual(len(cat["points"]), 10)
        allp = call("GET", "/api/v1/analytics/margins/series?from=2024-08-01&to=2024-08-03").json()
        self.assertEqual(allp.get("points") and len(allp["points"]), 3)
        self.assertEqual(set(allp), {"points"})
        snapshot("margin_series_category_and_all.json", {"category": cat, "all": allp})

    def test_10_margins_export_csv(self):
        r = call("GET", "/api/v1/analytics/margins/export?format=csv")
        self.assertEqual(r.status, 200)
        self.assertEqual(r.header("Content-Type"), "text/plain; charset=UTF-8")
        lines = r.text.split("\n")
        self.assertEqual(lines[0], "sku,name,category,supplier,list_price_usd,commodity_cost_usd,"
                                   "freight_cost_usd,overhead_cost_usd,cogs_usd,margin_pct")
        self.assertEqual(len(lines), 42)
        self.assertEqual(lines[-1], "")
        snapshot("margins_export.csv", r.text)

    def test_11_margins_export_json(self):
        b = call("GET", "/api/v1/analytics/margins/export").json()
        self.assertEqual(b["rows"], call("GET", "/api/v1/analytics/margins").json()["rows"])

    def test_12_observations_all_invalid(self):
        r = call("POST", "/api/v1/analytics/market/observations", {"observations": [
            {"series_code": "NOPE", "price_date": "2024-08-01", "value": 1.0},
            {"series_code": "USD_NOK", "price_date": "08/01/2024", "value": 1.0},
            {"series_code": "USD_NOK", "price_date": "2999-01-01", "value": 1.0},
            {"series_code": "USD_NOK", "price_date": "2024-08-01", "value": 0},
        ]})
        self.assertEqual(r.status, 400)
        self.assertEqual(r.header("Content-Type"), "application/json")
        self.assertEqual(r.json(), {"accepted": 0, "recomputed_skus": 0, "run_id": 0, "rejected": [
            {"series_code": "NOPE", "price_date": "2024-08-01", "reason": "unknown series_code 'NOPE'"},
            {"series_code": "USD_NOK", "price_date": "08/01/2024", "reason": "invalid price_date (expected YYYY-MM-DD)"},
            {"series_code": "USD_NOK", "price_date": "2999-01-01", "reason": "price_date is in the future"},
            {"series_code": "USD_NOK", "price_date": "2024-08-01", "reason": "value must be positive"},
        ]})
        self.assertEqual(call("GET", "/api/v1/analytics/market/status").json()["source"], "synthetic")

    def test_13_observations_malformed(self):
        r = call("POST", "/api/v1/analytics/market/observations", {"obs": []})
        self.assertEqual(r.status, 400)
        self.assertTrue(r.text.startswith("The request content was malformed:"), r.text)

    def test_14_observations_manual_pull(self):
        r = call("POST", "/api/v1/analytics/market/observations", {
            "observations": [
                {"series_code": "SALMON_NOK_KG", "price_date": "2024-08-02", "value": 103.10},
                {"series_code": "BOGUS", "price_date": "2024-08-02", "value": 1},
            ],
            "source_note": "characterization",
        })
        self.assertEqual(r.status, 200)
        b = r.json()
        self.assertEqual(set(b), {"accepted", "rejected", "recomputed_skus", "run_id"})
        self.assertEqual(b["accepted"], 1)
        self.assertEqual(b["rejected"], [{"series_code": "BOGUS", "price_date": "2024-08-02",
                                          "reason": "unknown series_code 'BOGUS'"}])
        self.assertGreater(b["run_id"], 0)
        salmon_skus = len([row for row in call("GET", "/api/v1/analytics/margins").json()["rows"]
                           if row["sku"].startswith("SLM-")])
        self.assertEqual(b["recomputed_skus"], salmon_skus)

        p = call("GET", "/api/v1/analytics/market/prices?series_code=SALMON_NOK_KG&from=2024-08-02&to=2024-08-02").json()
        self.assertEqual(p, {"prices": [{"series_code": "SALMON_NOK_KG", "price_date": "2024-08-02",
                                         "value": 103.1, "source": "manual_pull"}]})
        s = call("GET", "/api/v1/analytics/market/status").json()
        self.assertEqual((s["source"], s["last_run_type"], s["observations_count"]), ("manual_pull", "manual_pull", 1))
        self.assertEqual(call("GET", "/api/v1/analytics/margins").json()["source"], "manual_pull")
        series = call("GET", "/api/v1/analytics/margins/series?sku=SLM-001&from=2024-08-01&to=2024-08-03").json()
        snapshot("after_manual_pull.json", {"response": {k: v for k, v in b.items() if k != "run_id"},
                                            "prices": p, "margin_series": series})


if __name__ == "__main__":
    print(f"BASE_URL={BASE_URL} run={RUN}")
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    res = runner.run(suite)
    print(f"Tests run: {res.testsRun}, Failures: {len(res.failures)}, Errors: {len(res.errors)}, "
          f"Skipped: {len(res.skipped)}")
    sys.exit(0 if res.wasSuccessful() else 1)
