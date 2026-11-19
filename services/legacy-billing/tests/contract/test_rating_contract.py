import pytest
from werkzeug.exceptions import BadRequest, InternalServerError

from app import app, select

TENANT = "00000000-0000-0000-0000-000000000001"
UNKNOWN = "ffffffff-ffff-ffff-ffff-ffffffffffff"
PERIOD = {"period_start": "2026-02-01", "period_end": "2026-02-28"}
BASE = "/api/v1/billing/tenants"
LEGACY_RENAMES = {}  # rating fields keep their legacy names


def state():
    return {table: select(f"SELECT * FROM billing.{table} ORDER BY id")
            for table in ("rating_periods", "rating_results")}


@pytest.mark.parametrize("tenant", [TENANT, "00000000-0000-0000-0000-000000000002", UNKNOWN])
def test_preview(compare_requests, tenant):
    old, new = compare_requests(
        {"path": "/api/rating/preview", "method": "POST", "json": {"tenant_id": tenant, **PERIOD}},
        {"path": f"{BASE}/{tenant}/rating", "query_string": PERIOD},
        renames=LEGACY_RENAMES, legacy_body=lambda r: r.json[0], unwrap=True)
    assert new.status_code == 200
    assert old.headers["Deprecation"] == "true"
    assert old.headers["Link"] == f'<{BASE}/{tenant}/rating>; rel="successor-version"'


def test_finalize(compare_requests):
    old, new = compare_requests(
        {"path": "/api/rating/finalize", "method": "POST", "json": {"tenant_id": TENANT, **PERIOD}},
        {"path": f"{BASE}/{TENANT}/rating-periods", "method": "POST", "json": PERIOD},
        status_map={201: 200}, v1_body=lambda r: {"status": r.json["data"]["status"]},
        state_probe=state)
    assert new.status_code == 201
    assert new.json["data"] == {"tenant_id": TENANT, **PERIOD, "status": "finalized"}
    assert old.headers["Link"] == f'<{BASE}/{TENANT}/rating-periods>; rel="successor-version"'


@pytest.mark.parametrize("action,resource,case", [
    (action, resource, case)
    for action, resource in [("preview", "rating"), ("finalize", "rating-periods")]
    for case in ["malformed", "missing", "date", "uuid", "unknown"]
    if not (action == "preview" and case == "unknown")
])
def test_errors(client, action, resource, case):
    tenant = "bad" if case == "uuid" else UNKNOWN if case == "unknown" else TENANT
    values = {**PERIOD}
    if case == "missing":
        values.pop("period_start")
    if case == "date":
        values["period_start"] = "bad"
    legacy_kwargs = {"json": {"tenant_id": tenant, **values}}
    if case == "malformed":
        legacy_kwargs = {"data": "{", "content_type": "application/json"}
    old = client.post(f"/api/rating/{action}", **legacy_kwargs)
    expected = BadRequest() if case == "malformed" else InternalServerError()
    assert old.status_code == expected.code
    assert old.data == expected.get_body().encode()
    assert old.headers["Deprecation"] == "true"
    old_state = state()
    if action == "preview":
        new = client.get(f"{BASE}/{tenant}/{resource}", query_string={} if case == "malformed" else values)
    else:
        kwargs = {"data": "{", "content_type": "application/json"} if case == "malformed" else {"json": values}
        new = client.post(f"{BASE}/{tenant}/{resource}", **kwargs)
    assert new.status_code == (422 if case == "unknown" else 400)
    assert new.is_json
    assert new.json["error"]["code"] == ("unprocessable" if case == "unknown" else "invalid_request")
    if action == "finalize":
        assert state() == old_state


@pytest.mark.parametrize("resource,method", [("rating", "GET"), ("rating-periods", "POST")])
@pytest.mark.parametrize("field", ["period_start", "period_end"])
def test_required(client, resource, method, field):
    values = {k: v for k, v in PERIOD.items() if k != field}
    response = client.open(f"{BASE}/{TENANT}/{resource}", method=method,
                           **({"query_string": values} if method == "GET" else {"json": values}))
    assert response.status_code == 400
    assert response.json["error"]["details"][0]["field"] == field


@pytest.mark.parametrize("kwargs", [{"json": []}, {"json": None}, {"data": "x"}, {"json": {"period_start": 42, "period_end": "2026-02-28"}}])
def test_body_validation(client, kwargs):
    response = client.post(f"{BASE}/{TENANT}/rating-periods", **kwargs)
    assert response.status_code == 400
    assert response.json["error"]["code"] == "invalid_request"


def test_single_resource_has_no_pagination(client):
    response = client.get(f"{BASE}/{TENANT}/rating", query_string={**PERIOD, "limit": "bad", "cursor": "bad"})
    assert response.status_code == 200
    assert set(response.json) == {"data"}


def test_empty_result(client, monkeypatch):
    monkeypatch.setattr("v1.rating.preview", lambda *args: [])
    response = client.get(f"{BASE}/{TENANT}/rating", query_string=PERIOD)
    assert response.status_code == 404
    assert response.json["error"]["code"] == "not_found"


def test_repeat_finalize(reset_db):
    client = app.test_client()
    request = {"path": f"{BASE}/{TENANT}/rating-periods", "json": PERIOD}
    assert client.post(**request).status_code == 201
    first = state()
    assert client.post(**request).status_code == 201
    assert state() == first
