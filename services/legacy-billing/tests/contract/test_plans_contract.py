import pytest
from werkzeug.exceptions import default_exceptions

from app import app, execute, select

TENANT = "00000000-0000-0000-0000-000000000001"
PLAN = "10000000-0000-0000-0000-000000000002"
UNKNOWN = "ffffffff-ffff-ffff-ffff-ffffffffffff"
PREFIX = "/api/v1/billing"
LEGACY_RENAMES = {"id": "plan_id", "status": "subscription_status"}  # adapter keeps the old names
LEGACY = f"/plans/{TENANT}"
V1 = f"{PREFIX}/tenants/{TENANT}"
INPUT = {"plan_id": PLAN, "effective_on": "2026-03-01"}


def state():
    return select("SELECT * FROM billing.subscriptions ORDER BY id")


def headers(response, successor):
    assert response.headers["Deprecation"] == "true"
    assert response.headers["Link"] == f'<{PREFIX}{successor}>; rel="successor-version"'


def error(response, status, code):
    assert response.status_code == status
    assert response.content_type == "application/json"
    assert response.json["error"]["code"] == code
    assert isinstance(response.json["error"]["message"], str)


def test_list(compare_requests):
    old, new = compare_requests({"path": "/plans"}, {"path": f"{PREFIX}/plans"},
                                unwrap=True, renames=LEGACY_RENAMES)
    assert len(new.json["data"]) > 1
    assert new.json["pagination"] == {"limit": 50, "next_cursor": None}
    assert isinstance(new.json["data"][0]["monthly_fee"], str)
    headers(old, "/plans")


@pytest.mark.parametrize("on", ["2026-02-28", "2026-03-01"])
def test_entitlement(compare_requests, on):
    old, new = compare_requests({"path": f"{LEGACY}/entitlement?on={on}"},
                                {"path": f"{V1}/entitlement?on={on}"},
                                renames=LEGACY_RENAMES,
                                v1_body=lambda r: [r.json["data"]])
    assert new.json["data"]["tenant_id"] == TENANT
    headers(old, f"/tenants/{TENANT}/entitlement")


def test_legacy_default(compare_requests):
    compare_requests({"path": f"{LEGACY}/entitlement"},
                     {"path": f"{V1}/entitlement?on=2026-02-28"},
                     renames=LEGACY_RENAMES, v1_body=lambda r: [r.json["data"]])


def test_change(compare_requests):
    old, new = compare_requests(
        {"path": f"{LEGACY}/change", "method": "POST", "data": INPUT},
        {"path": f"{V1}/subscriptions", "method": "POST", "json": INPUT},
        status_map={201: 302}, renames=LEGACY_RENAMES, state_probe=state,
        legacy_body=lambda r: select("SELECT * FROM billing.fn_entitlement(%s, %s)",
                                     (TENANT, INPUT["effective_on"]))[0],
        v1_body=lambda r: r.json["data"])
    assert old.headers["Location"] == f"{LEGACY}/entitlement?on=2026-03-01"
    assert new.headers["Location"] == f"{V1}/entitlement?on=2026-03-01"
    headers(old, f"/tenants/{TENANT}/subscriptions")


@pytest.mark.parametrize("legacy_request,v1_request,old_status,new_status,code", [
    ({"path": "/plans", "method": "POST"}, {"path": f"{PREFIX}/plans", "method": "POST"}, 405, 405, "method_not_allowed"),
    ({"path": f"{LEGACY}/entitlement?on=bad"}, {"path": f"{V1}/entitlement?on=bad"}, 500, 400, "invalid_request"),
    ({"path": "/plans/bad/entitlement"}, {"path": f"{PREFIX}/tenants/bad/entitlement?on=2026-02-28"}, 500, 400, "invalid_request"),
    ({"path": f"{LEGACY}/change", "method": "POST"}, {"path": f"{V1}/subscriptions", "method": "POST", "json": {}}, 400, 400, "invalid_request"),
    ({"path": f"{LEGACY}/change", "method": "POST", "data": {**INPUT, "plan_id": UNKNOWN}}, {"path": f"{V1}/subscriptions", "method": "POST", "json": {**INPUT, "plan_id": UNKNOWN}}, 500, 422, "unprocessable"),
    ({"path": f"{LEGACY}/entitlement?on=1900-01-01"}, {"path": f"{V1}/entitlement?on=1900-01-01"}, 200, 404, "not_found"),
])
def test_legacy_errors(compare_requests, legacy_request, v1_request, old_status, new_status, code):
    def legacy_body(response):
        assert response.status_code == old_status
        if old_status >= 400:
            assert response.content_type.startswith("text/html")
            assert response.data == default_exceptions[old_status]().get_body().encode()
        else:
            assert response.json == []
        return None

    def v1_body(response):
        error(response, new_status, code)
        return None

    old, _ = compare_requests(legacy_request, v1_request, status_map={new_status: old_status},
                              legacy_body=legacy_body, v1_body=v1_body, state_probe=state)
    assert old.headers["Deprecation"] == "true"
    assert 'rel="successor-version"' in old.headers["Link"]


@pytest.mark.parametrize("payload", [{}, {"plan_id": PLAN}, {"effective_on": "2026-03-01"},
                                     {**INPUT, "plan_id": "bad"}, {**INPUT, "effective_on": "2026-02-30"}, [], None])
def test_required_inputs(client, payload):
    error(client.post(f"{V1}/subscriptions", json=payload), 400, "invalid_request")


@pytest.mark.parametrize("data,content_type", [("{", "application/json"), ("", "text/plain")])
def test_invalid_body(client, data, content_type):
    error(client.post(f"{V1}/subscriptions", data=data, content_type=content_type), 400, "invalid_request")


def test_required_on_and_unknown(client):
    error(client.get(f"{V1}/entitlement"), 400, "invalid_request")
    error(client.get(f"{PREFIX}/tenants/{UNKNOWN}/entitlement?on=2026-02-28"), 404, "not_found")


@pytest.mark.parametrize("query", ["limit=0", "limit=201", "limit=x", "cursor=bad", "cursor="])
def test_invalid_pagination(client, query):
    error(client.get(f"{PREFIX}/plans?{query}"), 400, "invalid_request")


def test_pagination(client):
    expected = client.get(f"{PREFIX}/plans").json["data"]
    result, cursor = [], None
    while True:
        query = {"limit": 1}
        if cursor:
            query["cursor"] = cursor
        response = client.get(f"{PREFIX}/plans", query_string=query).json
        result.extend(response["data"])
        cursor = response["pagination"]["next_cursor"]
        if cursor is None:
            break
    assert result == expected


def test_empty_plans(reset_db):
    execute("UPDATE billing.plans SET active = false")
    client = app.test_client()
    assert client.get("/plans").json == []
    assert client.get(f"{PREFIX}/plans").json == {"data": [], "pagination": {"limit": 50, "next_cursor": None}}


def test_duplicate_change(reset_db):
    client = app.test_client()
    assert client.post(f"{V1}/subscriptions", json=INPUT).status_code == 201
    before = state()
    error(client.post(f"{V1}/subscriptions", json=INPUT), 409, "conflict")
    assert state() == before
    old = client.post(f"{LEGACY}/change", data=INPUT)
    assert old.status_code == 500
    headers(old, f"/tenants/{TENANT}/subscriptions")
    assert state() == before
