import logging
import os
import sys
import unittest

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
basic_config = logging.basicConfig
try:
    logging.basicConfig = lambda **kwargs: None
    import locator
finally:
    logging.basicConfig = basic_config


class LocatorTest(unittest.TestCase):
    def setUp(self):
        self.original_locate = locator.locate
        self.original_branches = locator.branches
        self.locate_calls = []
        self.branches_calls = []
        locator.locate = self.locate
        locator.branches = self.branches
        self.client = locator.app.test_client()
        self.logs = StringIO()
        self.handler = logging.StreamHandler(self.logs)
        self.level = locator.log.level
        locator.log.addHandler(self.handler)
        locator.log.setLevel(logging.INFO)

    def tearDown(self):
        locator.locate = self.original_locate
        locator.branches = self.original_branches
        locator.log.removeHandler(self.handler)
        locator.log.setLevel(self.level)
        self.handler.close()
        self.logs.close()

    def locate(self, query):
        self.locate_calls.append(query)
        return 10.0, -30.0

    def branches(self):
        self.branches_calls.append(True)
        return []

    def assert_query_logged_safely(self, query):
        response = self.client.get("/api/nearest", query_string={"q": query})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {
            "query": query, "lat": 10.0, "lon": -30.0, "branches": [],
        })
        self.assertEqual(self.locate_calls, [query])
        self.assertEqual(self.branches_calls, [True])
        message = self.logs.getvalue()
        self.assertEqual(message, "nearest q=%r -> []\n" % query)
        self.assertEqual(len(message.splitlines()), 1)
        for control in u"\r\n\t\x00\x1b\x85\u2028\u2029":
            self.assertNotIn(control, message[:-1])

    def test_normal_query(self):
        self.assert_query_logged_safely(u"Central")

    def test_lf_query(self):
        self.assert_query_logged_safely(
            u"foo\n2026-01-01 00:00:00,000 INFO forged")

    def test_cr_query(self):
        self.assert_query_logged_safely(u"foo\rforged")

    def test_crlf_query(self):
        self.assert_query_logged_safely(u"foo\r\nforged")

    def test_other_control_characters(self):
        self.assert_query_logged_safely(
            u"foo\t\x00\x1b\x85\u2028\u2029forged")

    def test_empty_queries(self):
        for query in (u"", u" \r\n "):
            response = self.client.get("/api/nearest",
                                       query_string={"q": query})
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.get_json(), {"error": "q is required"})
        self.assertEqual(self.locate_calls, [])
        self.assertEqual(self.branches_calls, [])
        self.assertEqual(self.logs.getvalue(), "")

    def test_geocoder_error_does_not_log_success(self):
        def unavailable(query):
            raise RuntimeError("geocoder unavailable")

        locator.locate = unavailable
        response = self.client.get("/api/nearest",
                                   query_string={"q": u"Central"})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.branches_calls, [])
        self.assertEqual(self.logs.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
