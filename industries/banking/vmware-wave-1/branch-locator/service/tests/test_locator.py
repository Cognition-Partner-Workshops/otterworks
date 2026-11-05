import datetime
import os
import sys
import unittest
from decimal import Decimal
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import psycopg2  # noqa: E402

import locator  # noqa: E402

ROWS = [
    {"name": "Harbour Point", "address": "12 Quay Street", "lat": Decimal("10.01200"),
     "lon": Decimal("-30.02100"), "opens": "08:30", "closes": "16:30"},
    {"name": "Market Square", "address": "3 Market Square", "lat": Decimal("10.03400"),
     "lon": Decimal("-30.00800"), "opens": "08:30", "closes": "16:30"},
]

WEB02_404 = (b'<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">\n<title>404 Not Found</title>\n'
             b"<h1>Not Found</h1>\n<p>The requested URL was not found on the server. If you entered the URL "
             b"manually please check your spelling and try again.</p>\n")


class LocatorTest(unittest.TestCase):
    def setUp(self):
        self.client = locator.app.test_client()

    def test_health_up(self):
        with mock.patch.object(locator, "connect") as c:
            r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), {"status": "UP"})
        c.return_value.close.assert_called_once()

    def test_health_down_when_database_unreachable(self):
        with mock.patch.object(locator, "connect", side_effect=psycopg2.OperationalError("down")):
            r = self.client.get("/health")
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.get_json(), {"status": "DOWN"})

    def test_q_required(self):
        for path in ("/api/nearest", "/api/nearest?q=", "/api/nearest?q=%20%20"):
            r = self.client.get(path)
            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.content_type, "application/json")
            self.assertEqual(r.data, b'{"error":"q is required"}\n')

    def test_nearest_json_bytes_match_web02_format(self):
        with mock.patch.object(locator, "locate", return_value=(10.01, -30.02)), \
                mock.patch.object(locator, "branches", return_value=ROWS), \
                mock.patch.object(locator, "business_hhmm", return_value="09:00"):
            r = self.client.get("/api/nearest?q=harbour")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, (
            b'{"branches":[{"address":"12 Quay Street","closes":"16:30","km":0.25,"lat":10.012,"lon":-30.021,'
            b'"name":"Harbour Point","open_now":true,"opens":"08:30"},{"address":"3 Market Square",'
            b'"closes":"16:30","km":2.97,"lat":10.034,"lon":-30.008,"name":"Market Square","open_now":true,'
            b'"opens":"08:30"}],"lat":10.01,"lon":-30.02,"query":"harbour"}\n'))

    def test_open_now_uses_business_zone_not_host_zone(self):
        fixed = datetime.datetime(2026, 10, 15, 17, 0, tzinfo=datetime.timezone.utc)
        with mock.patch.object(locator.datetime, "datetime", wraps=datetime.datetime) as dt:
            dt.now.side_effect = lambda tz=None: fixed.astimezone(tz)
            with mock.patch.object(locator, "BUSINESS_TZ", locator.ZoneInfo("Etc/UTC")):
                self.assertEqual(locator.business_hhmm(), "17:00")
            with mock.patch.object(locator, "BUSINESS_TZ", locator.ZoneInfo("America/New_York")):
                self.assertEqual(locator.business_hhmm(), "13:00")

    def test_not_found_page_matches_web02(self):
        r = self.client.get("/nope")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.content_type, "text/html; charset=utf-8")
        self.assertEqual(r.data, WEB02_404)

    def test_method_not_allowed_keeps_allow_header(self):
        r = self.client.post("/api/nearest?q=x")
        self.assertEqual(r.status_code, 405)
        self.assertIn("GET", r.headers["Allow"])
        self.assertTrue(r.data.startswith(b'<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">\n'
                                          b"<title>405 Method Not Allowed</title>"))

    def test_geocoder_failure_is_web02_500_page(self):
        with mock.patch.object(locator, "locate", side_effect=RuntimeError("geo down")):
            r = self.client.get("/api/nearest?q=harbour")
        self.assertEqual(r.status_code, 500)
        self.assertEqual(r.content_type, "text/html; charset=utf-8")
        self.assertTrue(r.data.startswith(b'<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">\n'
                                          b"<title>500 Internal Server Error</title>\n"))

    def test_settings_carry_no_password_default(self):
        import settings
        with mock.patch.dict(os.environ, {}, clear=True):
            import importlib
            self.assertEqual(importlib.reload(settings).DB_PASSWORD, "")
        importlib.reload(settings)

    def test_index_template_unchanged(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, "text/html; charset=utf-8")
        self.assertIn(b"<title>Find a branch - Halvergate Bank</title>", r.data)


if __name__ == "__main__":
    unittest.main()
