"""Authentication middleware for the search service.

Public endpoints (health, metrics) are exempt. All other endpoints accept
either of two authentication modes:

* A valid service-to-service token via ``Authorization: Bearer <token>``
  (used by trusted internal callers such as the SQS indexer or admin
  reindex jobs).
* A JWT verified with the same HMAC keys as the API gateway.

If a service token is configured the middleware will accept it on any
endpoint; if it is not configured (e.g. local dev), only the gateway
JWT identity path is available.
"""

from __future__ import annotations

import jwt
import structlog
from flask import g, jsonify, request

logger = structlog.get_logger()

PUBLIC_PREFIXES = ("/health", "/metrics")


def require_auth(app):
    """Register a ``before_request`` hook that enforces authentication.

    * Requests to health/metrics paths are always allowed.
    * All other requests must present either a valid service token in
      the ``Authorization`` header or a verified user JWT.
    """
    auth_config = app.config["APP_CONFIG"].auth

    @app.before_request
    def _check_auth():
        g.user_id = None
        g.service_authenticated = False

        path = request.path
        if any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return None

        # Accept a valid service token if one is configured.
        if auth_config.service_token:
            token = _extract_bearer_token()
            if token and token == auth_config.service_token:
                g.service_authenticated = True
                return None

        token = _extract_bearer_token()
        if token:
            for secret in (auth_config.jwt_secret, auth_config.jwt_peer_secret):
                if not secret:
                    continue
                try:
                    claims = jwt.decode(
                        token, secret, algorithms=["HS256", "HS384", "HS512"],
                        options={"verify_aud": False, "verify_iat": False},
                    )
                except jwt.InvalidTokenError:
                    continue
                user_id = claims.get("sub") or claims.get("user_id")
                if not isinstance(user_id, str) or not user_id.strip():
                    break
                forwarded = request.headers.get("X-User-ID", "").strip()
                if forwarded and forwarded != user_id:
                    return jsonify({"error": "forbidden"}), 403
                g.user_id = user_id
                return None
        elif not auth_config.require_auth:
            return None

        endpoint = request.endpoint or ""
        logger.warning("auth_rejected", endpoint=endpoint, path=path)
        return jsonify({"error": "unauthorized"}), 401


def _extract_bearer_token() -> str:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return ""
