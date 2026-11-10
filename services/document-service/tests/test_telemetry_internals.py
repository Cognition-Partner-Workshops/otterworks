"""Process gauges, handler labelling and OTLP tracing setup."""

import io
import sys
from types import SimpleNamespace

import pytest
from fastapi import FastAPI

from app import telemetry
from app.config import settings
from tests.conftest import engine as test_engine


def _fake_open(files: dict[str, str]):
    def fake_open(path: str, *_args, **_kwargs):
        if path not in files:
            raise FileNotFoundError(path)
        return io.StringIO(files[path])

    return fake_open


def test_read_rss_bytes_uses_statm_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        telemetry, "open", _fake_open({"/proc/self/statm": "100 25 3"}), raising=False
    )
    assert telemetry._read_rss_bytes() == 25 * 4096


@pytest.mark.parametrize("files", [{}, {"/proc/self/statm": "garbage"}, {"/proc/self/statm": "1"}])
def test_read_rss_bytes_is_zero_when_unreadable(
    monkeypatch: pytest.MonkeyPatch, files: dict[str, str]
) -> None:
    monkeypatch.setattr(telemetry, "open", _fake_open(files), raising=False)
    assert telemetry._read_rss_bytes() == 0


@pytest.mark.parametrize(
    ("files", "expected"),
    [
        ({"/sys/fs/cgroup/memory.max": "536870912\n"}, 536870912),
        ({"/sys/fs/cgroup/memory.max": "max\n"}, 0),
        ({"/sys/fs/cgroup/memory/memory.limit_in_bytes": "268435456"}, 268435456),
        ({"/sys/fs/cgroup/memory/memory.limit_in_bytes": str(1 << 62)}, 0),
        ({}, 0),
    ],
)
def test_read_memory_limit_bytes(
    monkeypatch: pytest.MonkeyPatch, files: dict[str, str], expected: int
) -> None:
    monkeypatch.setattr(telemetry, "open", _fake_open(files), raising=False)
    assert telemetry._read_memory_limit_bytes() == expected


def test_handler_label_prefers_route_template() -> None:
    request = SimpleNamespace(
        scope={"route": SimpleNamespace(path="/api/v1/documents/{document_id}")},
        url=SimpleNamespace(path="/api/v1/documents/123"),
    )
    assert telemetry._handler_label(request) == "/api/v1/documents/{document_id}"


def test_handler_label_falls_back_to_raw_path() -> None:
    request = SimpleNamespace(scope={}, url=SimpleNamespace(path="/no/such/route"))
    assert telemetry._handler_label(request) == "/no/such/route"


def test_setup_tracing_is_a_no_op_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "otel_enabled", False)
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    def unexpected(*_args, **_kwargs):
        raise AssertionError("tracing must stay off")

    monkeypatch.setattr(FastAPIInstrumentor, "instrument_app", unexpected)
    telemetry.setup_tracing(FastAPI(), test_engine)


@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        ("http://collector:4318/", "http://collector:4318/v1/traces"),
        ("http://collector:4318/v1/traces", "http://collector:4318/v1/traces"),
    ],
)
def test_setup_tracing_wires_otlp_exporter(
    monkeypatch: pytest.MonkeyPatch, configured: str, expected: str
) -> None:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http import trace_exporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

    endpoints: list[str] = []
    providers: list[object] = []
    instrumented: dict[str, object] = {}
    real_exporter = trace_exporter.OTLPSpanExporter

    def capture_exporter(endpoint: str):
        endpoints.append(endpoint)
        return real_exporter(endpoint=endpoint)

    def capture_app(app, **kwargs):
        instrumented["app"] = (app, kwargs)

    def capture_sql(self, **kwargs):
        instrumented["sql"] = kwargs

    monkeypatch.setattr(settings, "otel_enabled", True)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.setattr(settings, "otel_exporter_otlp_endpoint", configured)
    monkeypatch.setattr(trace_exporter, "OTLPSpanExporter", capture_exporter)
    monkeypatch.setattr(trace, "set_tracer_provider", providers.append)
    monkeypatch.setattr(FastAPIInstrumentor, "instrument_app", staticmethod(capture_app))
    monkeypatch.setattr(SQLAlchemyInstrumentor, "instrument", capture_sql)
    app = FastAPI()

    telemetry.setup_tracing(app, test_engine)

    assert endpoints == [expected]
    (provider,) = providers
    try:
        assert instrumented["app"][0] is app
        assert instrumented["app"][1]["tracer_provider"] is provider
        assert instrumented["sql"]["engine"] is test_engine.sync_engine
        assert instrumented["sql"]["tracer_provider"] is provider
    finally:
        provider.shutdown()


def test_setup_tracing_env_endpoint_overrides_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http import trace_exporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

    endpoints: list[str] = []
    providers: list[object] = []
    real_exporter = trace_exporter.OTLPSpanExporter

    def capture_exporter(endpoint: str):
        endpoints.append(endpoint)
        return real_exporter(endpoint=endpoint)

    monkeypatch.setattr(settings, "otel_enabled", True)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://env-collector:4318")
    monkeypatch.setattr(trace_exporter, "OTLPSpanExporter", capture_exporter)
    monkeypatch.setattr(trace, "set_tracer_provider", providers.append)
    monkeypatch.setattr(FastAPIInstrumentor, "instrument_app", staticmethod(lambda app, **kw: None))
    monkeypatch.setattr(SQLAlchemyInstrumentor, "instrument", lambda self, **kw: None)

    telemetry.setup_tracing(FastAPI(), test_engine)

    assert endpoints == ["http://env-collector:4318/v1/traces"]
    for provider in providers:
        provider.shutdown()


def test_setup_tracing_failure_does_not_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "otel_enabled", True)
    monkeypatch.setitem(sys.modules, "opentelemetry.exporter.otlp.proto.http.trace_exporter", None)
    telemetry.setup_tracing(FastAPI(), test_engine)
