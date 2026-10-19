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

Index mutation (``/index/...``) and ``/reindex`` are administrative: a
plain user identity is not enough. They require the service token or a
gateway-forwarded ``X-User-Roles`` header containing ``ADMIN``.
"""

from __future__ import annotations

import structlog
from flask import jsonify, request

logger = structlog.get_logger()

PUBLIC_PREFIXES = ("/health", "/metrics")
ADMIN_PREFIXES = ("/api/v1/search/index", "/api/v1/search/reindex")
ADMIN_ROLE = "ADMIN"


def require_auth(app):
    """Register a ``before_request`` hook that enforces authentication.

    * Requests to health/metrics paths are always allowed.
    * All other requests must present either a valid service token in
      the ``Authorization`` header or an ``X-User-ID`` header set by
      the API gateway after JWT validation.
    * Index mutation and reindex paths additionally require the service
      token or the ``ADMIN`` role in the gateway-set ``X-User-Roles``.
    """
    auth_config = app.config["APP_CONFIG"].auth

    @app.before_request
    def _check_auth():
        if not auth_config.require_auth:
            return None

        path = request.path
        if any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return None

        endpoint = request.endpoint or ""

        # Accept a valid service token if one is configured.
        if auth_config.service_token:
            token = _extract_bearer_token()
            if token and token == auth_config.service_token:
                return None

        # Otherwise require gateway-injected user identity.
        user_id = request.headers.get("X-User-ID", "").strip()
        if not user_id:
            logger.warning("auth_rejected", endpoint=endpoint, path=path)
            return jsonify({"error": "unauthorized"}), 401

        if _is_admin_path(path) and ADMIN_ROLE not in _user_roles():
            logger.warning("auth_forbidden", endpoint=endpoint, path=path, user_id=user_id)
            return jsonify({"error": "forbidden"}), 403

        return None


def _is_admin_path(path: str) -> bool:
    return any(path == p or path.startswith(p + "/") for p in ADMIN_PREFIXES)


def _user_roles() -> set[str]:
    raw = request.headers.get("X-User-Roles", "")
    return {r.strip().upper() for r in raw.split(",") if r.strip()}


def _extract_bearer_token() -> str:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return ""
