"""Health check and metrics endpoints."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import (
    Counter,
    Histogram,
    generate_latest,
)

logger = structlog.get_logger()

router = APIRouter()

# Prometheus metrics
REQUEST_COUNT = Counter(
    "search_service_requests_total",
    "Total number of requests to the search service",
    ["method", "endpoint", "status"],
)
REQUEST_LATENCY = Histogram(
    "search_service_request_duration_seconds",
    "Request latency in seconds",
    ["method", "endpoint"],
)
SEARCH_COUNT = Counter(
    "search_service_searches_total",
    "Total number of search queries executed",
)
INDEX_COUNT = Counter(
    "search_service_index_operations_total",
    "Total number of index operations",
    ["operation", "type"],
)


@router.get("/health")
def health() -> JSONResponse:
    """Liveness check — returns 200 if the process is running."""
    return JSONResponse({"status": "alive", "service": "search-service"}, status_code=200)


@router.get("/health/ready")
def readiness(request: Request) -> JSONResponse:
    """Readiness check — returns 503 if MeiliSearch is unreachable."""
    search_service = getattr(request.app.state, "search_service", None)

    healthy = False
    if search_service:
        healthy = search_service.ping()

    if healthy:
        return JSONResponse({"ready": True}, status_code=200)
    return JSONResponse({"ready": False, "reason": "meilisearch_unavailable"}, status_code=503)


@router.get("/metrics")
def metrics() -> Response:
    """Prometheus metrics endpoint."""
    return Response(generate_latest(), status_code=200, media_type="text/plain; charset=utf-8")
