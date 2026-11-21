"""Authentication middleware for the search service.

Public endpoints (health, metrics) are exempt. All other endpoints accept
either of two authenticated modes:

* A valid service-to-service token via ``Authorization: Bearer <token>``
  (used by trusted internal callers).
* A JWT signed with the configured secret (used by user-facing requests).
"""

from __future__ import annotations

import hmac

import jwt
import structlog
from flask import g, jsonify, request

logger = structlog.get_logger()

PUBLIC_PREFIXES = ("/health", "/metrics")
JWT_ALGORITHMS = ["HS256", "HS384", "HS512"]


def require_auth(app):
    """Register a ``before_request`` hook that enforces authentication.

    * Requests to health/metrics paths are always allowed.
    * All other requests must present either a valid service token in
      the ``Authorization`` header or a valid user JWT.
    """
    auth_config = app.config["APP_CONFIG"].auth

    @app.before_request
    def _check_auth():
        if not auth_config.require_auth:
            return None

        path = request.path
        if any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return None

        token = _extract_bearer_token()
        if auth_config.service_token:
            if token and hmac.compare_digest(token, auth_config.service_token):
                g.service_call = True
                g.caller_id = None
                return None

        endpoint = request.endpoint or ""
        if not auth_config.jwt_secret:
            logger.error("authentication_not_configured", endpoint=endpoint, path=path)
            return jsonify({"error": "service unavailable: authentication is not configured"}), 503

        if not token:
            logger.warning("auth_rejected", endpoint=endpoint, path=path)
            return jsonify({"error": "unauthorized"}), 401

        try:
            claims = jwt.decode(
                token,
                auth_config.jwt_secret,
                algorithms=JWT_ALGORITHMS,
            )
        except jwt.PyJWTError:
            logger.warning("auth_rejected", endpoint=endpoint, path=path)
            return jsonify({"error": "unauthorized"}), 401

        user_id = claims.get("sub") or claims.get("user_id")
        if not isinstance(user_id, str) or not user_id.strip():
            logger.warning("auth_rejected", endpoint=endpoint, path=path)
            return jsonify({"error": "unauthorized"}), 401

        g.caller_id = user_id.strip()
        g.service_call = False


def _extract_bearer_token() -> str:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return ""


def caller_id() -> str | None:
    """Return the authenticated caller id, if this request has one."""
    return g.get("caller_id")
