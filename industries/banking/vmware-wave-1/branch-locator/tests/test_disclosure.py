import importlib
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
import settings
settings.LOG_FILE = os.devnull
settings.TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "templates")
locator = importlib.import_module("locator")


class DisclosureTest(unittest.TestCase):
    def setUp(self):
        self.client = locator.app.test_client()

    def test_reflected_query_and_logs_do_not_disclose_accounts(self):
        for account in ["HG611000001", "IT01W1000001", "12345678901"]:
            with patch.object(locator, "locate", return_value=(10, -30)), \
                    patch.object(locator, "branches", return_value=[]), \
                    self.assertLogs("branch-locator", level="INFO") as captured:
                response = self.client.get("/api/nearest", query_string={"q": account})
            self.assertEqual(response.status_code, 200)
            self.assertNotIn(account, response.get_data(as_text=True))
            self.assertNotIn(account, " ".join(captured.output))

    def test_normal_empty_and_error_queries_are_safe(self):
        with patch.object(locator, "locate", return_value=(10, -30)), \
                patch.object(locator, "branches", return_value=[]):
            self.assertEqual(self.client.get("/api/nearest?q=harbour").get_json()["branches"], [])
        self.assertEqual(self.client.get("/api/nearest").status_code, 400)
        with patch.object(locator, "locate", side_effect=RuntimeError("HG611000001")):
            response = self.client.get("/api/nearest?q=HG611000001")
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("HG611000001", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
