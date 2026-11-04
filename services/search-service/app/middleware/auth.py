"""Authentication middleware for the search service.

Public endpoints (health, metrics) are exempt. The rest fall in two groups:

* Internal endpoints (the ``index`` blueprint: ``/index/*`` and ``/reindex``)
  accept only the service-to-service token via
  ``Authorization: Bearer <SEARCH_SERVICE_TOKEN>``. They never accept the
  gateway's ``X-User-ID``, are enforced even when ``REQUIRE_AUTH`` is off, and
  fail closed (401) when no token is configured.
* User-facing endpoints accept the service token or the ``X-User-ID`` header
  injected by the API gateway after it has validated the caller's JWT.
"""

from __future__ import annotations

import hmac

import structlog
from flask import jsonify, request

logger = structlog.get_logger()

PUBLIC_PREFIXES = ("/health", "/metrics")
INTERNAL_BLUEPRINTS = frozenset({"index"})


def require_auth(app):
    """Register a ``before_request`` hook that enforces authentication."""
    auth_config = app.config["APP_CONFIG"].auth

    @app.before_request
    def _check_auth():
        path = request.path
        if any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return None

        has_service_token = _is_valid_service_token(auth_config.service_token)

        if request.blueprint in INTERNAL_BLUEPRINTS:
            if has_service_token:
                return None
            logger.warning(
                "internal_auth_rejected",
                endpoint=request.endpoint or "",
                path=path,
                token_configured=bool(auth_config.service_token),
            )
            return jsonify({"error": "unauthorized"}), 401

        if not auth_config.require_auth or has_service_token:
            return None

        if request.headers.get("X-User-ID", "").strip():
            return None

        logger.warning("auth_rejected", endpoint=request.endpoint or "", path=path)
        return jsonify({"error": "unauthorized"}), 401


def _is_valid_service_token(expected: str) -> bool:
    if not expected:
        return False
    token = _extract_bearer_token()
    return bool(token) and hmac.compare_digest(token.encode(), expected.encode())


def _extract_bearer_token() -> str:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return ""
