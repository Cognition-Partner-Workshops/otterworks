import pytest
from flask import Flask, jsonify
from psycopg.errors import CheckViolation, ForeignKeyViolation, UniqueViolation
from werkzeug.exceptions import BadRequest

from v1 import init_app
from v1.pagination import paginate
from v1.validation import date_value, json_body, required, uuid_value
from app import select


def test_module_auto_registration_and_adapter_override(monkeypatch):
    from v1 import plans

    def register(app, blueprint):
        @blueprint.get("/extension-test")
        def extension():
            return jsonify(data={"implemented": True})

        app.view_functions["legacy_test"] = lambda: "adapter"

    monkeypatch.setattr(plans, "register", register)
    for _ in range(2):
        app = Flask(__name__)
        app.add_url_rule("/legacy-test", "legacy_test", lambda: "original")
        init_app(app)
        client = app.test_client()
        assert client.get("/api/v1/billing/extension-test").json == {"data": {"implemented": True}}
        assert client.get("/legacy-test").text == "adapter"


def test_health(compare_requests):
    old, _ = compare_requests({"path": "/health"}, {"path": "/health"})
    assert old.status_code == 200
    assert old.json == {"status": "UP", "service": "legacy-billing"}


def test_comparison_mapping_and_mismatch(compare_requests):
    def envelope(response):
        return {"data": [{("id" if key == "plan_id" else key): value
                          for key, value in row.items()} for row in response.json]}
    compare_requests({"path": "/plans"}, {"path": "/plans"}, unwrap=True,
                     renames={"id": "plan_id"}, status_map={200: 200}, v1_body=envelope)
    with pytest.raises(AssertionError):
        compare_requests({"path": "/plans"}, {"path": "/health"})


def test_mutation_state_comparison(compare_requests):
    request = {"path": "/api/rating/finalize", "method": "POST", "json": {
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "period_start": "2026-02-01", "period_end": "2026-02-28"}}
    compare_requests(request, request, state_probe=lambda: select(
        "SELECT * FROM billing.rating_results ORDER BY id"))


def test_client_resets_before_each_request(client):
    client.post("/plans/00000000-0000-0000-0000-000000000001/change", data={
        "plan_id": "10000000-0000-0000-0000-000000000003", "effective_on": "2026-03-01"})
    response = client.get("/plans/00000000-0000-0000-0000-000000000001/entitlement?on=2026-03-01")
    assert response.json[0]["plan_code"] == "STARTER"


def test_unknown_paths(client):
    response = client.get("/api/v1/billing/no-such-route")
    assert response.status_code == 404
    assert response.content_type == "application/json"
    assert response.json == {"error": {"code": "not_found", "message": "Not Found"}}
    response = client.get("/missing-legacy")
    assert response.status_code == 404
    assert response.content_type.startswith("text/html")


@pytest.fixture
def helper_app():
    app = Flask(__name__)

    @app.route("/api/v1/billing/helper", methods=["GET", "POST"])
    def helper():
        from flask import request
        if request.method == "POST":
            body = json_body()
            return jsonify(id=uuid_value(required(body, "id"), "id"),
                           on=str(date_value(required(body, "on"), "on")))
        return jsonify(paginate([1, 2, 3]))

    @app.get("/api/v1/billing/fail/<kind>")
    def fail(kind):
        raise {"unique": UniqueViolation, "fk": ForeignKeyViolation,
               "check": CheckViolation, "bad": BadRequest, "internal": RuntimeError}[kind]("private SQL")

    init_app(app)
    return app


def test_pagination(helper_app):
    client = helper_app.test_client()
    first = client.get("/api/v1/billing/helper?limit=2").json
    assert first["data"] == [1, 2]
    last = client.get("/api/v1/billing/helper", query_string={"limit": 2, "cursor": first["pagination"]["next_cursor"]}).json
    assert last == {"data": [3], "pagination": {"limit": 2, "next_cursor": None}}
    with helper_app.test_request_context("/api/v1/billing/empty"):
        assert paginate([]) == {"data": [], "pagination": {"limit": 50, "next_cursor": None}}


@pytest.mark.parametrize("query", ["limit=0", "limit=201", "limit=x", "cursor=bad", "cursor=", "limit=-1"])
def test_bad_pagination(helper_app, query):
    response = helper_app.test_client().get("/api/v1/billing/helper?" + query)
    assert response.status_code == 400
    assert response.json["error"]["code"] == "invalid_request"


@pytest.mark.parametrize("payload", [{}, [], {"id": "bad"}, {"id": "00000000-0000-0000-0000-000000000001", "on": "2026-02-30"}])
def test_bad_body(helper_app, payload):
    response = helper_app.test_client().post("/api/v1/billing/helper", json=payload)
    assert response.status_code == 400
    assert response.json["error"]["details"]


def test_valid_body_and_malformed_json(helper_app):
    client = helper_app.test_client()
    payload = {"id": "00000000-0000-0000-0000-000000000001", "on": "2026-02-28"}
    assert client.post("/api/v1/billing/helper", json=payload).json == payload
    for data, content_type in [("{", "application/json"), ("", "text/plain")]:
        assert client.post("/api/v1/billing/helper", data=data, content_type=content_type).status_code == 400
    assert client.delete("/api/v1/billing/helper").json["error"]["code"] == "method_not_allowed"


@pytest.mark.parametrize("kind,status,code", [("unique",409,"conflict"), ("fk",422,"unprocessable"), ("check",422,"unprocessable"), ("bad",400,"invalid_request"), ("internal",500,"internal")])
def test_error_translation(helper_app, kind, status, code):
    response = helper_app.test_client().get("/api/v1/billing/fail/" + kind)
    assert response.status_code == status
    assert response.json["error"]["code"] == code
    assert "private SQL" not in response.text
