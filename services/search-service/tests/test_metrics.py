"""Request metrics middleware: Flask rule labels, skipped paths, auth 401s, routing errors, 500s."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from prometheus_client import REGISTRY
from starlette.testclient import TestClient

from app.middleware.metrics import flask_rule
from tests.test_flask_compat import PREFIX, TOKEN, make_client

AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture()
def client() -> Iterator[TestClient]:
    yield from make_client()


def count(method: str, endpoint: str, status: str) -> float:
    labels = {"method": method, "endpoint": endpoint, "status": status}
    return REGISTRY.get_sample_value("search_service_requests_total", labels) or 0.0


def observed(method: str, endpoint: str) -> float:
    labels = {"method": method, "endpoint": endpoint}
    return REGISTRY.get_sample_value("search_service_request_duration_seconds_count", labels) or 0.0


@pytest.mark.parametrize(
    ("path", "rule"),
    [
        (f"{PREFIX}/", f"{PREFIX}/"),
        (f"{PREFIX}/index/{{doc_type}}/{{doc_id}}", f"{PREFIX}/index/<doc_type>/<doc_id>"),
        ("/x/{n:int}/{p:path}/{u:uuid}/{f:float}/{s:str}", "/x/<int:n>/<path:p>/<uuid:u>/<float:f>/<s>"),
    ],
)
def test_flask_rule(path: str, rule: str) -> None:
    assert flask_rule(path) == rule


@pytest.mark.parametrize(
    ("method", "path", "headers", "endpoint", "status"),
    [
        ("GET", PREFIX, AUTH, f"{PREFIX}/", "200"),
        ("GET", f"{PREFIX}/", AUTH, f"{PREFIX}/", "200"),
        ("DELETE", f"{PREFIX}/index/document/d1", AUTH, f"{PREFIX}/index/<doc_type>/<doc_id>", "200"),
        ("GET", f"{PREFIX}/suggest", {}, f"{PREFIX}/suggest", "401"),
        ("OPTIONS", f"{PREFIX}/advanced", AUTH, f"{PREFIX}/advanced", "200"),
        ("GET", "/nope", {}, "unknown", "401"),
        ("GET", "/nope", AUTH, "unknown", "404"),
        ("GET", f"{PREFIX}/suggest/", AUTH, "unknown", "404"),
        ("GET", f"{PREFIX}/advanced", AUTH, "unknown", "405"),
        ("GET", f"{PREFIX}/_test/abort/404", AUTH, f"{PREFIX}/_test/abort/<code>", "404"),
        ("GET", f"{PREFIX}/_test/boom", AUTH, f"{PREFIX}/_test/boom", "500"),
        ("GET", "/health/ready", {}, "/health/ready", "200"),
    ],
)
def test_request_counted(
    client: TestClient, method: str, path: str, headers: dict[str, str], endpoint: str, status: str
) -> None:
    before, before_obs = count(method, endpoint, status), observed(method, endpoint)
    r = client.request(method, path, headers=headers)
    assert r.status_code == int(status)
    assert count(method, endpoint, status) == before + 1
    assert observed(method, endpoint) == before_obs + 1


@pytest.mark.parametrize("path", ["/health", "/metrics"])
def test_health_and_metrics_not_counted(client: TestClient, path: str) -> None:
    before = observed("GET", path), observed("GET", "unknown")
    assert client.get(path).status_code == 200
    assert (observed("GET", path), observed("GET", "unknown")) == before


def test_trailing_slash_health_is_counted(client: TestClient) -> None:
    before = count("GET", "unknown", "404")
    assert client.get("/health/").status_code == 404
    assert count("GET", "unknown", "404") == before + 1
