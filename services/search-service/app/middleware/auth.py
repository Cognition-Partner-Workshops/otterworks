"""Authentication middleware for the search service.

Public endpoints (health, metrics) are exempt. All other endpoints accept
either of two authentication modes:

* A valid service-to-service token via ``Authorization: Bearer <token>``
  (used by trusted internal callers such as the SQS indexer or admin
  reindex jobs). Only these callers may assert a user identity with the
  ``X-User-ID`` header.
* The caller's own JWT via ``Authorization: Bearer <jwt>``, which the API
  gateway forwards unchanged. The service verifies it with ``JWT_SECRET``
  and derives the user identity from its ``sub`` (or ``user_id``) claim.

A bare ``X-User-ID`` header is never treated as authentication, since the
service may be reachable without passing through the gateway.

The resolved identity is stored on ``flask.g.user_id`` and is what the
search endpoints use to scope results.
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
    * All other requests must present either a valid service token or a
      JWT signed with ``JWT_SECRET`` in the ``Authorization`` header.
    """
    auth_config = app.config["APP_CONFIG"].auth
    jwtSecrets = [s for s in (auth_config.jwt_secret, auth_config.jwt_peer_secret) if s]

    if auth_config.require_auth and not jwtSecrets:
        logger.warning("jwt_secret_not_configured", detail="user requests will be rejected")

    @app.before_request
    def _check_auth():
        g.user_id = None

        if not auth_config.require_auth:
            # Local development only: trust the header as-is.
            g.user_id = request.headers.get("X-User-ID", "").strip() or None
            return None

        path = request.path
        if any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return None

        token = _extract_bearer_token()

        if token and auth_config.service_token and hmac.compare_digest(
            token.encode(), auth_config.service_token.encode()
        ):
            g.user_id = request.headers.get("X-User-ID", "").strip() or None
            return None

        if token:
            userId = _verify_user_jwt(token, jwtSecrets)
            if userId:
                g.user_id = userId
                return None

        logger.warning("auth_rejected", endpoint=request.endpoint or "", path=path)
        return jsonify({"error": "unauthorized"}), 401


def _verify_user_jwt(token: str, secrets: list[str]) -> str | None:
    """Return the user ID from a valid JWT, or None if it cannot be verified."""
    for secret in secrets:
        try:
            claims = jwt.decode(token, secret, algorithms=JWT_ALGORITHMS)
        except jwt.PyJWTError:
            continue
        userId = claims.get("sub") or claims.get("user_id")
        if isinstance(userId, str) and userId.strip():
            return userId.strip()
        return None
    return None


def _extract_bearer_token() -> str:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return ""
