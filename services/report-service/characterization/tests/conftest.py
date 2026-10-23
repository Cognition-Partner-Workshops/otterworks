"""Shared helpers for the report-service characterization suite.

Black-box only: plain HTTP against the running containers (see ../run.sh), no Spring or JVM
types, so the same files run before and after the Java 17 / Spring Boot 3 upgrade.

Snapshots: ``snapshot(name, value)`` compares a JSON-able value with
``baseline/snapshots/<name>.json``. ``CHAR_RECORD=1`` (``./run.sh record``) rewrites them; that is
done once on the reference (Java 8) code and the files are committed as the baseline.
"""
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests

URLS = {
    "off": os.environ.get("CHAR_URL_OFF", "http://localhost:18091"),
    "db2": os.environ.get("CHAR_URL_DB2", "http://localhost:18092"),
    "pg": os.environ.get("CHAR_URL_PG", "http://localhost:18093"),
}
SNAPSHOTS = Path(__file__).resolve().parents[1] / "baseline" / "snapshots"
RECORD = os.environ.get("CHAR_RECORD") == "1"
RUN_TOKEN = os.environ.get("CHAR_RUN_TOKEN", "char-%d" % int(time.time()))

# Request window used by every generated report: 03:30 UTC is still the previous day in
# America/Chicago, so a UTC-pinned format and a TZ-default format cannot coincide.
DATE_FROM = "2026-01-15T03:30:00Z"
DATE_TO = "2026-01-16T03:30:00Z"

HEADERS_OF_INTEREST = (
    "Content-Type", "Content-Disposition", "Content-Length", "X-Frame-Options",
    "X-Content-Type-Options", "X-XSS-Protection", "Cache-Control", "Pragma", "Expires",
)

FILE_TS = re.compile(r"_(\d{8}_\d{6})\.(csv|pdf|xlsx)\"$")
JSON_TS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}\+00:00$")
DISPLAY_TS = re.compile(r"^[A-Z][a-z]{2} \d{2}, \d{4} \d{2}:\d{2}$")


def url(instance, path):
    return URLS[instance] + path


def http(method, instance, path, **kwargs):
    kwargs.setdefault("timeout", 30)
    kwargs.setdefault("allow_redirects", False)
    return requests.request(method, url(instance, path), **kwargs)


def headers_of(resp, names=HEADERS_OF_INTEREST):
    return {n: resp.headers[n] for n in names if n in resp.headers}


def body_of(resp):
    ctype = resp.headers.get("Content-Type", "")
    if "json" in ctype:
        try:
            return resp.json()
        except ValueError:
            return resp.text
    return resp.text


def error_shape(resp):
    """Spring's default error body carries a timestamp; keep everything else, sorted keys."""
    body = body_of(resp)
    if isinstance(body, dict):
        body = {k: ("<timestamp>" if k == "timestamp" else v) for k, v in sorted(body.items())}
    return {"status": resp.status_code, "content_type": resp.headers.get("Content-Type"), "body": body}


def utc_file_stamp(stamp):
    return datetime.strptime(stamp, "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)


def assert_recent_utc(moment, slack_seconds=600):
    now = datetime.now(timezone.utc)
    assert abs((now - moment).total_seconds()) < slack_seconds, (
        "%s is not the current UTC time (%s); a zone other than UTC was applied" % (moment, now))


def normalize_disposition(value):
    """Checks the file-name stamp is the current UTC time and replaces it with a placeholder."""
    if value is None:
        return None
    m = FILE_TS.search(value)
    assert m, value
    assert_recent_utc(utc_file_stamp(m.group(1)))
    return value[:m.start(1)] + "<yyyyMMdd_HHmmss>" + value[m.end(1):]


def normalize_report(body):
    out = dict(body)
    rid = out.get("id")
    assert isinstance(rid, int)
    out["id"] = "<id>"
    for key in ("createdAt", "completedAt"):
        if out.get(key) is not None:
            assert JSON_TS.match(out[key]), (key, out[key])
            out[key] = "<timestamp>"
    if out.get("downloadUrl"):
        assert out["downloadUrl"] == "/api/v1/reports/%d/download" % rid
        out["downloadUrl"] = "/api/v1/reports/<id>/download"
    if isinstance(out.get("requestedBy"), str):
        out["requestedBy"] = out["requestedBy"].replace(RUN_TOKEN, "<run>")
    return out


def create_report(instance, name, category, report_type, dates=True, parameters=None, **extra):
    payload = {
        "reportName": name,
        "category": category,
        "reportType": report_type,
        "requestedBy": "%s-%s" % (RUN_TOKEN, name.lower().replace(" ", "-")),
    }
    if dates:
        payload["dateFrom"] = DATE_FROM
        payload["dateTo"] = DATE_TO
    if parameters is not None:
        payload["parameters"] = parameters
    payload.update(extra)
    resp = http("POST", instance, "/api/v1/reports", json=payload)
    assert resp.status_code == 202, resp.text
    return resp


def wait_for_report(instance, report_id, timeout=60):
    deadline = time.time() + timeout
    while True:
        resp = http("GET", instance, "/api/v1/reports/%d" % report_id)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        if body["status"] in ("COMPLETED", "FAILED"):
            return body
        assert time.time() < deadline, "report %d still %s" % (report_id, body["status"])
        time.sleep(0.5)


def generate(instance, name, category, report_type, **kwargs):
    created = create_report(instance, name, category, report_type, **kwargs).json()
    return wait_for_report(instance, created["id"])


def _canonical(value):
    return json.loads(json.dumps(value, ensure_ascii=False))


@pytest.fixture
def snapshot():
    def check(name, value):
        path = SNAPSHOTS / ("%s.json" % name)
        value = _canonical(value)
        if RECORD:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            return
        assert path.exists(), "no baseline %s: record it on the reference code (./run.sh record)" % path
        expected = json.loads(path.read_text(encoding="utf-8"))
        assert value == expected, "differs from baseline %s" % path.name
    return check


@pytest.fixture(scope="session", autouse=True)
def stack_is_up():
    for name in URLS:
        try:
            resp = http("GET", name, "/health", timeout=5)
        except requests.RequestException as exc:
            pytest.exit("report-service instance %s is not reachable at %s (%s); run ./run.sh up"
                        % (name, URLS[name], exc), returncode=3)
        if resp.status_code != 200:
            pytest.exit("instance %s /health answered %s" % (name, resp.status_code), returncode=3)


def days(n):
    return timedelta(days=n)
