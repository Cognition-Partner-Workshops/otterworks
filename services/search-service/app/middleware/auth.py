"""Authentication middleware for the search service.

Public endpoints (health, metrics) are exempt. All other endpoints accept
either of two authentication modes:

* A valid service-to-service token via ``Authorization: Bearer <token>``
  (used by trusted internal callers such as the SQS indexer or admin
  reindex jobs).
* A signed access JWT. The user identity is derived from its subject, never
  from a caller-supplied ``X-User-ID`` header.

If a service token is configured the middleware will accept it on any
endpoint; if it is not configured (e.g. local dev), only the gateway
JWT path is available and internal endpoints become reachable only
via the gateway.
"""

from __future__ import annotations

import hmac
from uuid import UUID

import jwt
import structlog
from flask import jsonify, request

logger = structlog.get_logger()

PUBLIC_PREFIXES = ("/health", "/metrics")


def require_auth(app):
    """Register a ``before_request`` hook that enforces authentication.

    * Requests to health/metrics paths are always allowed.
    * All other requests must present either a valid service token in
      the ``Authorization`` header or a signed access JWT.
    """
    auth_config = app.config["APP_CONFIG"].auth

    @app.before_request
    def _check_auth():
        if not auth_config.require_auth:
            return None

        path = request.path
        if any(path == p or path.startswith(p + "/") for p in PUBLIC_PREFIXES):
            return None

        # Accept a valid service token if one is configured.
        if auth_config.service_token:
            token = _extract_bearer_token()
            if token and hmac.compare_digest(token.encode(), auth_config.service_token.encode()):
                return None

        token = _extract_bearer_token()
        if token:
            for secret in (auth_config.jwt_secret, auth_config.jwt_peer_secret):
                if not secret:
                    continue
                try:
                    claims = jwt.decode(
                        token, secret, algorithms=["HS256", "HS384", "HS512"],
                        options={"require": ["exp", "sub"]},
                    )
                    if claims.get("type") != "access":
                        continue
                    user_id = str(UUID(claims["sub"]))
                except (jwt.InvalidTokenError, ValueError, TypeError, AttributeError):
                    continue
                request.environ["HTTP_X_USER_ID"] = user_id
                return None

        endpoint = request.endpoint or ""
        logger.warning("auth_rejected", endpoint=endpoint, path=path)
        return jsonify({"error": "unauthorized"}), 401


def _extract_bearer_token() -> str:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return ""
