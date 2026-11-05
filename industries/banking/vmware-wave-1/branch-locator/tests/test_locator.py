import datetime
import importlib
import os
import sys
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
with patch.dict(os.environ, DB_HOST="db", DB_NAME="bankwave", DB_USER="branch_app",
                DB_PASSWORD="", GEO_URL="http://geo:8090/geocode", BRANCH_TZ="Etc/UTC"):
    import locator


class LocatorTest(unittest.TestCase):
    def setUp(self):
        self.client = locator.app.test_client()

    def test_missing_query_is_legacy_json(self):
        for path in ("/api/nearest", "/api/nearest?q=", "/api/nearest?q=%20"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.data, b'{"error":"q is required"}\n')

    def test_home(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Find a branch", response.data)

    @patch.object(locator, "branches", return_value=[])
    @patch.object(locator, "locate", return_value=(10.0, -30.0))
    def test_empty_branches(self, locate, branches):
        response = self.client.get("/api/nearest?q=%20harbour%20")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b'{"branches":[],"lat":10.0,"lon":-30.0,"query":"harbour"}\n')
        locate.assert_called_once_with("harbour")

    @patch.object(locator, "branches", return_value=[dict(name="A", address="1 St", lat=10,
                  lon=-30, opens="08:30", closes="16:30")])
    @patch.object(locator, "locate", return_value=(10.0, -30.0))
    @patch.object(locator, "branch_time", return_value="09:00")
    def test_nearest(self, clock, locate, branches):
        response = self.client.get("/api/nearest?q=harbour")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["branches"][0]["open_now"])
        self.assertEqual(response.json["branches"][0]["km"], 0.0)

    @patch.object(locator, "branches", return_value=[])
    @patch.object(locator, "locate", return_value=(10.0, -30.0))
    def test_health(self, locate, branches):
        self.assertEqual(self.client.get("/health").status_code, 200)

    @patch.object(locator, "branches", side_effect=locator.psycopg.OperationalError())
    def test_unhealthy_database(self, branches):
        self.assertEqual(self.client.get("/health").status_code, 503)

    @patch.object(locator, "branches", return_value=[])
    @patch.object(locator, "locate", side_effect=locator.requests.ConnectionError())
    def test_unhealthy_geocoder(self, locate, branches):
        self.assertEqual(self.client.get("/health").status_code, 503)
        self.assertEqual(self.client.get("/api/nearest?q=harbour").status_code, 500)

    def test_explicit_timezone_across_day_and_closing_boundary(self):
        utc = datetime.timezone.utc
        with patch.object(locator.settings, "BRANCH_TZ", ZoneInfo("America/Los_Angeles")):
            before = datetime.datetime(2026, 10, 16, 23, 29, tzinfo=utc)
            after = datetime.datetime(2026, 10, 17, 0, 0, tzinfo=utc)
            self.assertEqual(locator.branch_time(before), "16:29")
            self.assertTrue(locator.geo.is_open("08:30", "16:30", locator.branch_time(before)))
            closing = before + datetime.timedelta(minutes=1)
            self.assertFalse(locator.geo.is_open("08:30", "16:30", locator.branch_time(closing)))
            self.assertEqual(locator.branch_time(after), "17:00")

    def test_settings_require_password(self):
        with patch.dict(os.environ, {"DB_HOST": "db", "DB_NAME": "bankwave", "DB_USER": "branch_app"}, clear=True):
            with self.assertRaisesRegex(KeyError, "DB_PASSWORD"):
                importlib.reload(locator.settings)
