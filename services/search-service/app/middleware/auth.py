"""Authentication middleware for the search service.

Public endpoints (health, metrics) are exempt. All other endpoints accept
either of two authentication modes:

* A valid service-to-service token via ``Authorization: Bearer <token>``
  (used by trusted internal callers such as the SQS indexer or admin
  reindex jobs).
* The ``X-User-ID`` header injected by the API gateway after it has
  validated the caller's JWT (used by user-facing requests proxied
  through the gateway).

If a service token is configured the middleware will accept it on any
endpoint; if it is not configured (e.g. local dev), only the gateway
identity path is available and internal endpoints become reachable only
via the gateway.
"""

from __future__ import annotations

from dataclasses import dataclass

import jwt
import structlog
from flask import current_app, jsonify, request

logger = structlog.get_logger()

PUBLIC_PREFIXES = ("/health", "/metrics")
ADMIN_ROLES = frozenset({"ADMIN", "ROLE_ADMIN"})


@dataclass(frozen=True)
class Caller:
    """Who is making the current request.

    ``user_id`` is the gateway-injected ``X-User-ID``. A caller with no user
    identity only gets this far when it holds the service token or when
    ``REQUIRE_AUTH`` is off (internal, cluster-only callers), so it is trusted.
    """

    user_id: str | None
    is_admin: bool = False
    is_service: bool = False

    @property
    def is_trusted(self) -> bool:
        return self.is_service or self.is_admin or self.user_id is None


def get_caller() -> Caller:
    """Resolve the caller of the current request."""
    auth_config = current_app.config["APP_CONFIG"].auth
    token = _extract_bearer_token()
    if auth_config.service_token and token and token == auth_config.service_token:
        return Caller(user_id=None, is_service=True)

    user_id = request.headers.get("X-User-ID", "").strip() or None
    if user_id is None:
        return Caller(user_id=None)
    return Caller(user_id=user_id, is_admin=_token_grants_admin(token, user_id, auth_config.jwt_secret))


def _token_grants_admin(token: str, user_id: str, secret: str) -> bool:
    """True if *token* is a valid access JWT for *user_id* carrying an admin role."""
    if not token or not secret:
        return False
    try:
        claims = jwt.decode(token, secret, algorithms=["HS256", "HS384", "HS512"])
    except jwt.PyJWTError:
        return False
    if claims.get("type", "access") != "access":
        return False
    if str(claims.get("sub") or claims.get("user_id") or "") != user_id:
        return False
    roles = claims.get("roles") or []
    if isinstance(roles, str):
        roles = [roles]
    return any(str(role).upper() in ADMIN_ROLES for role in roles)


def require_auth(app):
    """Register a ``before_request`` hook that enforces authentication.

    * Requests to health/metrics paths are always allowed.
    * All other requests must present either a valid service token in
      the ``Authorization`` header or an ``X-User-ID`` header set by
      the API gateway after JWT validation.
    """
    auth_config = app.config["APP_CONFIG"].auth

    @app.before_request
    def _check_auth():
        if not auth_config.require_auth:
            return None

        path = request.path
        if any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return None

        # Accept a valid service token if one is configured.
        if auth_config.service_token:
            token = _extract_bearer_token()
            if token and token == auth_config.service_token:
                return None

        # Otherwise require gateway-injected user identity.
        user_id = request.headers.get("X-User-ID", "").strip()
        if user_id:
            return None

        endpoint = request.endpoint or ""
        logger.warning("auth_rejected", endpoint=endpoint, path=path)
        return jsonify({"error": "unauthorized"}), 401


def _extract_bearer_token() -> str:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return ""
