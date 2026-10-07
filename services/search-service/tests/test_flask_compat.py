"""Auth middleware, error handlers, routing and Flask helpers vs. the Flask transcript.

A stub router with the Flask blueprints' rule table (paths, methods,
``strict_slashes``) replaces the real search/index routes, so these cases need
no MeiliSearch; the real routes are covered by the parity harness.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, ClassVar
from unittest.mock import patch

import pytest
from fastapi import APIRouter, HTTPException, Request
from starlette.testclient import TestClient

from app.config import AppConfig, AuthConfig
from app.flask_compat import get_json, header, is_json_mimetype, jsonify, query_arg, werkzeug_error_body
from app.main import create_app
from app.routing import strict_slashes
from tests.parity.harness import normalise_body, normalise_headers

TRANSCRIPT = json.loads((Path(__file__).parent / "parity" / "flask_transcript.json").read_text())
CASES = {e["name"]: e for e in TRANSCRIPT if "request" in e}
TOKEN = "parity-service-token"
PREFIX = "/api/v1/search"

stub = APIRouter(prefix=PREFIX)


@stub.get("/")
@strict_slashes(False)
async def search_documents() -> Any:
    return jsonify({"stub": "search"})


@stub.get("/suggest")
async def suggest() -> Any:
    return jsonify({"stub": "suggest"})


@stub.post("/advanced")
async def advanced_search() -> Any:
    return jsonify({"stub": "advanced"})


@stub.get("/analytics")
async def search_analytics() -> Any:
    return jsonify({"stub": "analytics"})


@stub.post("/index/document")
async def index_document(request: Request) -> Any:
    return jsonify({"parsed": await get_json(request)})


@stub.post("/index/file")
async def index_file(request: Request) -> Any:
    return jsonify({"parsed": await get_json(request)})


@stub.delete("/index/{doc_type}/{doc_id}")
async def remove_from_index(doc_type: str, doc_id: str) -> Any:
    return jsonify({"stub": "delete"})


@stub.post("/reindex")
async def reindex() -> Any:
    return jsonify({"stub": "reindex"})


@stub.get("/_test/page")
async def typed_page(page: int = 1, size: int = 20) -> Any:
    return jsonify({"page": page, "size": size})


@stub.get("/_test/typed")
async def typed_other(limit: int) -> Any:
    return jsonify({"limit": limit})


@stub.get("/_test/abort/{code}")
async def abort(code: int) -> Any:
    raise HTTPException(code)


@stub.get("/_test/error")
async def json_error() -> Any:
    raise HTTPException(400, "Missing required field: id")


@stub.get("/_test/boom")
async def boom() -> Any:
    raise RuntimeError("boom")


def make_client(**auth: Any) -> Iterator[TestClient]:
    config = AppConfig(auth=AuthConfig(**{"service_token": TOKEN, "require_auth": True, **auth}))
    with patch("app.services.meilisearch_client.meilisearch.Client"):
        app = create_app(config)
        app.router.routes[:] = [r for r in app.router.routes if not getattr(r, "path", "").startswith(PREFIX)]
        app.include_router(stub)
        with TestClient(app, base_url="http://localhost", raise_server_exceptions=False) as client:
            yield client


@pytest.fixture()
def client() -> Iterator[TestClient]:
    yield from make_client()


def observe(client: TestClient, req: dict[str, Any]) -> dict[str, Any]:
    body = req.get("body")
    r = client.request(
        req["method"],
        req["path"],
        headers=req["headers"],
        content=body.encode() if body is not None else None,
        follow_redirects=False,
    )
    return {
        "status": r.status_code,
        "headers": normalise_headers(r.headers.multi_items(), "http://localhost"),
        "body": normalise_body(req["path"], r.status_code, r.headers.get("content-type", ""), r.content),
    }


def transcript_request(name: str) -> dict[str, Any]:
    case = CASES[name]
    return case["request"]


# Transcript entries whose full response (status, headers, body) needs no real router or MeiliSearch.
def _routing_only(case: dict[str, Any]) -> bool:
    status, body = case["response"]["status"], case["response"]["body"] or {}
    if status == 401 or (case["request"]["method"] == "OPTIONS" and status == 200):
        return True
    # Werkzeug HTML pages from routing or get_json(); 400/415 only on the routes that call get_json().
    if "text" not in body or status == 500:
        return False
    return status in (404, 405) or case["request"]["path"].startswith(f"{PREFIX}/index/")


ROUTING_ONLY = [name for name, case in CASES.items() if _routing_only(case)]
# Entries the real routers answer with 200 JSON: only status and headers are comparable here.
ROUTED_OK = [
    "search.no_slash.user1",
    "search.slash.user1",
    "auth.user_id",
    "auth.bearer_valid",
    "auth.bearer_lowercase_scheme",
    "auth.bearer_invalid_with_user_id",
    "cors.simple.allowed",
    "cors.simple.disallowed",
]


def test_routing_only_cases_selected() -> None:
    assert len(ROUTING_ONLY) >= 40
    assert {"auth.none.unknown_path", "auth.none.wrong_method", "suggest.trailing_slash"} <= set(ROUTING_ONLY)


@pytest.mark.parametrize("name", ROUTING_ONLY)
def test_transcript_error_and_options_cases(client: TestClient, name: str) -> None:
    case = CASES[name]
    assert observe(client, case["request"]) == case["response"]


@pytest.mark.parametrize("name", ROUTED_OK)
def test_transcript_authenticated_cases_reach_route(client: TestClient, name: str) -> None:
    case = CASES[name]
    got = observe(client, case["request"])
    assert (got["status"], got["headers"]) == (case["response"]["status"], case["response"]["headers"])


@pytest.mark.parametrize("path", [f"{PREFIX}", f"{PREFIX}/", f"{PREFIX}?q=otter", f"{PREFIX}/?q=otter"])
def test_search_root_served_with_and_without_slash(client: TestClient, path: str) -> None:
    r = client.get(path, headers={"X-User-ID": "u"}, follow_redirects=False)
    assert r.status_code == 200
    assert r.json() == {"stub": "search"}


@pytest.mark.parametrize("path", ["/health/", "/metrics/", f"{PREFIX}/suggest/", f"{PREFIX}/advanced/", f"{PREFIX}//"])
def test_other_slash_variants_are_404_not_redirects(client: TestClient, path: str) -> None:
    r = client.request(
        "POST" if "advanced" in path else "GET", path, headers={"X-User-ID": "u"}, follow_redirects=False
    )
    assert r.status_code == 404
    assert "location" not in r.headers
    assert r.text == werkzeug_error_body(404)


def test_head_and_options_follow_werkzeug(client: TestClient) -> None:
    h = {"X-User-ID": "u"}
    assert client.head(f"{PREFIX}/suggest", headers=h).status_code == 200
    r = client.options(f"{PREFIX}/index/document/x", headers=h)
    assert (r.status_code, r.headers["allow"], r.content) == (200, "DELETE, OPTIONS", b"")
    r = client.put(f"{PREFIX}/index/document/x", headers=h)
    assert (r.status_code, r.headers["allow"]) == (405, "DELETE, OPTIONS")


class TestAuthMiddleware:
    @pytest.mark.parametrize(
        "headers",
        [
            {},
            {"X-User-ID": "   "},
            {"Authorization": "Bearer wrong"},
            {"Authorization": "Basic cGFyaXR5OnRva2Vu"},
            {"Authorization": f"Token {TOKEN}"},
            {"Authorization": "Bearer "},
        ],
    )
    @pytest.mark.parametrize(
        ("method", "path"),
        [("GET", f"{PREFIX}/"), ("GET", "/nope"), ("DELETE", f"{PREFIX}/"), ("GET", "/"), ("PATCH", "/api")],
    )
    def test_rejected_before_routing(self, client: TestClient, headers: dict[str, str], method: str, path: str) -> None:
        r = client.request(method, path, headers=headers)
        assert (r.status_code, r.content, r.headers["content-type"]) == (
            401,
            b'{"error":"unauthorized"}\n',
            "application/json",
        )

    @pytest.mark.parametrize(
        "headers",
        [
            {"X-User-ID": "u1"},
            {"X-User-ID": "  u1  "},
            {"Authorization": f"Bearer {TOKEN}"},
            {"Authorization": f"bearer {TOKEN}"},
            {"Authorization": f"BEARER   {TOKEN}  "},
            {"Authorization": "Bearer wrong", "X-User-ID": "u1"},
        ],
    )
    def test_accepted(self, client: TestClient, headers: dict[str, str]) -> None:
        assert client.get(f"{PREFIX}/", headers=headers).status_code == 200
        assert client.get("/nope", headers=headers).status_code == 404

    @pytest.mark.parametrize("path", ["/health", "/metrics", "/healthcheck", "/metrics/extra", "/health/ready/x"])
    def test_public_prefixes(self, client: TestClient, path: str) -> None:
        assert client.get(path).status_code != 401

    def test_token_not_accepted_when_unconfigured(self) -> None:
        for client in make_client(service_token=""):
            assert client.get(f"{PREFIX}/", headers={"Authorization": "Bearer "}).status_code == 401
            assert client.get(f"{PREFIX}/", headers={"Authorization": f"Bearer {TOKEN}"}).status_code == 401

    def test_disabled(self) -> None:
        for client in make_client(require_auth=False):
            assert client.get(f"{PREFIX}/").status_code == 200
            assert client.get("/nope").status_code == 404

    def test_logs_auth_rejected_with_endpoint(self, client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
        client.get(f"{PREFIX}/suggest")
        client.get("/nope")
        client.put(f"{PREFIX}/suggest")
        events = [json.loads(r.getMessage()) for r in caplog.records if r.name == "app.middleware.auth"]
        rejected = [(e["endpoint"], e["path"]) for e in events if e["event"] == "auth_rejected"]
        assert rejected == [("suggest", f"{PREFIX}/suggest"), ("", "/nope"), ("", f"{PREFIX}/suggest")]


class TestErrorHandlers:
    H: ClassVar[dict[str, str]] = {"X-User-ID": "u"}

    @pytest.mark.parametrize("query", ["page=abc", "size=xyz", "page=1.5", "page=1&size=x"])
    def test_invalid_page_or_size_is_400_json(self, client: TestClient, query: str) -> None:
        r = client.get(f"{PREFIX}/_test/page?{query}", headers=self.H)
        assert (r.status_code, r.content) == (400, b'{"error":"Invalid page or size parameter"}\n')

    def test_other_validation_errors_are_400_not_422(self, client: TestClient) -> None:
        r = client.get(f"{PREFIX}/_test/typed", headers=self.H)
        assert (r.status_code, r.json()) == (400, {"error": "Invalid request"})

    @pytest.mark.parametrize("code", [400, 403, 404, 405, 415, 503])
    def test_bare_http_exception_is_werkzeug_html(self, client: TestClient, code: int) -> None:
        r = client.get(f"{PREFIX}/_test/abort/{code}", headers=self.H)
        assert (r.status_code, r.text, r.headers["content-type"]) == (
            code,
            werkzeug_error_body(code),
            "text/html; charset=utf-8",
        )

    def test_http_exception_with_detail_is_error_json(self, client: TestClient) -> None:
        r = client.get(f"{PREFIX}/_test/error", headers=self.H)
        assert (r.status_code, r.content) == (400, b'{"error":"Missing required field: id"}\n')

    def test_unhandled_exception_is_werkzeug_500_with_cors(self, client: TestClient) -> None:
        expected = CASES["chaos.suggest.normal_500"]["response"]
        r = client.get(f"{PREFIX}/_test/boom", headers=self.H)
        got = observe(client, {"method": "GET", "path": f"{PREFIX}/_test/boom", "headers": self.H})
        assert r.status_code == 500
        assert got == expected


class TestFlaskHelpers:
    @pytest.mark.parametrize(
        ("content_type", "body", "expected"),
        [
            ("application/json", b'{"a": 1}', {"a": 1}),
            ("application/json; charset=utf-8", b"[1, 2]", [1, 2]),
            ("Application/JSON", b"null", None),
            ("application/vnd.api+json", b'"x"', "x"),
        ],
    )
    def test_get_json_parses(self, client: TestClient, content_type: str, body: bytes, expected: Any) -> None:
        r = client.post(
            f"{PREFIX}/index/document", headers={"X-User-ID": "u", "Content-Type": content_type}, content=body
        )
        assert r.json() == {"parsed": expected}

    @pytest.mark.parametrize(
        ("content_type", "body", "status"),
        [
            (None, b"", 415),
            (None, b'{"a": 1}', 415),
            ("text/plain", b'{"a": 1}', 415),
            ("application/jsonx", b"{}", 415),
            ("application/json", b"", 400),
            ("application/json", b"{bad", 400),
            ("application/json", b"\xff", 400),
        ],
    )
    def test_get_json_errors_are_werkzeug_html(
        self, client: TestClient, content_type: str | None, body: bytes, status: int
    ) -> None:
        headers = {"X-User-ID": "u"}
        if content_type:
            headers["Content-Type"] = content_type
        r = client.post(f"{PREFIX}/index/file", headers=headers, content=body)
        expected = CASES["index.document.no_content_type" if status == 415 else "index.document.invalid_json"]
        assert (r.status_code, r.headers["content-type"]) == (status, "text/html; charset=utf-8")
        assert r.text == expected["response"]["body"]["text"]

    def test_jsonify_matches_flask_bytes(self) -> None:
        r = jsonify({"b": 1, "a": "ö", "c": [None, True]}, 201)
        assert (r.status_code, r.body) == (201, b'{"a":"\\u00f6","b":1,"c":[null,true]}\n')

    def test_query_arg_first_value_wins(self, client: TestClient) -> None:
        from starlette.requests import Request as StarletteRequest

        req = StarletteRequest({"type": "http", "query_string": b"q=a&q=b", "headers": []})
        assert query_arg(req, "q") == "a"
        assert query_arg(req, "missing", "d") == "d"

    def test_header_joins_repeats_like_wsgi(self) -> None:
        from starlette.datastructures import Headers

        h = Headers(
            raw=[
                (b"x-user-id", b"a"),
                (b"x-user-id", b"b"),
                (b"content-type", b"text/plain"),
                (b"content-type", b"application/json"),
            ]
        )
        assert header(h, "X-User-ID") == "a,b"
        assert header(h, "missing") == ""
        assert is_json_mimetype(h)
