"""Authentication middleware for the search service.

Public endpoints (health, metrics) are exempt.

Internal endpoints (indexing, delete-from-index and reindex) mutate the index
every tenant user searches, so they only accept the service-to-service token
(``Authorization: Bearer <SEARCH_SERVICE_TOKEN>``). A gateway-forwarded
``X-User-ID`` never satisfies them, and they stay closed when no token is
configured or when ``REQUIRE_AUTH`` is off.

All other endpoints accept either the service token or the ``X-User-ID``
header injected by the API gateway after it has validated the caller's JWT.
"""

from __future__ import annotations

import hmac

import structlog
from flask import jsonify, request

logger = structlog.get_logger()

PUBLIC_PREFIXES = ("/health", "/metrics")
INTERNAL_PREFIXES = ("/api/v1/search/index", "/api/v1/search/reindex")


def is_internal_path(path: str) -> bool:
    return any(path == p or path.startswith(p + "/") for p in INTERNAL_PREFIXES)


def require_auth(app):
    """Register a ``before_request`` hook that enforces authentication."""
    auth_config = app.config["APP_CONFIG"].auth

    @app.before_request
    def _check_auth():
        path = request.path
        if any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return None

        has_service_token = _service_token_valid(auth_config.service_token)

        if is_internal_path(path):
            if has_service_token:
                return None
            logger.warning("internal_route_rejected", path=path)
            return jsonify({"error": "forbidden"}), 403

        if not auth_config.require_auth or has_service_token:
            return None

        user_id = request.headers.get("X-User-ID", "").strip()
        if user_id:
            return None

        endpoint = request.endpoint or ""
        logger.warning("auth_rejected", endpoint=endpoint, path=path)
        return jsonify({"error": "unauthorized"}), 401


def _service_token_valid(configured: str) -> bool:
    if not configured:
        return False
    presented = _extract_bearer_token()
    if not presented:
        return False
    return hmac.compare_digest(presented.encode(), configured.encode())


def _extract_bearer_token() -> str:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return ""
