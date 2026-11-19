import pytest
from werkzeug.exceptions import BadRequest, InternalServerError

from app import app, select

LEGACY_RENAMES = {"id": "invoice_id"}  # adapter keeps the old name
BASE = "/api/v1/billing"
OPERATIONS = [
    ("overdue", "overdue-invoices", "GET"),
    ("schedule", "dunning-schedules", "POST"),
    ("suspend", "suspensions", "POST"),
]


def state():
    return {table: select(f"SELECT * FROM billing.{table} ORDER BY id")
            for table in ("dunning_attempts", "tenants", "subscriptions", "notifications")}


def assert_headers(response, resource):
    assert response.headers["Deprecation"] == "true"
    assert response.headers["Link"] == f'<{BASE}/{resource}>; rel="successor-version"'


@pytest.mark.parametrize("action,resource,method", OPERATIONS)
@pytest.mark.parametrize("as_of", ["2026-02-28", "2026-03-01", "2020-01-01"])
def test_parity(compare_requests, action, resource, method, as_of):
    old = {"path": f"/api/dunning/{action}", "method": method}
    new = {"path": f"{BASE}/{resource}", "method": method}
    if method == "GET":
        old["query_string"] = new["query_string"] = {"as_of": as_of}
        options = {"unwrap": True, "renames": LEGACY_RENAMES}
    else:
        old["data"] = new["json"] = {"as_of": as_of}
        options = {"status_map": {201: 200}, "state_probe": state,
                   "v1_body": lambda response: {"status": response.json["data"]["status"]}}
    legacy, response = compare_requests(old, new, **options)
    assert_headers(legacy, resource)
    if method == "POST":
        assert response.json["data"]["as_of"] == as_of


@pytest.mark.parametrize("action,resource,method", OPERATIONS)
@pytest.mark.parametrize("value", [None, "bad", "2026-02-30"])
def test_errors(client, action, resource, method, value):
    values = {} if value is None else {"as_of": value}
    kwargs = {"query_string": values} if method == "GET" else {"data": values}
    legacy = client.open(f"/api/dunning/{action}", method=method, **kwargs)
    if method == "GET" and value is None:
        explicit = client.get("/api/dunning/overdue?as_of=2026-02-28")
        assert legacy.data == explicit.data
        assert legacy.status_code == 200
    else:
        status = 400 if value is None else 500
        error = BadRequest() if status == 400 else InternalServerError()
        assert legacy.status_code == status
        assert legacy.data == error.get_response().data
    assert_headers(legacy, resource)
    kwargs = {"query_string": values} if method == "GET" else {"json": values}
    response = client.open(f"{BASE}/{resource}", method=method, **kwargs)
    assert response.status_code == 400
    assert response.content_type == "application/json"
    assert response.json["error"]["code"] == "invalid_request"
    assert response.json["error"]["details"][0]["field"] == "as_of"


@pytest.mark.parametrize("resource", ["dunning-schedules", "suspensions"])
@pytest.mark.parametrize("kwargs", [
    {"json": []}, {"json": {"as_of": None}}, {"json": {"as_of": 123}},
    {"data": "{", "content_type": "application/json"}, {"data": {"as_of": "2026-02-28"}},
])
def test_required_json(client, resource, kwargs):
    response = client.post(f"{BASE}/{resource}", **kwargs)
    assert response.status_code == 400
    assert response.json["error"]["code"] == "invalid_request"


@pytest.mark.parametrize("query", ["limit=0", "limit=201", "limit=x", "cursor=bad"])
def test_invalid_pagination(client, query):
    response = client.get(f"{BASE}/overdue-invoices?as_of=2026-02-28&{query}")
    assert response.status_code == 400
    assert response.json["error"]["code"] == "invalid_request"


def test_pagination_and_empty(client):
    response = client.get(f"{BASE}/overdue-invoices?as_of=2026-02-28&limit=1")
    assert response.status_code == 200
    assert len(response.json["data"]) == 1
    assert response.json["pagination"]["limit"] == 1
    cursor = response.json["pagination"]["next_cursor"]
    if cursor is not None:
        following = client.get(f"{BASE}/overdue-invoices", query_string={
            "as_of": "2026-02-28", "limit": 1, "cursor": cursor})
        assert following.status_code == 200
        assert following.json["data"] != response.json["data"]
    empty = client.get(f"{BASE}/overdue-invoices?as_of=2020-01-01")
    assert empty.json == {"data": [], "pagination": {"limit": 50, "next_cursor": None}}


@pytest.mark.parametrize("action,resource,method", OPERATIONS)
def test_internal_errors(client, monkeypatch, action, resource, method):
    import app as legacy_app

    def fail(*args, **kwargs):
        raise RuntimeError("private SQL")

    monkeypatch.setattr(legacy_app, "select" if method == "GET" else "execute", fail)
    values = {"as_of": "2026-02-28"}
    kwargs = {"query_string": values} if method == "GET" else {"data": values}
    old = client.open(f"/api/dunning/{action}", method=method, **kwargs)
    assert old.status_code == 500
    assert old.data == InternalServerError().get_response().data
    assert_headers(old, resource)
    kwargs = {"query_string": values} if method == "GET" else {"json": values}
    new = client.open(f"{BASE}/{resource}", method=method, **kwargs)
    assert new.status_code == 500
    assert new.json == {"error": {"code": "internal", "message": "Internal server error"}}


@pytest.mark.parametrize("action,resource", [("schedule", "dunning-schedules"), ("suspend", "suspensions")])
def test_repeat_mutations(reset_db, action, resource):
    states = []
    for path, kwargs in [
        (f"/api/dunning/{action}", {"data": {"as_of": "2026-02-28"}}),
        (f"{BASE}/{resource}", {"json": {"as_of": "2026-02-28"}}),
    ]:
        reset_db()
        client = app.test_client()
        for _ in range(2):
            assert client.post(path, **kwargs).status_code in (200, 201)
        states.append(state())
    assert states[0] == states[1]
