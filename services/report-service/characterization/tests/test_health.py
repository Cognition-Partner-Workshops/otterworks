"""HealthController, actuator and the cross-cutting HTTP behaviour (security headers, docs)."""
import pytest

from conftest import body_of, error_shape, headers_of, http

INSTANCES = ["off", "db2", "pg"]


@pytest.mark.parametrize("instance", INSTANCES)
def test_health(instance, snapshot):
    resp = http("GET", instance, "/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "healthy", "service": "report-service", "version": "0.1.0"}
    snapshot("health__%s" % instance, {"status": resp.status_code, "headers": headers_of(resp),
                                       "body": resp.json()})


@pytest.mark.parametrize("instance,store,namespace,status", [
    ("off", "off", "", "disabled"),
    ("db2", "db2", "char-before", "healthy"),
    ("pg", "postgresql", "char-after", "healthy"),
])
def test_health_archive(instance, store, namespace, status, snapshot):
    resp = http("GET", instance, "/health/archive")
    assert resp.status_code == 200
    body = resp.json()
    assert body["store"] == store
    assert body["status"] == status
    assert (body["namespace"] or "") == namespace
    snapshot("health_archive__%s" % instance, {"status": resp.status_code, "body": body})


@pytest.mark.parametrize("path", ["/actuator/health", "/actuator/info"])
def test_actuator(path, snapshot):
    resp = http("GET", "off", path)
    snapshot("actuator%s" % path.replace("/actuator", "").replace("/", "_"),
             {"status": resp.status_code, "content_type": resp.headers.get("Content-Type"), "body": body_of(resp)})


def test_actuator_prometheus(snapshot):
    resp = http("GET", "off", "/actuator/prometheus")
    families = sorted({line.split()[2] for line in resp.text.splitlines() if line.startswith("# TYPE ")
                       and line.split()[2].startswith(("http_server_requests", "jvm_memory_used", "process_uptime"))})
    snapshot("actuator_prometheus", {"status": resp.status_code,
                                     "content_type": resp.headers.get("Content-Type"),
                                     "selected_families": families})


def test_unknown_path_and_method(snapshot):
    snapshot("unknown_path", error_shape(http("GET", "off", "/api/v1/nope")))
    snapshot("health_post", error_shape(http("POST", "off", "/health")))


def test_swagger_v2_api_docs(snapshot):
    resp = http("GET", "off", "/v2/api-docs")
    out = {"status": resp.status_code, "content_type": resp.headers.get("Content-Type")}
    if resp.status_code == 200:
        doc = resp.json()
        out["swagger"] = doc.get("swagger")
        out["paths"] = {p: sorted(ops) for p, ops in sorted(doc.get("paths", {}).items())}
    snapshot("swagger_v2_api_docs", out)
