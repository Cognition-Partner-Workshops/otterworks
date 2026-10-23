"""ReportController under /api/v1/reports: request validation, status codes, JSON shapes."""
import re

import pytest

from conftest import DATE_FROM, RUN_TOKEN, create_report, error_shape, generate, http, normalize_report, wait_for_report


def test_create_returns_202_and_echoes_request(snapshot):
    resp = create_report("off", "Api Create", "USAGE_ANALYTICS", "PDF")
    body = resp.json()
    assert body["status"] in ("PENDING", "GENERATING", "COMPLETED")
    body["status"] = "<pending|generating|completed>"
    snapshot("create_202", {"status": resp.status_code, "content_type": resp.headers.get("Content-Type"),
                            "body": normalize_report(body)})


@pytest.mark.parametrize("dates,label", [
    ({"dateFrom": "2026-01-15T03:30:00Z", "dateTo": "2026-01-16T03:30:00.250+00:00"}, "iso"),
    ({"dateFrom": "2026-01-15", "dateTo": "2026-01-16"}, "date_only"),
    ({"dateFrom": 1768447800000, "dateTo": 1768534200000}, "epoch_millis"),
    ({"dateFrom": "2026-01-14T21:30:00-06:00", "dateTo": "2026-01-15T21:30:00-0600"}, "offset"),
])
def test_request_date_parsing_and_json_date_format(dates, label, snapshot):
    resp = create_report("off", "Api Dates %s" % label, "USER_ACTIVITY", "CSV", dates=False, **dates)
    body = resp.json()
    snapshot("dates__%s" % label, {"dateFrom": body["dateFrom"], "dateTo": body["dateTo"]})
    wait_for_report("off", body["id"])


@pytest.mark.parametrize("missing", ["reportName", "category", "reportType", "requestedBy"])
def test_create_missing_required_field_is_400(missing, snapshot):
    payload = {"reportName": "x", "category": "AUDIT_LOG", "reportType": "CSV", "requestedBy": RUN_TOKEN}
    del payload[missing]
    snapshot("create_missing__%s" % missing, error_shape(http("POST", "off", "/api/v1/reports", json=payload)))


def test_create_blank_name_bad_enum_and_bad_json(snapshot):
    blank = {"reportName": "  ", "category": "AUDIT_LOG", "reportType": "CSV", "requestedBy": RUN_TOKEN}
    snapshot("create_blank_name", error_shape(http("POST", "off", "/api/v1/reports", json=blank)))
    enum = {"reportName": "x", "category": "NOPE", "reportType": "CSV", "requestedBy": RUN_TOKEN}
    snapshot("create_bad_enum", error_shape(http("POST", "off", "/api/v1/reports", json=enum)))
    snapshot("create_bad_json", error_shape(http("POST", "off", "/api/v1/reports", data="{not json",
                                                 headers={"Content-Type": "application/json"})))
    snapshot("create_wrong_media_type", error_shape(http("POST", "off", "/api/v1/reports", data="a=b",
                                                         headers={"Content-Type": "text/plain"})))


@pytest.mark.parametrize("path", [
    "/api/v1/reports/999999999",
    "/api/v1/reports/999999999/download",
    "/api/v1/reports/scheduled",
    "/api/v1/reports/abc/download",
    "/api/v1/reports?status=BOGUS",
])
def test_get_edge_cases(path, snapshot):
    name = path.replace("/api/v1/reports", "reports").replace("/", "_").replace("?", "_q_").replace("=", "-")
    snapshot("get__%s" % name, error_shape(http("GET", "off", path)))


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE"])
def test_scheduled_other_methods(method, snapshot):
    snapshot("scheduled__%s" % method.lower(), error_shape(http(method, "off", "/api/v1/reports/scheduled")))


def test_get_by_id_matches_completed_report(snapshot):
    done = generate("off", "Api Get", "AUDIT_LOG", "CSV")
    resp = http("GET", "off", "/api/v1/reports/%d" % done["id"])
    assert resp.status_code == 200
    snapshot("get_completed", normalize_report(resp.json()))


def test_list_by_user_status_and_default(snapshot):
    failed = generate("off", "Api List Failed", "USAGE_ANALYTICS", "CSV", parameters={"metric": "upstream-error"})
    assert failed["status"] == "FAILED"
    user_report = generate("off", "Api List", "USER_ACTIVITY", "CSV")
    user = user_report["requestedBy"]
    by_user = http("GET", "off", "/api/v1/reports", params={"userId": user})
    assert by_user.status_code == 200
    body = by_user.json()
    assert sorted(body) == ["reports", "total"]
    assert body["total"] == len(body["reports"]) == 1
    assert body["reports"][0]["id"] == user_report["id"]

    # With a FAILED row present (its error_message is a @Lob), the status filters answer:
    statuses = {}
    for status in ("COMPLETED", "FAILED", "PENDING", "GENERATING"):
        resp = http("GET", "off", "/api/v1/reports", params={"status": status})
        statuses[status] = error_shape(resp) if resp.status_code != 200 else {"status": 200}
        if resp.status_code == 200:
            assert all(r["status"] == status for r in resp.json()["reports"])
    failed_user = http("GET", "off", "/api/v1/reports", params={"userId": failed["requestedBy"]})
    statuses["userId_of_failed_report"] = error_shape(failed_user) if failed_user.status_code != 200 else {
        "status": 200, "body": [normalize_report(r) for r in failed_user.json()["reports"]]}
    snapshot("list_status_filters", statuses)

    default = http("GET", "off", "/api/v1/reports").json()
    assert default["total"] == len(default["reports"])
    assert all(r["status"] == "COMPLETED" for r in default["reports"])
    assert user_report["id"] in [r["id"] for r in default["reports"]]

    both = http("GET", "off", "/api/v1/reports", params={"userId": user, "status": "FAILED"}).json()
    assert [r["id"] for r in both["reports"]] == [user_report["id"]], "userId wins over status"


def test_delete_lifecycle(snapshot):
    done = generate("off", "Api Delete", "STORAGE_SUMMARY", "EXCEL")
    rid = done["id"]
    steps = [
        ("delete", http("DELETE", "off", "/api/v1/reports/%d" % rid)),
        ("get_after", http("GET", "off", "/api/v1/reports/%d" % rid)),
        ("download_after", http("GET", "off", "/api/v1/reports/%d/download" % rid)),
        ("delete_again", http("DELETE", "off", "/api/v1/reports/%d" % rid)),
    ]
    snapshot("delete_lifecycle", {name: {"status": r.status_code, "body": r.text} for name, r in steps})


def test_failed_report_and_download(snapshot):
    failed = generate("off", "Api Upstream Error", "USAGE_ANALYTICS", "CSV",
                      parameters={"metric": "upstream-error"})
    dl = http("GET", "off", "/api/v1/reports/%d/download" % failed["id"])
    snapshot("failed_upstream_500", {"report": normalize_report(failed),
                                     "download": {"status": dl.status_code, "body": dl.text}})


def test_unreachable_upstreams(snapshot):
    """db2/pg instances point the three upstream URLs at an unresolvable host."""
    out = {}
    for category in ("USAGE_ANALYTICS", "AUDIT_LOG", "USER_ACTIVITY"):
        report = generate("db2", "Api Unreachable %s" % category, category, "CSV")
        message = report["errorMessage"]
        if message:
            # The resolver's wording ("Name or service not known" or not) varies run to run.
            m = re.match(r'^(\S+): I/O error on GET request for "([^"]+)"', message)
            assert m, message
            assert "java.net.UnknownHostException: unreachable.invalid" in message
            message = {"exception": m.group(1), "url": m.group(2),
                       "nested": "nested exception is java.net.UnknownHostException" in message}
        out[category] = {"status": report["status"], "rowCount": report["rowCount"],
                         "errorMessage": message}
    snapshot("unreachable_upstreams", out)


def test_date_from_is_echoed_in_utc():
    resp = create_report("off", "Api Echo", "USER_ACTIVITY", "CSV")
    assert resp.json()["dateFrom"] == DATE_FROM.replace("Z", ".000+00:00")
    wait_for_report("off", resp.json()["id"])
