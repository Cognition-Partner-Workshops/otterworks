"""Prometheus metrics and OpenTelemetry tracing for the document service."""

from __future__ import annotations

import contextvars
import os
import time
from collections.abc import Awaitable, Callable

import structlog
from asyncpg.exceptions import QueryCanceledError
from fastapi import FastAPI, Request, Response
from prometheus_client import Counter, Gauge, Histogram
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import event
from sqlalchemy.engine import Engine, ExceptionContext
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.pool import QueuePool

from app.config import settings

logger = structlog.get_logger()

SERVICE = "document-service"

LATENCY_BUCKETS = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    0.75,
    1.0,
    1.5,
    2.0,
    2.5,
    3.0,
    4.0,
    5.0,
    7.5,
    10.0,
)

DB_QUERIES_TOTAL = Counter(
    "otterworks_db_queries_total",
    "SQL statements executed by the service.",
    ["service"],
)
DB_QUERIES_PER_REQUEST = Histogram(
    "otterworks_db_queries_per_request",
    "SQL statements executed while serving one HTTP request.",
    ["service", "handler"],
    buckets=(1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233),
)
DB_QUERY_SECONDS = Histogram(
    "otterworks_db_query_duration_seconds",
    "Wall time of individual SQL statements.",
    ["service"],
    buckets=(0.0005, 0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)
PROCESS_RSS_BYTES = Gauge(
    "otterworks_process_resident_memory_bytes",
    "Resident set size of the service process.",
    ["service"],
)
RENDER_CACHE_ENTRIES = Gauge(
    "otterworks_render_cache_entries",
    "Entries held by the in-process rendered-document cache.",
    ["service"],
)
REQUEST_LOG_BYTES = Gauge(
    "otterworks_request_log_bytes",
    "Bytes currently occupied by the per-request debug log directory.",
    ["service"],
)
REQUEST_LOG_CAPACITY_BYTES = Gauge(
    "otterworks_request_log_capacity_bytes",
    "Capacity of the volume backing the per-request debug log directory.",
    ["service"],
)
ROLLUP_RUNS_TOTAL = Counter(
    "otterworks_rollup_runs_total",
    "Executions of the scheduled document-stats rollup job.",
    ["service", "outcome"],
)
ROLLUP_DUPLICATE_WINDOWS = Gauge(
    "otterworks_rollup_duplicate_windows",
    "Rollup windows in the last hour that were computed more than once.",
    ["service"],
)

PROCESS_MEMORY_LIMIT_BYTES = Gauge(
    "otterworks_process_memory_limit_bytes",
    "Memory limit of the cgroup the service runs in (0 when unlimited).",
    ["service"],
)

FOLDER_DIGEST_QUEUE_DEPTH = Gauge(
    "otterworks_folder_digest_queue_depth",
    "Folder-digest jobs waiting in the in-process queue.",
)
FOLDER_DIGEST_OLDEST_JOB_AGE = Gauge(
    "otterworks_folder_digest_oldest_job_age_seconds",
    "Seconds the oldest queued folder-digest job has been waiting.",
)
FOLDER_DIGEST_JOBS_TOTAL = Counter(
    "otterworks_folder_digest_jobs_total",
    "Folder-digest jobs finished, by outcome.",
    ["outcome"],
)
FOLDER_DIGEST_JOB_SECONDS = Histogram(
    "otterworks_folder_digest_job_duration_seconds",
    "Wall time of one folder-digest job.",
    buckets=LATENCY_BUCKETS,
)
DB_POOL_CHECKED_OUT = Gauge(
    "otterworks_db_pool_checked_out",
    "Connections currently checked out of the shared SQLAlchemy pool.",
)
DB_POOL_CAPACITY = Gauge(
    "otterworks_db_pool_capacity",
    "Connections the shared SQLAlchemy pool can hand out (pool_size + max_overflow).",
)
DB_STATEMENT_TIMEOUTS_TOTAL = Counter(
    "otterworks_db_statement_timeouts_total",
    "SQL statements cancelled by the PostgreSQL statement_timeout.",
    ["source"],
)

STATEMENT_PREFIX_CHARS = 120

# Which caller issued the SQL running in this task: "api" unless a background
# job marks itself (the folder-digest worker sets "worker").
db_source: contextvars.ContextVar[str] = contextvars.ContextVar("db_source", default="api")

# The counter lives in a list so the endpoint task, which runs in a copy of the
# middleware's context, increments the same object the middleware reads.
_request_queries: contextvars.ContextVar[list[int] | None] = contextvars.ContextVar(
    "request_queries", default=None
)


def _read_rss_bytes() -> int:
    try:
        with open("/proc/self/statm") as fh:
            pages = int(fh.read().split()[1])
        return pages * 4096
    except (OSError, ValueError, IndexError):
        return 0


def _read_memory_limit_bytes() -> int:
    for path in ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
        try:
            with open(path) as fh:
                raw = fh.read().strip()
        except OSError:
            continue
        if raw.isdigit() and int(raw) < 1 << 60:
            return int(raw)
        return 0
    return 0


def instrument_sql() -> None:
    """Count and time every SQL statement, attributing it to the active request."""

    @event.listens_for(Engine, "before_cursor_execute")
    def _before(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        conn.info.setdefault("query_start", []).append(time.perf_counter())

    @event.listens_for(Engine, "after_cursor_execute")
    def _after(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        starts = conn.info.get("query_start") or []
        if starts:
            DB_QUERY_SECONDS.labels(SERVICE).observe(time.perf_counter() - starts.pop())
        DB_QUERIES_TOTAL.labels(SERVICE).inc()
        counter = _request_queries.get()
        if counter is not None:
            counter[0] += 1


def is_statement_timeout(exc: BaseException | None) -> bool:
    """Whether `exc` is, or wraps, a PostgreSQL statement cancellation (SQLSTATE 57014)."""
    seen: set[int] = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        if isinstance(exc, QueryCanceledError):
            return True
        if isinstance(exc, DBAPIError) and is_statement_timeout(exc.orig):
            return True
        exc = exc.__cause__ or exc.__context__
    return False


def record_statement_timeout(statement: str | None) -> None:
    source = db_source.get()
    DB_STATEMENT_TIMEOUTS_TOTAL.labels(source).inc()
    prefix = " ".join((statement or "").split())[:STATEMENT_PREFIX_CHARS]
    logger.warning("db_statement_timeout", source=source, statement=prefix)


def _on_db_error(context: ExceptionContext) -> None:
    if is_statement_timeout(context.original_exception):
        record_statement_timeout(context.statement)


def instrument_statement_timeouts() -> None:
    """Count and log every statement the server cancels on statement_timeout."""
    if not event.contains(Engine, "handle_error", _on_db_error):
        event.listen(Engine, "handle_error", _on_db_error)


def instrument_pool(engine: AsyncEngine, pool_size: int, max_overflow: int) -> None:
    """Export checked-out connections and capacity of the pool shared by API and jobs."""
    DB_POOL_CAPACITY.set(pool_size + max(max_overflow, 0))
    pool = engine.sync_engine.pool
    if isinstance(pool, QueuePool):
        DB_POOL_CHECKED_OUT.set_function(pool.checkedout)


def _handler_label(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if path:
        return str(path)
    return request.url.path


def instrument_app(app: FastAPI) -> None:
    """Expose HTTP RED metrics plus per-request query fan-out."""
    Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=False,
        excluded_handlers=["/health", "/metrics", "/ready"],
        should_instrument_requests_inprogress=True,
        inprogress_labels=True,
    ).add(
        _default_metrics(),
    ).instrument(app)

    @app.middleware("http")
    async def _count_queries(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        counter = [0]
        token = _request_queries.set(counter)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            _request_queries.reset(token)
        queries = counter[0]
        if request.url.path not in ("/health", "/metrics", "/ready"):
            DB_QUERIES_PER_REQUEST.labels(SERVICE, _handler_label(request)).observe(queries)
            response.headers["X-DB-Queries"] = str(queries)
            response.headers["X-Request-Duration-Ms"] = (
                f"{(time.perf_counter() - started) * 1000:.1f}"
            )
        PROCESS_RSS_BYTES.labels(SERVICE).set(_read_rss_bytes())
        PROCESS_MEMORY_LIMIT_BYTES.labels(SERVICE).set(_read_memory_limit_bytes())
        return response


def _default_metrics():  # noqa: ANN202
    from prometheus_fastapi_instrumentator import metrics

    return metrics.default(
        should_only_respect_2xx_for_highr=False,
        latency_highr_buckets=LATENCY_BUCKETS,
        latency_lowr_buckets=LATENCY_BUCKETS,
    )


def setup_tracing(app: FastAPI, engine: AsyncEngine) -> None:
    """Ship request and SQL spans to the OTLP collector when tracing is enabled."""
    if not settings.otel_enabled:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        endpoint = os.environ.get(
            "OTEL_EXPORTER_OTLP_ENDPOINT", settings.otel_exporter_otlp_endpoint
        ).rstrip("/")
        if not endpoint.endswith("/v1/traces"):
            endpoint = f"{endpoint}/v1/traces"
        provider = TracerProvider(
            resource=Resource.create(
                {SERVICE_NAME: settings.app_name, "service.version": settings.app_version}
            )
        )
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(
            app, excluded_urls="health,metrics,ready", tracer_provider=provider
        )
        SQLAlchemyInstrumentor().instrument(
            engine=engine.sync_engine, tracer_provider=provider, enable_commenter=False
        )
        logger.info("opentelemetry_instrumented", endpoint=endpoint)
    except Exception:
        logger.exception("opentelemetry_setup_failed")
