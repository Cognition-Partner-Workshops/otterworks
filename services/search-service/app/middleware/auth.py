"""Authentication middleware for the search service.

Public endpoints (health, metrics) are exempt. The indexing endpoints
(``/index/*`` and ``/reindex``) are internal: they accept only a valid
service-to-service token via ``Authorization: Bearer <token>``
(``SEARCH_SERVICE_TOKEN``). A gateway-forwarded user identity is not
enough, because the gateway forwards every authenticated user.

All other endpoints accept either the service token or the ``X-User-ID``
header injected by the API gateway after it has validated the caller's
JWT. If no service token is configured, the internal endpoints are
closed over HTTP.
"""

from __future__ import annotations

import hmac

import structlog
from flask import jsonify, request

logger = structlog.get_logger()

PUBLIC_PREFIXES = ("/health", "/metrics")
INTERNAL_BLUEPRINTS = ("index",)


def require_auth(app):
    """Register a ``before_request`` hook that enforces authentication.

    * Requests to health/metrics paths are always allowed.
    * Internal indexing endpoints require the service token.
    * All other requests must present either the service token or an
      ``X-User-ID`` header set by the API gateway after JWT validation.
    """
    auth_config = app.config["APP_CONFIG"].auth

    @app.before_request
    def _check_auth():
        if not auth_config.require_auth:
            return None

        path = request.path
        if any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return None

        if _has_service_token(auth_config.service_token):
            return None

        endpoint = request.endpoint or ""
        if request.blueprint in INTERNAL_BLUEPRINTS:
            logger.warning("internal_auth_rejected", endpoint=endpoint, path=path)
            return jsonify({"error": "forbidden"}), 403

        user_id = request.headers.get("X-User-ID", "").strip()
        if user_id:
            return None

        logger.warning("auth_rejected", endpoint=endpoint, path=path)
        return jsonify({"error": "unauthorized"}), 401


def _has_service_token(service_token: str) -> bool:
    if not service_token:
        return False
    token = _extract_bearer_token()
    return bool(token) and hmac.compare_digest(token.encode(), service_token.encode())


def _extract_bearer_token() -> str:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return ""
