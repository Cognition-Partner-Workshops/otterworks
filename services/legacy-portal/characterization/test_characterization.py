#!/usr/bin/env python3
"""Characterization tests for legacy-portal, run against a RUNNING instance over HTTP.

They pin the behavior the module has today (status codes, the headers that matter, JSON bodies
and their key order, error shapes, the absence of auth) so the same file can be rerun unchanged
after a runtime/framework upgrade. Odd behavior is pinned as-is, not fixed.

Environment:
  BASE_URL      base URL of the running module (default http://localhost:8095)
  CHAR_BACKEND  h2 | postgres (default h2). Only used for the one check whose answer depends on
                the database, not the runtime: the row order of an unsorted findAll() after an
                UPDATE.

The suite is ordered and stateful: start it against a FRESH database (restart the H2 process, or
`docker compose -f docker-compose.onprem.yml down -v` before `up`). Standard library only.

  BASE_URL=http://localhost:8095 python3 characterization/test_characterization.py
"""
import http.client
import json
import os
import re
import sys
import unittest
import urllib.parse

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8095").rstrip("/")
BACKEND = os.environ.get("CHAR_BACKEND", "h2").lower()

ISO_INSTANT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,9})?Z$")
SPRING_ERROR_TS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}\+00:00$")
ERROR_KEYS = ["timestamp", "status", "error", "path"]
ANN_KEYS = ["id", "title", "body", "published", "createdAt"]
PREF_KEYS = ["userId", "theme", "locale", "emailNotifications"]
FB_KEYS = ["id", "userId", "rating", "message", "createdAt"]
# Actuator answers in the media type the client asked for; these tests send Accept: application/json.
ACTUATOR_JSON = "application/json"
ACTUATOR_V3 = "application/vnd.spring-boot.actuator.v3+json"


class Response:
    def __init__(self, status, headers, raw):
        self.status = status
        self.headers = headers
        self.raw = raw
        self.text = raw.decode("utf-8", errors="replace")

    @property
    def media(self):
        return (self.headers.get("content-type") or "").split(";")[0].strip().lower()

    def json(self):
        return json.loads(self.text)

    def __repr__(self):
        return f"<{self.status} {self.headers.get('content-type')} {self.text[:300]!r}>"


def call(method, path, body=None, content_type="application/json", accept="application/json",
         headers=None):
    url = urllib.parse.urlsplit(BASE_URL)
    conn_cls = http.client.HTTPSConnection if url.scheme == "https" else http.client.HTTPConnection
    conn = conn_cls(url.hostname, url.port, timeout=30)
    hdrs = {}
    if accept is not None:
        hdrs["Accept"] = accept
    payload = None
    if body is not None:
        payload = body if isinstance(body, bytes) else (
            body.encode("utf-8") if isinstance(body, str) else json.dumps(body).encode("utf-8"))
        hdrs["Content-Type"] = content_type
    hdrs.update(headers or {})
    try:
        conn.request(method, url.path + path, body=payload, headers=hdrs)
        resp = conn.getresponse()
        raw = resp.read()
        return Response(resp.status, {k.lower(): v for k, v in resp.getheaders()}, raw)
    finally:
        conn.close()


class LegacyPortalCharacterization(unittest.TestCase):
    """Methods are numbered: unittest runs them in name order and later checks build on earlier state."""

    maxDiff = None

    # ---- helpers -----------------------------------------------------------------------------
    def assertJson(self, r, status, media="application/json"):
        self.assertEqual(r.status, status, r)
        self.assertEqual(r.media, media, r)
        return r.json()

    def assertDefaultError(self, r, status, error, path):
        body = self.assertJson(r, status)
        self.assertEqual(list(body.keys()), ERROR_KEYS, r)
        self.assertRegex(body["timestamp"], SPRING_ERROR_TS)
        self.assertEqual(body["status"], status)
        self.assertEqual(body["error"], error)
        self.assertEqual(body["path"], path)

    def assertPortalError(self, r, status, error, message):
        body = self.assertJson(r, status)
        self.assertEqual(body, {"error": error, "message": message})
        self.assertEqual(list(body.keys()), ["error", "message"])

    def assertAnnouncement(self, item, id_, title, body, published):
        self.assertEqual(list(item.keys()), ANN_KEYS, item)
        self.assertEqual([item["id"], item["title"], item["body"], item["published"]],
                         [id_, title, body, published])
        self.assertRegex(item["createdAt"], ISO_INSTANT)

    def assertFeedback(self, item, id_, user, rating, message):
        self.assertEqual(list(item.keys()), FB_KEYS, item)
        self.assertEqual([item["id"], item["userId"], item["rating"], item["message"]],
                         [id_, user, rating, message])
        self.assertRegex(item["createdAt"], ISO_INSTANT)

    def assertEmpty(self, r, status):
        self.assertEqual(r.status, status, r)
        self.assertEqual(r.raw, b"", r)

    # ---- common: health, actuator, routing, content negotiation, auth ------------------------
    def test_c01_health(self):
        r = call("GET", "/health")
        body = self.assertJson(r, 200)
        self.assertEqual(body, {"status": "UP", "service": "legacy-portal",
                                "banner": "OtterWorks Portal (on-prem) - contact portal-support@otterworks.example"})
        self.assertEqual(list(body.keys()), ["status", "service", "banner"])

    def test_c02_actuator_health(self):
        r = call("GET", "/actuator/health")
        self.assertEqual(self.assertJson(r, 200, ACTUATOR_JSON),
                         {"status": "UP", "groups": ["liveness", "readiness"]})

    def test_c03_actuator_liveness_readiness(self):
        for probe in ("liveness", "readiness"):
            r = call("GET", f"/actuator/health/{probe}")
            self.assertEqual(self.assertJson(r, 200, ACTUATOR_JSON), {"status": "UP"})

    def test_c04_actuator_info_empty(self):
        self.assertEqual(self.assertJson(call("GET", "/actuator/info"), 200, ACTUATOR_JSON), {})

    def test_c05_actuator_discovery_lists_only_health_and_info(self):
        body = self.assertJson(call("GET", "/actuator"), 200, ACTUATOR_JSON)
        self.assertEqual(sorted(body["_links"].keys()), ["health", "health-path", "info", "self"])

    def test_c05b_actuator_default_media_type(self):
        for accept in (None, "*/*"):
            r = call("GET", "/actuator/health", accept=accept)
            self.assertEqual(self.assertJson(r, 200, ACTUATOR_V3)["status"], "UP")

    def test_c06_actuator_other_endpoints_not_exposed(self):
        for ep in ("env", "beans", "metrics", "loggers"):
            self.assertEqual(call("GET", f"/actuator/{ep}").status, 404, ep)

    def test_c07_unmapped_route_default_error(self):
        self.assertDefaultError(call("GET", "/does-not-exist"), 404, "Not Found", "/does-not-exist")

    def test_c08_paths_are_case_sensitive(self):
        self.assertDefaultError(call("GET", "/HEALTH"), 404, "Not Found", "/HEALTH")
        self.assertDefaultError(call("GET", "/Actuator/health"), 404, "Not Found", "/Actuator/health")

    def test_c09_xml_accept_is_406_empty(self):
        self.assertEmpty(call("GET", "/health", accept="application/xml"), 406)

    def test_c10_browser_accept_gets_json(self):
        r = call("GET", "/health", accept="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
        self.assertEqual(self.assertJson(r, 200)["status"], "UP")

    def test_c11_no_auth_required_and_credentials_ignored(self):
        for hdrs in ({}, {"Authorization": "Bearer not-a-real-token"}, {"Authorization": "Basic Zm9vOmJhcg=="}):
            r = call("GET", "/api/preferences/someone", headers=hdrs)
            self.assertEqual(r.status, 200, r)
            self.assertNotIn("www-authenticate", r.headers)
            self.assertNotIn("set-cookie", r.headers)

    def test_c12_head_health(self):
        r = call("HEAD", "/health")
        self.assertEqual(r.status, 200)
        self.assertEqual(r.raw, b"")

    # ---- announcements -------------------------------------------------------------------------
    def test_a01_empty_lists(self):
        self.assertEqual(self.assertJson(call("GET", "/api/announcements"), 200), [],
                         "database is not fresh: restart the module / recreate the DB volume")
        self.assertEqual(self.assertJson(call("GET", "/api/announcements?publishedOnly=false"), 200), [])

    def test_a02_create(self):
        r = call("POST", "/api/announcements", {"title": "Release", "body": "v1 is out", "published": True})
        self.assertAnnouncement(self.assertJson(r, 201), 1, "Release", "v1 is out", True)
        self.assertNotIn("location", r.headers)
        r = call("POST", "/api/announcements", {"title": "Draft", "body": "coming soon"})
        self.assertAnnouncement(self.assertJson(r, 201), 2, "Draft", "coming soon", False)
        r = call("POST", "/api/announcements", {"title": "Second", "body": "another", "published": True})
        self.assertAnnouncement(self.assertJson(r, 201), 3, "Second", "another", True)

    def test_a03_list_published_newest_first(self):
        body = self.assertJson(call("GET", "/api/announcements"), 200)
        self.assertEqual([a["title"] for a in body], ["Second", "Release"])

    def test_a04_get_by_id(self):
        self.assertAnnouncement(self.assertJson(call("GET", "/api/announcements/2"), 200),
                                2, "Draft", "coming soon", False)

    def test_a05_get_unknown_is_portal_404(self):
        self.assertPortalError(call("GET", "/api/announcements/999"), 404, "Not Found",
                               "announcement 999 not found")

    def test_a06_get_non_numeric_and_overflow_id(self):
        # The type-mismatch exception wraps a NumberFormatException (an IllegalArgumentException),
        # so GlobalExceptionHandler's {error,message} shape answers, not Spring's default body.
        self.assertPortalError(call("GET", "/api/announcements/abc"), 400, "Bad Request",
                               'For input string: "abc"')
        self.assertPortalError(call("GET", "/api/announcements/99999999999999999999"), 400,
                               "Bad Request", 'For input string: "99999999999999999999"')

    def test_a07_publish(self):
        self.assertAnnouncement(self.assertJson(call("POST", "/api/announcements/2/publish"), 200),
                                2, "Draft", "coming soon", True)
        self.assertPortalError(call("POST", "/api/announcements/999/publish"), 404, "Not Found",
                               "announcement 999 not found")

    def test_a08_list_after_publish(self):
        published = self.assertJson(call("GET", "/api/announcements"), 200)
        self.assertEqual([a["title"] for a in published], ["Second", "Draft", "Release"])
        everything = self.assertJson(call("GET", "/api/announcements?publishedOnly=false"), 200)
        # findAll() has no ORDER BY: the database decides. PostgreSQL returns the UPDATEd row last.
        expected = [1, 3, 2] if BACKEND == "postgres" else [1, 2, 3]
        self.assertEqual([a["id"] for a in everything], expected)

    def test_a09_validation_errors_are_default_400(self):
        cases = [
            {"body": "no title"},
            {"title": "   ", "body": "blank title"},
            {"title": "x" * 201, "body": "title too long"},
            {"title": "long body", "body": "y" * 4001},
            {"Title": "Case", "body": "property names are case-sensitive"},
        ]
        for payload in cases:
            self.assertDefaultError(call("POST", "/api/announcements", payload), 400, "Bad Request",
                                    "/api/announcements")

    def test_a10_boundary_lengths_accepted(self):
        r = call("POST", "/api/announcements", {"title": "x" * 200, "body": "y" * 4000})
        self.assertAnnouncement(self.assertJson(r, 201), 4, "x" * 200, "y" * 4000, False)

    def test_a11_malformed_and_empty_body(self):
        self.assertDefaultError(call("POST", "/api/announcements", '{"title": '), 400, "Bad Request",
                                "/api/announcements")
        self.assertDefaultError(call("POST", "/api/announcements", b""), 400, "Bad Request",
                                "/api/announcements")

    def test_a12_form_body_is_415(self):
        r = call("POST", "/api/announcements", "title=x", content_type="application/x-www-form-urlencoded")
        self.assertDefaultError(r, 415, "Unsupported Media Type", "/api/announcements")

    def test_a13_method_not_allowed(self):
        r = call("DELETE", "/api/announcements/1")
        self.assertDefaultError(r, 405, "Method Not Allowed", "/api/announcements/1")
        self.assertEqual(r.headers.get("allow"), "GET")
        r = call("PUT", "/api/announcements", {"title": "x", "body": "y"})
        self.assertDefaultError(r, 405, "Method Not Allowed", "/api/announcements")
        self.assertEqual(sorted(r.headers.get("allow", "").replace(" ", "").split(",")), ["GET", "POST"])

    def test_a14_published_only_parsing(self):
        self.assertPortalError(call("GET", "/api/announcements?publishedOnly=abc"), 400, "Bad Request",
                               "Invalid boolean value [abc]")
        self.assertEqual(len(self.assertJson(call("GET", "/api/announcements?publishedOnly=FALSE"), 200)), 4)
        self.assertEqual(len(self.assertJson(call("GET", "/api/announcements?publishedOnly=0"), 200)), 4)

    def test_a15_jackson_coercion_and_unknown_fields(self):
        r = call("POST", "/api/announcements", '{"title":"Coerced","body":"string bool","published":"true"}')
        self.assertAnnouncement(self.assertJson(r, 201), 5, "Coerced", "string bool", True)
        r = call("POST", "/api/announcements",
                 {"title": "Extra", "body": "unknown field ignored", "published": False, "author": "otter"})
        self.assertAnnouncement(self.assertJson(r, 201), 6, "Extra", "unknown field ignored", False)
        r = call("POST", "/api/announcements", '{"title": "Trailing", "body": "tokens"} xyz')
        self.assertAnnouncement(self.assertJson(r, 201), 7, "Trailing", "tokens", False)

    def test_a16_trailing_slash_matches_collection(self):
        body = self.assertJson(call("GET", "/api/announcements/"), 200)
        self.assertEqual([a["title"] for a in body], ["Coerced", "Second", "Draft", "Release"])

    def test_a17_latin1_request_body(self):
        payload = '{"title": "caf\u00e9", "body": "latin-1 body", "published": true}'.encode("iso-8859-1")
        r = call("POST", "/api/announcements", payload, content_type="application/json;charset=ISO-8859-1")
        self.assertAnnouncement(self.assertJson(r, 201), 8, "caf\u00e9", "latin-1 body", True)
        self.assertIn("caf\u00e9".encode("utf-8"), r.raw)

    def test_a18_xml_accept_on_list_is_406_empty(self):
        self.assertEmpty(call("GET", "/api/announcements", accept="application/xml"), 406)

    def test_a19_api_prefix_case_sensitive(self):
        self.assertDefaultError(call("GET", "/API/announcements"), 404, "Not Found", "/API/announcements")

    # ---- user preferences ---------------------------------------------------------------------
    def test_p01_defaults_for_unknown_user(self):
        body = self.assertJson(call("GET", "/api/preferences/newuser"), 200)
        self.assertEqual(body, {"userId": "newuser", "theme": "light", "locale": "en-US",
                                "emailNotifications": True})
        self.assertEqual(list(body.keys()), PREF_KEYS)

    def test_p02_put_then_get(self):
        r = call("PUT", "/api/preferences/u1", {"theme": "dark", "locale": "fr-FR", "emailNotifications": False})
        self.assertEqual(self.assertJson(r, 200), {"userId": "u1", "theme": "dark", "locale": "fr-FR",
                                                   "emailNotifications": False})
        self.assertEqual(self.assertJson(call("GET", "/api/preferences/u1"), 200),
                         {"userId": "u1", "theme": "dark", "locale": "fr-FR", "emailNotifications": False})

    def test_p03_omitted_email_flag_becomes_false(self):
        r = call("PUT", "/api/preferences/u3", {"theme": "light", "locale": "en-US"})
        self.assertEqual(self.assertJson(r, 200)["emailNotifications"], False)

    def test_p04_validation_errors(self):
        for payload in ({"locale": "en-GB", "emailNotifications": True},
                        {"theme": "t" * 21, "locale": "en-GB"},
                        {"theme": "dark", "locale": "  "}):
            self.assertDefaultError(call("PUT", "/api/preferences/u2", payload), 400, "Bad Request",
                                    "/api/preferences/u2")
        self.assertDefaultError(call("PUT", "/api/preferences/u2", "{not json"), 400, "Bad Request",
                                "/api/preferences/u2")
        self.assertDefaultError(call("PUT", "/api/preferences/u2", "theme=dark",
                                     content_type="application/x-www-form-urlencoded"),
                                415, "Unsupported Media Type", "/api/preferences/u2")
        self.assertEqual(self.assertJson(call("GET", "/api/preferences/u2"), 200)["theme"], "light")

    def test_p05_string_boolean_coercion(self):
        r = call("PUT", "/api/preferences/u2", '{"theme":"dark","locale":"de-DE","emailNotifications":"true"}')
        self.assertEqual(self.assertJson(r, 200), {"userId": "u2", "theme": "dark", "locale": "de-DE",
                                                   "emailNotifications": True})

    def test_p06_method_not_allowed(self):
        for method in ("POST", "DELETE"):
            r = call(method, "/api/preferences/u1", {"theme": "dark", "locale": "en-US"} if method == "POST" else None)
            self.assertDefaultError(r, 405, "Method Not Allowed", "/api/preferences/u1")
            self.assertEqual(sorted(r.headers.get("allow", "").replace(" ", "").split(",")), ["GET", "PUT"])

    def test_p07_missing_user_segment_is_404(self):
        self.assertDefaultError(call("GET", "/api/preferences/"), 404, "Not Found", "/api/preferences/")

    def test_p08_encoded_user_id(self):
        self.assertEqual(self.assertJson(call("GET", "/api/preferences/user%20with%20space"), 200)["userId"],
                         "user with space")

    def test_p09_defaults_are_not_persisted(self):
        self.assertEqual(self.assertJson(call("GET", "/api/preferences/newuser"), 200)["theme"], "light")

    # ---- feedback -------------------------------------------------------------------------------
    def test_f01_empty_average_and_list(self):
        body = self.assertJson(call("GET", "/api/feedback/average-rating"), 200)
        self.assertEqual(body, {"averageRating": 0.0})
        self.assertIn('"averageRating":0.0', r'%s' % call("GET", "/api/feedback/average-rating").text)
        self.assertEqual(self.assertJson(call("GET", "/api/feedback?userId=u1"), 200), [])

    def test_f02_submit(self):
        for i, (user, rating, msg) in enumerate([("u1", 5, "great"), ("u1", 3, "ok"), ("u2", 1, "bad")], 1):
            r = call("POST", "/api/feedback", {"userId": user, "rating": rating, "message": msg})
            self.assertFeedback(self.assertJson(r, 201), i, user, rating, msg)
            self.assertNotIn("location", r.headers)

    def test_f03_list_newest_first_and_average(self):
        body = self.assertJson(call("GET", "/api/feedback?userId=u1"), 200)
        self.assertEqual([f["message"] for f in body], ["ok", "great"])
        self.assertEqual(self.assertJson(call("GET", "/api/feedback/average-rating"), 200), {"averageRating": 3.0})

    def test_f04_validation_errors(self):
        for payload in ('{"userId": "u1", "rating": 9, "message": "bad rating"}',
                        '{"userId": "u1", "rating": 0, "message": "zero"}',
                        '{"userId": "u1", "message": "rating omitted"}',
                        '{"userId": "u1", "rating": null, "message": "rating null"}',
                        '{"userId": "u1", "rating": 4, "message": ""}',
                        '{"userId": "%s", "rating": 4, "message": "userId too long"}' % ("u" * 101),
                        '{"userId": ',
                        ):
            self.assertDefaultError(call("POST", "/api/feedback", payload), 400, "Bad Request", "/api/feedback")
        self.assertDefaultError(call("POST", "/api/feedback", "rating=5",
                                     content_type="application/x-www-form-urlencoded"),
                                415, "Unsupported Media Type", "/api/feedback")

    def test_f05_user_id_param(self):
        self.assertDefaultError(call("GET", "/api/feedback"), 400, "Bad Request", "/api/feedback")
        self.assertEqual(self.assertJson(call("GET", "/api/feedback?userId="), 200), [])

    def test_f06_numeric_coercion(self):
        r = call("POST", "/api/feedback", '{"userId":"u3","rating":"4","message":"string rating"}')
        self.assertFeedback(self.assertJson(r, 201), 4, "u3", 4, "string rating")
        r = call("POST", "/api/feedback", '{"userId": "u3", "rating": 4.7, "message": "float rating"}')
        self.assertFeedback(self.assertJson(r, 201), 5, "u3", 4, "float rating")

    def test_f07_non_integral_average(self):
        self.assertEqual(self.assertJson(call("GET", "/api/feedback/average-rating?extra=1"), 200),
                         {"averageRating": 3.4})

    def test_f08_406_after_handler_still_persists(self):
        r = call("POST", "/api/feedback", {"userId": "xml-client", "rating": 5, "message": "saved before 406"},
                 accept="application/xml")
        self.assertEmpty(r, 406)
        body = self.assertJson(call("GET", "/api/feedback?userId=xml-client"), 200)
        self.assertEqual([f["message"] for f in body], ["saved before 406"])

    def test_f09_method_not_allowed_and_case(self):
        r = call("DELETE", "/api/feedback")
        self.assertDefaultError(r, 405, "Method Not Allowed", "/api/feedback")
        self.assertEqual(sorted(r.headers.get("allow", "").replace(" ", "").split(",")), ["GET", "POST"])
        self.assertDefaultError(call("GET", "/api/Feedback?userId=a"), 404, "Not Found", "/api/Feedback")
        self.assertDefaultError(call("GET", "/api/feedback/Average-Rating"), 404, "Not Found",
                                "/api/feedback/Average-Rating")


def main():
    print(f"legacy-portal characterization against {BASE_URL} (backend={BACKEND})", flush=True)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(LegacyPortalCharacterization)
    result = unittest.TextTestRunner(verbosity=2, stream=sys.stdout).run(suite)
    print(f"Tests run: {result.testsRun}, Failures: {len(result.failures)}, "
          f"Errors: {len(result.errors)}, Skipped: {len(result.skipped)}")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
