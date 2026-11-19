import pytest
from werkzeug.exceptions import BadRequest, InternalServerError

from app import select

TENANT = "00000000-0000-0000-0000-000000000001"
INVOICE = "60000000-0000-0000-0000-000000000001"
UNKNOWN = "ffffffff-ffff-ffff-ffff-ffffffffffff"
PERIOD = {"period_start": "2026-02-01", "period_end": "2026-02-28"}
BASE = "/api/v1/billing"
PREVIEW = f"{BASE}/tenants/{TENANT}/invoice-preview"
ISSUE = f"{BASE}/tenants/{TENANT}/invoices"
LINES = f"{BASE}/invoices/{INVOICE}/lines"
LEGACY_RENAMES = {"number": "line_no", "type": "line_type"}  # adapter keeps the old names


def state():
    return {table: select(f"SELECT * FROM billing.{table} ORDER BY id")
            for table in ("rating_periods", "rating_results", "invoices", "invoice_lines", "credit_notes")}


def headers(response, successor):
    assert response.headers["Deprecation"] == "true"
    assert response.headers["Link"] == f'<{successor}>; rel="successor-version"'


@pytest.mark.parametrize("kind,identifier", [("preview", TENANT), ("lines", INVOICE), ("lines", UNKNOWN)])
def test_reads(compare_requests, kind, identifier):
    successor = (f"{BASE}/tenants/{identifier}/invoice-preview" if kind == "preview"
                 else f"{BASE}/invoices/{identifier}/lines")
    old, new = compare_requests(
        {"path": f"/api/invoices/{identifier}/{kind}"},
        {"path": successor, "query_string": PERIOD if kind == "preview" else {}},
        unwrap=True, renames=LEGACY_RENAMES)
    headers(old, successor)
    assert new.json["pagination"] == {"limit": 50, "next_cursor": None}


def test_issue(compare_requests):
    old, new = compare_requests(
        {"path": f"/api/invoices/{TENANT}/issue", "method": "POST", "data": PERIOD},
        {"path": ISSUE, "method": "POST", "json": PERIOD},
        status_map={201: 200}, v1_body=lambda response: {"status": response.json["data"]["status"]},
        state_probe=state)
    headers(old, ISSUE)
    assert new.json["data"] == {"id": select("SELECT id FROM billing.invoices WHERE tenant_id = %s AND issued_at = '2026-02-28'", (TENANT,))[0]["id"],
                                "tenant_id": TENANT, **PERIOD, "status": "issued"}
    assert new.headers["Location"] == f"{BASE}/invoices/{new.json['data']['id']}/lines"


@pytest.mark.parametrize("kind,legacy_kwargs,v1_kwargs,old_status,new_status", [
    ("preview", {"query_string": {"period_start": "bad"}}, {"query_string": {**PERIOD, "period_start": "bad"}}, 500, 400),
    ("lines", {}, {}, 500, 400),
    ("issue", {"data": {}}, {"json": {}}, 400, 400),
    ("issue", {"data": {**PERIOD, "period_end": "bad"}}, {"json": {**PERIOD, "period_end": "bad"}}, 500, 400),
    ("issue", {"data": {**PERIOD, "period_end": "2026-01-01"}}, {"json": {**PERIOD, "period_end": "2026-01-01"}}, 500, 422),
])
def test_errors(compare_requests, kind, legacy_kwargs, v1_kwargs, old_status, new_status):
    identifier = "bad" if kind == "lines" else TENANT
    successor = {"preview": PREVIEW, "issue": ISSUE, "lines": f"{BASE}/invoices/bad/lines"}[kind]
    method = "POST" if kind == "issue" else "GET"
    old, new = compare_requests(
        {"path": f"/api/invoices/{identifier}/{kind}", "method": method, **legacy_kwargs},
        {"path": successor, "method": method, **v1_kwargs},
        status_map={new_status: old_status},
        legacy_body=lambda response: response.status_code,
        v1_body=lambda response: old_status,
        state_probe=state if kind == "issue" else None)
    expected = BadRequest() if old_status == 400 else InternalServerError()
    assert old.data == expected.get_response().data
    headers(old, successor)
    assert new.content_type == "application/json"
    assert new.json["error"]["code"] == ("invalid_request" if new_status == 400 else "unprocessable")


@pytest.mark.parametrize("path,kwargs", [
    (PREVIEW, {}), (PREVIEW, {"query_string": {"period_start": PERIOD["period_start"]}}),
    (PREVIEW, {"query_string": {**PERIOD, "period_start": "2026-02-30"}}),
    (LINES, {"query_string": {"limit": "0"}}), (LINES, {"query_string": {"limit": "201"}}),
    (LINES, {"query_string": {"cursor": "bad"}}),
    (ISSUE, {"method": "POST", "json": {}}),
    (ISSUE, {"method": "POST", "json": {"period_start": PERIOD["period_start"]}}),
    (ISSUE, {"method": "POST", "json": []}),
    (ISSUE, {"method": "POST", "data": "{", "content_type": "application/json"}),
    (ISSUE, {"method": "POST", "data": PERIOD}),
    (f"{BASE}/tenants/bad/invoices", {"method": "POST", "json": PERIOD}),
])
def test_invalid_inputs(client, path, kwargs):
    response = client.open(path, **kwargs)
    assert response.status_code == 400
    assert response.content_type == "application/json"
    assert response.json["error"]["code"] == "invalid_request"
    assert isinstance(response.json["error"]["details"], list)


@pytest.mark.parametrize("path,filters", [(PREVIEW, PERIOD), (LINES, {})])
def test_pagination(client, path, filters):
    full = client.get(path, query_string=filters).json["data"]
    collected = []
    query = {**filters, "limit": 1}
    while True:
        response = client.get(path, query_string=query)
        assert response.status_code == 200
        collected.extend(response.json["data"])
        cursor = response.json["pagination"]["next_cursor"]
        if cursor is None:
            break
        query["cursor"] = cursor
    assert collected == full


def test_unknown_tenant_issue(compare_requests):
    old, new = compare_requests(
        {"path": f"/api/invoices/{UNKNOWN}/issue", "method": "POST", "data": PERIOD},
        {"path": f"{BASE}/tenants/{UNKNOWN}/invoices", "method": "POST", "json": PERIOD},
        status_map={422: 500}, legacy_body=lambda response: response.status_code,
        v1_body=lambda response: 500, state_probe=state)
    assert old.data == InternalServerError().get_response().data
    assert new.json["error"]["code"] == "unprocessable"


@pytest.mark.parametrize("period_end", ["2026-01-31", "2026-01-30"])
def test_issue_reads_back_tenant_six_january_invoice(client, period_end):
    tenant = "00000000-0000-0000-0000-000000000006"
    period = {"period_start": "2026-01-01", "period_end": period_end}
    response = client.post(f"{BASE}/tenants/{tenant}/invoices", json=period)
    assert response.status_code == 201
    issued = select(
        "SELECT i.id FROM billing.invoices i "
        "JOIN billing.rating_periods p ON p.id = i.period_id "
        "WHERE i.tenant_id = %s AND p.tenant_id = %s "
        "AND p.period_start = %s AND p.period_end = %s",
        (tenant, tenant, period["period_start"], period_end),
    )
    assert len(issued) == 1
    assert response.json["data"] == {**issued[0], "tenant_id": tenant, **period, "status": "issued"}
    assert response.headers["Location"] == f"{BASE}/invoices/{issued[0]['id']}/lines"


def test_unknown_tenant_preview(client):
    old = client.get(f"/api/invoices/{UNKNOWN}/preview", query_string=PERIOD)
    assert old.status_code == 200
    assert len(old.json) == 5
    assert old.json[0]["description"] is None
    assert old.json[0]["amount"] is None
    response = client.get(f"{BASE}/tenants/{UNKNOWN}/invoice-preview", query_string=PERIOD)
    assert response.status_code == 404
    assert response.content_type == "application/json"
    assert response.json == {"error": {"code": "not_found", "message": "Not Found"}}
