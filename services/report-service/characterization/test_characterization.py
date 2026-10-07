"""Characterization tests for report-service, run against a RUNNING instance over HTTP.

They pin the behaviour observed on the Java 8 / Spring Boot 2.5.15 build so the same file can be
rerun unchanged against any later build. Odd behaviour is pinned as-is, not fixed.

Environment:
  REPORT_SERVICE_URL  base URL of the running service (default http://localhost:8091)

The deployment under test must have ARCHIVE_STORE unset and analytics-service / audit-service /
auth-service unresolvable (as in a standalone docker run), so report generation takes the
sample-data / failure paths deterministically.
"""

import io
import json
import os
import re
import time
import urllib.error
import urllib.request
import uuid
import zipfile

import pytest

BASE = os.environ.get("REPORT_SERVICE_URL", "http://localhost:8091").rstrip("/")
RUN = uuid.uuid4().hex[:8]
OK_USER = "char-ok-" + RUN
FAIL_USER = "char-fail-" + RUN

ISO_MILLIS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}\+00:00$")
ISO_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
ERROR_KEYS = ["timestamp", "status", "error", "path"]
REPORT_KEYS = ["id", "reportName", "category", "reportType", "status", "requestedBy", "dateFrom", "dateTo",
               "createdAt", "completedAt", "fileSizeBytes", "rowCount", "downloadUrl", "errorMessage"]
ARCHIVE_OFF = {"error": "archive feature is not enabled",
               "hint": "archive feature is off; set ARCHIVE_STORE=db2, postgresql or azuresql to enable it"}
RECON_OFF = {"error": "no migration in this namespace",
             "hint": "archive feature is off; set ARCHIVE_STORE=db2, postgresql or azuresql to enable it"}
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class Resp:
    def __init__(self, status, headers, body):
        self.status = status
        self.headers = headers
        self.body = body

    def header(self, name):
        return self.headers.get(name)

    @property
    def content_type(self):
        return self.headers.get("Content-Type")

    def json(self):
        return json.loads(self.body.decode("utf-8"))


def call(method, path, body=None, content_type=None):
    data = None
    headers = {}
    if body is not None:
        data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        headers["Content-Type"] = content_type or "application/json"
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return Resp(r.status, r.headers, r.read())
    except urllib.error.HTTPError as e:
        return Resp(e.code, e.headers, e.read())


def get(path):
    return call("GET", path)


def assert_error_body(resp, status, error, path):
    assert resp.content_type == "application/json"
    body = resp.json()
    assert list(body.keys()) == ERROR_KEYS
    assert ISO_MILLIS.match(body["timestamp"])
    assert body["status"] == status
    assert body["error"] == error
    assert body["path"] == path


def create(name, category, rtype, user, dates=True):
    payload = {"reportName": name, "category": category, "reportType": rtype, "requestedBy": user,
               "parameters": {"metric": "m1"}}
    if dates:
        payload["dateFrom"] = "2026-01-01T00:00:00.000+00:00"
        payload["dateTo"] = "2026-01-31T00:00:00.000+00:00"
    return call("POST", "/api/v1/reports", payload)


def wait_terminal(report_id, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = get("/api/v1/reports/%d" % report_id)
        if r.status == 200 and r.json()["status"] in ("COMPLETED", "FAILED"):
            return r.json()
        time.sleep(0.5)
    raise AssertionError("report %d did not finish" % report_id)


def create_and_wait(name, category, rtype, user):
    r = create(name, category, rtype, user)
    assert r.status == 202, r.body
    return wait_terminal(r.json()["id"])


def normalize_dns(msg):
    return re.sub(r": (Temporary failure in name resolution|Name or service not known|"
                  r"nodename nor servname provided, or not known)", "", msg)


@pytest.fixture(scope="module")
def reports():
    # Created one at a time: report generation shares non-thread-safe date formatters.
    out = {}
    out["csv"] = create_and_wait("Char CSV " + RUN, "USER_ACTIVITY", "CSV", OK_USER)
    out["pdf"] = create_and_wait("Char PDF " + RUN, "STORAGE_SUMMARY", "PDF", OK_USER)
    out["xlsx"] = create_and_wait("Char XLSX " + RUN, "USER_ACTIVITY", "EXCEL", OK_USER)
    out["fail_analytics"] = create_and_wait("Char Fail A " + RUN, "USAGE_ANALYTICS", "CSV", FAIL_USER)
    out["fail_audit"] = create_and_wait("Char Fail B " + RUN, "AUDIT_LOG", "PDF", FAIL_USER)
    return out


# ---------------------------------------------------------------- health / security headers

def test_health():
    r = get("/health")
    assert r.status == 200
    assert r.content_type == "application/json"
    assert r.json() == {"service": "report-service", "version": "0.1.0", "status": "healthy"}


def test_health_trailing_slash_matches():
    r = get("/health/")
    assert r.status == 200
    assert r.json() == {"service": "report-service", "version": "0.1.0", "status": "healthy"}


def test_health_archive_disabled():
    r = get("/health/archive")
    assert r.status == 200
    assert r.content_type == "application/json"
    assert list(r.json().items()) == [("store", "off"), ("namespace", ""), ("status", "disabled")]


@pytest.mark.parametrize("path", ["/health", "/api/v1/reports", "/does-not-exist"])
def test_security_headers(path):
    r = get(path)
    assert r.header("X-Content-Type-Options") == "nosniff"
    assert r.header("X-XSS-Protection") == "1; mode=block"
    assert r.header("X-Frame-Options") == "DENY"
    assert r.header("Cache-Control") == "no-cache, no-store, max-age=0, must-revalidate"
    assert r.header("Pragma") == "no-cache"
    assert r.header("Expires") == "0"
    assert r.header("Set-Cookie") is None
    assert r.header("WWW-Authenticate") is None
    assert r.header("Strict-Transport-Security") is None


# ---------------------------------------------------------------- actuator

def test_actuator_health():
    r = get("/actuator/health")
    assert r.status == 200
    assert r.content_type == "application/vnd.spring-boot.actuator.v3+json"
    assert r.json() == {"status": "UP"}


def test_actuator_info():
    r = get("/actuator/info")
    assert r.status == 200
    assert r.content_type == "application/vnd.spring-boot.actuator.v3+json"
    assert r.json() == {"app": {"name": "OtterWorks Report Service", "version": "0.1.0"}}


def test_actuator_index_links():
    r = get("/actuator")
    assert r.status == 200
    links = r.json()["_links"]
    assert sorted(links) == ["health", "health-path", "info", "prometheus", "self"]
    assert links["health"]["href"].endswith("/actuator/health")


@pytest.mark.parametrize("path", ["/actuator/env", "/actuator/beans", "/actuator/metrics", "/actuator/heapdump"])
def test_actuator_sensitive_endpoints_not_exposed(path):
    r = get(path)
    assert r.status == 404


def test_actuator_prometheus():
    get("/health")
    r = get("/actuator/prometheus")
    assert r.status == 200
    ctype = [p.strip() for p in r.content_type.split(";")]
    assert ctype[0] == "text/plain"
    assert "version=0.0.4" in ctype
    text = r.body.decode("utf-8")
    assert "# TYPE jvm_memory_used_bytes gauge" in text
    assert re.search(r'^http_server_requests_seconds_count\{[^}]*method="GET"[^}]*status="200"[^}]*uri="/health"',
                     text, re.M)


# ---------------------------------------------------------------- generic errors

@pytest.mark.parametrize("path", ["/does-not-exist", "/metrics", "/login", "/api/v1/nope"])
def test_unknown_path_404(path):
    r = get(path)
    assert r.status == 404
    assert_error_body(r, 404, "Not Found", path)


def test_method_not_allowed():
    r = call("POST", "/health", {})
    assert r.status == 405
    assert r.header("Allow") == "GET"
    assert_error_body(r, 405, "Method Not Allowed", "/health")


# ---------------------------------------------------------------- API docs

def test_swagger_v2_api_docs():
    r = get("/v2/api-docs")
    assert r.status == 200
    assert r.content_type == "application/json"
    doc = r.json()
    assert doc["swagger"] == "2.0"
    assert doc["info"]["title"] == "OtterWorks Report Service API"
    assert doc["info"]["version"] == "0.1.0"
    assert {p: sorted(v) for p, v in doc["paths"].items()} == {
        "/api/v1/reports": ["get", "post"],
        "/api/v1/reports/{id}": ["delete", "get"],
        "/api/v1/reports/{id}/download": ["get"],
        "/health": ["get"],
        "/health/archive": ["get"],
    }


def test_swagger_ui():
    r = get("/swagger-ui/index.html")
    assert r.status == 200
    assert r.content_type.startswith("text/html")


# ---------------------------------------------------------------- create

def test_create_report_accepted():
    r = create("Char Create " + RUN, "USER_ACTIVITY", "CSV", "char-create-" + RUN)
    assert r.status == 202
    assert r.content_type == "application/json"
    body = r.json()
    assert list(body.keys()) == REPORT_KEYS
    assert isinstance(body["id"], int)
    assert body["reportName"] == "Char Create " + RUN
    assert body["category"] == "USER_ACTIVITY"
    assert body["reportType"] == "CSV"
    assert body["status"] == "PENDING"
    assert body["requestedBy"] == "char-create-" + RUN
    assert body["dateFrom"] == "2026-01-01T00:00:00.000+00:00"
    assert body["dateTo"] == "2026-01-31T00:00:00.000+00:00"
    assert ISO_MILLIS.match(body["createdAt"])
    for k in ("completedAt", "fileSizeBytes", "rowCount", "downloadUrl", "errorMessage"):
        assert body[k] is None
    wait_terminal(body["id"])


def test_create_report_default_date_range_is_30_days():
    r = create("Char Defaults " + RUN, "USER_ACTIVITY", "CSV", "char-create-" + RUN, dates=False)
    assert r.status == 202
    body = r.json()
    assert ISO_MILLIS.match(body["dateFrom"]) and ISO_MILLIS.match(body["dateTo"])
    fmt = "%Y-%m-%dT%H:%M:%S.%f%z"
    from datetime import datetime
    d_from = datetime.strptime(body["dateFrom"].replace("+00:00", "+0000"), fmt)
    d_to = datetime.strptime(body["dateTo"].replace("+00:00", "+0000"), fmt)
    assert abs((d_to - d_from).total_seconds() - 30 * 86400) < 5
    wait_terminal(body["id"])


def test_create_validation_error():
    r = call("POST", "/api/v1/reports", {})
    assert r.status == 400
    assert_error_body(r, 400, "Bad Request", "/api/v1/reports")


def test_create_blank_name_validation_error():
    r = call("POST", "/api/v1/reports", {"reportName": "  ", "category": "USER_ACTIVITY", "reportType": "CSV",
                                          "requestedBy": "u"})
    assert r.status == 400
    assert_error_body(r, 400, "Bad Request", "/api/v1/reports")


def test_create_malformed_json():
    r = call("POST", "/api/v1/reports", b"not json")
    assert r.status == 400
    assert_error_body(r, 400, "Bad Request", "/api/v1/reports")


def test_create_unknown_enum():
    r = call("POST", "/api/v1/reports", {"reportName": "x", "category": "NOPE", "reportType": "CSV",
                                          "requestedBy": "u"})
    assert r.status == 400
    assert_error_body(r, 400, "Bad Request", "/api/v1/reports")


def test_create_wrong_content_type():
    r = call("POST", "/api/v1/reports", b"x", content_type="text/plain")
    assert r.status == 415
    assert r.header("Accept") == "application/json, application/*+json"
    assert_error_body(r, 415, "Unsupported Media Type", "/api/v1/reports")


# ---------------------------------------------------------------- get

def test_get_unknown_report():
    r = get("/api/v1/reports/987654321")
    assert r.status == 404
    assert r.body == b""


def test_get_non_numeric_id():
    r = get("/api/v1/reports/abc")
    assert r.status == 400
    assert_error_body(r, 400, "Bad Request", "/api/v1/reports/abc")


def test_completed_report_metadata(reports):
    for key in ("csv", "pdf", "xlsx"):
        rep = reports[key]
        assert list(rep.keys()) == REPORT_KEYS
        assert rep["status"] == "COMPLETED"
        assert rep["rowCount"] == 25
        assert rep["fileSizeBytes"] > 0
        assert rep["downloadUrl"] == "/api/v1/reports/%d/download" % rep["id"]
        assert rep["errorMessage"] is None
        assert ISO_MILLIS.match(rep["completedAt"])


def test_failed_report_metadata(reports):
    expected = {
        "fail_analytics": ("analytics-service", "8088", "/api/v1/analytics/events"),
        "fail_audit": ("audit-service", "8090", "/api/v1/audit/events"),
    }
    for key, (host, port, path) in expected.items():
        rep = reports[key]
        assert rep["status"] == "FAILED"
        assert rep["rowCount"] is None
        assert rep["fileSizeBytes"] is None
        assert rep["downloadUrl"] is None
        assert ISO_MILLIS.match(rep["completedAt"])
        assert normalize_dns(rep["errorMessage"]) == (
            'org.springframework.web.client.ResourceAccessException: I/O error on GET request for '
            '"http://%s:%s%s": %s; nested exception is java.net.UnknownHostException: %s'
            % (host, port, path, host, host))


# ---------------------------------------------------------------- download

def _download(rep):
    r = get(rep["downloadUrl"])
    assert r.status == 200
    assert int(r.header("Content-Length")) == len(r.body) == rep["fileSizeBytes"]
    return r


def test_download_csv(reports):
    rep = reports["csv"]
    r = _download(rep)
    assert r.content_type == "text/csv"
    assert re.match(r'^attachment; filename="char_csv_%s_\d{8}_\d{6}\.csv"$' % RUN, r.header("Content-Disposition"))
    lines = r.body.decode("utf-8").splitlines()
    assert lines[0] == '"# OtterWorks Report: Char CSV %s"' % RUN
    assert re.match(r'^"# Generated: [A-Z][a-z]{2} \d{2}, \d{4} \d{2}:\d{2}"$', lines[1])
    assert lines[2] == '"# Period: Jan 01, 2026 00:00 to Jan 31, 2026 00:00"'
    assert lines[3] == '"# Rows: 25"'
    assert lines[4] == '"# Generated by OtterWorks Reporting | INTERNAL USE ONLY"'
    assert lines[5] == '""'
    assert lines[6] == ('"storage_used_mb","docs_created","user_id","collaborations","last_login","active",'
                        '"files_uploaded","email"')
    rows = lines[7:]
    assert len(rows) == 25
    first = rows[0].split(",")
    assert first[:4] == ['"100"', '"5"', '"user-000"', '"0"']
    assert ISO_Z.match(first[4].strip('"'))
    assert first[5:] == ['"false"', '"10"', '"user0@otterworks.example.com"']
    assert rows[24].split(",")[:4] == ['"1300"', '"53"', '"user-024"', '"96"']


def test_download_pdf(reports):
    rep = reports["pdf"]
    r = _download(rep)
    assert r.content_type == "application/pdf"
    assert re.match(r'^attachment; filename="char_pdf_%s_\d{8}_\d{6}\.pdf"$' % RUN, r.header("Content-Disposition"))
    assert r.body.startswith(b"%PDF-1.4")
    assert r.body.rstrip().endswith(b"%%EOF")


def test_download_excel(reports):
    rep = reports["xlsx"]
    r = _download(rep)
    assert r.content_type == XLSX
    assert re.match(r'^attachment; filename="char_xlsx_%s_\d{8}_\d{6}\.xlsx"$' % RUN,
                    r.header("Content-Disposition"))
    z = zipfile.ZipFile(io.BytesIO(r.body))
    assert z.namelist() == ["[Content_Types].xml", "_rels/.rels", "docProps/app.xml", "docProps/core.xml",
                            "xl/sharedStrings.xml", "xl/styles.xml", "xl/workbook.xml",
                            "xl/_rels/workbook.xml.rels", "xl/worksheets/sheet1.xml", "xl/worksheets/sheet2.xml"]
    strings = re.findall(r"<t[^>]*>([^<]*)</t>", z.read("xl/sharedStrings.xml").decode("utf-8"))
    assert strings[:8] == ["OtterWorks Report", "Report Name:", "Char XLSX " + RUN, "Category:", "USER_ACTIVITY",
                           "Period:", "Jan 01, 2026 00:00 to Jan 31, 2026 00:00", "Generated:"]
    for s in ("Storage used mb", "Docs created", "User id", "user-000", "user24@otterworks.example.com"):
        assert s in strings
    sheets = re.findall(r'<sheet [^>]*name="([^"]+)"', z.read("xl/workbook.xml").decode("utf-8"))
    assert len(sheets) == 2


def test_download_failed_report_404(reports):
    r = get("/api/v1/reports/%d/download" % reports["fail_analytics"]["id"])
    assert r.status == 404
    assert r.body == b""


def test_download_unknown_report_404():
    r = get("/api/v1/reports/987654321/download")
    assert r.status == 404
    assert r.body == b""


def test_report_name_template_tokens_are_literal():
    name = "Char Tpl ${base64Decoder:SGVsbG8=} ${env:HOME} " + RUN
    rep = create_and_wait(name, "USER_ACTIVITY", "CSV", "char-tpl-" + RUN)
    assert rep["status"] == "COMPLETED"
    r = get(rep["downloadUrl"])
    assert r.body.decode("utf-8").splitlines()[0] == '"# OtterWorks Report: %s"' % name


# ---------------------------------------------------------------- list

def test_list_by_user_ordered_desc(reports):
    r = get("/api/v1/reports?userId=" + OK_USER)
    assert r.status == 200
    body = r.json()
    assert sorted(body.keys()) == ["reports", "total"]
    assert body["total"] == 3
    assert [x["id"] for x in body["reports"]] == [reports["xlsx"]["id"], reports["pdf"]["id"], reports["csv"]["id"]]
    assert list(body["reports"][0].keys()) == REPORT_KEYS


def test_list_unknown_user_empty():
    r = get("/api/v1/reports?userId=nobody-" + RUN)
    assert r.status == 200
    assert r.json() == {"reports": [], "total": 0}


def test_list_by_user_with_failed_report_is_500(reports):
    # Pinned as-is: the failed report's @Lob error_message cannot be read outside a transaction.
    r = get("/api/v1/reports?userId=" + FAIL_USER)
    assert r.status == 500
    assert_error_body(r, 500, "Internal Server Error", "/api/v1/reports")


def test_list_status_failed_is_500(reports):
    r = get("/api/v1/reports?status=FAILED")
    assert r.status == 500
    assert_error_body(r, 500, "Internal Server Error", "/api/v1/reports")


def test_list_status_completed_ascending(reports):
    r = get("/api/v1/reports?status=COMPLETED")
    assert r.status == 200
    body = r.json()
    ids = [x["id"] for x in body["reports"]]
    assert body["total"] == len(ids)
    ours = [reports[k]["id"] for k in ("csv", "pdf", "xlsx")]
    assert [i for i in ids if i in ours] == ours
    assert all(x["status"] == "COMPLETED" for x in body["reports"])


def test_list_default_is_completed(reports):
    default_ids = [x["id"] for x in get("/api/v1/reports").json()["reports"]]
    completed_ids = [x["id"] for x in get("/api/v1/reports?status=COMPLETED").json()["reports"]]
    assert default_ids == completed_ids


def test_list_trailing_slash(reports):
    r = get("/api/v1/reports/?userId=" + OK_USER)
    assert r.status == 200
    assert r.json()["total"] == 3


def test_list_user_filter_wins_over_status(reports):
    r = get("/api/v1/reports?userId=%s&status=PENDING" % OK_USER)
    assert r.status == 200
    assert r.json()["total"] == 3


def test_list_bad_status():
    r = get("/api/v1/reports?status=BOGUS")
    assert r.status == 400
    assert_error_body(r, 400, "Bad Request", "/api/v1/reports")


# ---------------------------------------------------------------- delete

def test_delete_completed_report():
    rep = create_and_wait("Char Delete " + RUN, "USER_ACTIVITY", "CSV", "char-del-" + RUN)
    r = call("DELETE", "/api/v1/reports/%d" % rep["id"])
    assert r.status == 204
    assert r.body == b""
    assert get("/api/v1/reports/%d" % rep["id"]).status == 404
    assert get("/api/v1/reports/%d/download" % rep["id"]).status == 404
    again = call("DELETE", "/api/v1/reports/%d" % rep["id"])
    assert again.status == 404
    assert again.body == b""


def test_delete_failed_report():
    rep = create_and_wait("Char Delete Fail " + RUN, "COMPLIANCE", "CSV", "char-del-" + RUN)
    assert rep["status"] == "FAILED"
    r = call("DELETE", "/api/v1/reports/%d" % rep["id"])
    assert r.status == 204
    assert get("/api/v1/reports/%d" % rep["id"]).status == 404


def test_delete_unknown_report():
    r = call("DELETE", "/api/v1/reports/987654321")
    assert r.status == 404
    assert r.body == b""


# ---------------------------------------------------------------- archive / reconciliation (feature off)

ARCHIVE_PREFIXES = ["/api/archive/documents", "/api/v1/archive/documents", "/api/v1/reports/archive/documents"]


@pytest.mark.parametrize("prefix", ARCHIVE_PREFIXES)
@pytest.mark.parametrize("suffix", ["/DOC-1", "/DOC-1?raw=true", "/DOC-1/hash"])
def test_archive_feature_off(prefix, suffix):
    r = get(prefix + suffix)
    assert r.status == 404
    assert r.content_type == "application/json"
    assert list(r.json().items()) == list(ARCHIVE_OFF.items())


@pytest.mark.parametrize("prefix", ["/api/reports/reconciliation", "/api/v1/reports/reconciliation"])
@pytest.mark.parametrize("suffix", ["", "/latest", "/run-1", "/latest.csv", "/run-1.csv"])
def test_reconciliation_feature_off(prefix, suffix):
    r = get(prefix + suffix)
    assert r.status == 404
    assert r.content_type == "application/json"
    assert list(r.json().items()) == list(RECON_OFF.items())
    assert r.header("Content-Disposition") is None


@pytest.mark.parametrize("prefix", ["/api/reports/reconciliation", "/api/v1/reports/reconciliation"])
def test_reconciliation_html_feature_off(prefix):
    r = get(prefix + "/run-1.html")
    assert r.status == 404
    assert r.content_type == "application/json"
    assert list(r.json().items()) == list(RECON_OFF.items())
    assert r.header("Content-Disposition") == "inline;filename=f.txt"
