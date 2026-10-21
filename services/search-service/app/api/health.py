"""Health check and metrics endpoints."""

from __future__ import annotations

import asyncio

import structlog
from fastapi import APIRouter, Request
from prometheus_client import (
    Counter,
    Histogram,
    generate_latest,
)
from starlette.responses import Response

from app.flask_compat import jsonify

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
async def health() -> Response:
    """Liveness check — returns 200 if the process is running."""
    return jsonify({"status": "alive", "service": "search-service"}, 200)


@router.get("/health/ready")
async def readiness(request: Request) -> Response:
    """Readiness check — returns 503 if MeiliSearch is unreachable."""
    search_service = getattr(request.app.state, "search_service", None)

    healthy = False
    if search_service:
        healthy = await asyncio.to_thread(search_service.ping)

    if healthy:
        return jsonify({"ready": True}, 200)
    return jsonify({"ready": False, "reason": "meilisearch_unavailable"}, 503)


@router.get("/metrics")
async def metrics() -> Response:
    """Prometheus metrics endpoint."""
    return Response(generate_latest(), status_code=200, headers={"Content-Type": "text/plain; charset=utf-8"})
