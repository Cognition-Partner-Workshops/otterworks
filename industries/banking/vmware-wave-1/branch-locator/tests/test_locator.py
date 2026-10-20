import importlib
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
os.environ.setdefault("DB_PASSWORD", "unit-test-only")
import locator  # noqa: E402
import settings  # noqa: E402

ROWS = [
    {"name": "A", "address": "1 St", "lat": 10.0, "lon": -30.0, "opens": "08:30", "closes": "16:30"},
    {"name": "B", "address": "2 St", "lat": 10.1, "lon": -30.0, "opens": "08:30", "closes": "16:30"},
]


class LocatorTest(unittest.TestCase):
    def setUp(self):
        self.client = locator.app.test_client()

    def test_health(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), {"status": "ok"})

    def test_index(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Find a branch", r.data)

    def test_missing_q(self):
        r = self.client.get("/api/nearest?q=%20")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.get_json(), {"error": "q is required"})

    def test_nearest(self):
        with mock.patch.object(locator, "locate", return_value=(10.0, -30.0)), \
                mock.patch.object(locator, "branches", return_value=ROWS), \
                mock.patch.object(locator, "now_hhmm", return_value="09:00"):
            r = self.client.get("/api/nearest?q=x")
        body = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual([b["name"] for b in body["branches"]], ["A", "B"])
        self.assertTrue(body["branches"][0]["open_now"])
        self.assertEqual(body["query"], "x")

    def test_branch_tz(self):
        with mock.patch.object(settings, "BRANCH_TZ", "Etc/GMT-14"):
            self.assertRegex(locator.now_hhmm(), r"^\d\d:\d\d$")


class SettingsTest(unittest.TestCase):
    def test_password_is_required(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(KeyError):
                importlib.reload(settings)
        importlib.reload(settings)

    def test_defaults(self):
        with mock.patch.dict(os.environ, {"DB_PASSWORD": "x"}, clear=True):
            s = importlib.reload(settings)
            self.assertEqual(s.PORT, 8080)
            self.assertEqual(s.BRANCH_TZ, "")
        importlib.reload(settings)


if __name__ == "__main__":
    unittest.main()
