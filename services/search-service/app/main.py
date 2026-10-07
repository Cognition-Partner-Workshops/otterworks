"""OtterWorks Search Service - Full-text search via MeiliSearch."""

from __future__ import annotations

import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI
from starlette.types import ASGIApp

from app.api.health import router as health_router
from app.api.index import router as index_router
from app.api.search import router as search_router
from app.config import AppConfig
from app.errors import register_exception_handlers
from app.middleware.auth import AuthMiddleware
from app.middleware.cors import CORSMiddleware
from app.routing import install_flask_router
from app.services.meilisearch_client import MeiliSearchService

logger = structlog.get_logger()

CORS_ORIGINS = ["http://localhost:3000", "http://localhost:4200"]


def configure_logging(log_level: str) -> None:
    """Configure structured JSON logging via structlog."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )


class SearchServiceApp(FastAPI):
    """FastAPI with Werkzeug routing and CORS wrapped around the whole stack.

    ``add_middleware`` would place CORS inside Starlette's
    ``ServerErrorMiddleware``, so unhandled-error 500s would lose the CORS
    headers flask-cors adds to them (``intercept_exceptions``).
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(redirect_slashes=False, **kwargs)
        install_flask_router(self.router)

    def build_middleware_stack(self) -> ASGIApp:
        return CORSMiddleware(super().build_middleware_stack(), allow_origins=CORS_ORIGINS)


def create_app(config: AppConfig | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    if config is None:
        config = AppConfig()

    configure_logging(config.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        search_service = MeiliSearchService(config.meilisearch)
        app.state.search_service = search_service

        # Non-fatal if MeiliSearch is not available yet
        try:
            search_service.ensure_indices()
            logger.info("meilisearch_indices_ensured")
        except Exception:
            logger.warning("meilisearch_indices_creation_deferred", reason="MeiliSearch not available")

        logger.info(
            "search_service_created",
            port=config.port,
            meilisearch_url=config.meilisearch.url,
            sqs_enabled=config.sqs.enabled,
        )
        yield

    app = SearchServiceApp(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.config = config
    register_exception_handlers(app)
    # Inside ServerErrorMiddleware, before routing: Flask's before_request.
    app.add_middleware(AuthMiddleware, auth_config=config.auth)

    app.include_router(health_router)
    app.include_router(search_router)
    app.include_router(index_router)

    return app


if __name__ == "__main__":
    import uvicorn

    app_config = AppConfig()
    uvicorn.run(create_app(app_config), host=app_config.host, port=app_config.port)
