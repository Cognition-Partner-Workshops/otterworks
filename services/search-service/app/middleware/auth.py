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

This is a pure ASGI middleware rather than a FastAPI dependency so it runs
before routing, like Flask's ``before_request``: unauthenticated requests to
unknown paths or with the wrong method get 401, not 404/405.
"""

from __future__ import annotations

import structlog
from starlette.datastructures import Headers
from starlette.routing import get_route_path
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import AuthConfig
from app.flask_compat import header, jsonify

logger = structlog.get_logger()

PUBLIC_PREFIXES = ("/health", "/metrics")


class AuthMiddleware:
    """Enforce authentication on every HTTP request before routing.

    * Requests to health/metrics paths are always allowed.
    * All other requests must present either a valid service token in
      the ``Authorization`` header or an ``X-User-ID`` header set by
      the API gateway after JWT validation.
    """

    def __init__(self, app: ASGIApp, auth_config: AuthConfig) -> None:
        self.app = app
        self.auth_config = auth_config

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or self._is_allowed(scope):
            await self.app(scope, receive, send)
            return

        logger.warning("auth_rejected", endpoint=_endpoint(scope), path=get_route_path(scope))
        await jsonify({"error": "unauthorized"}, 401)(scope, receive, send)

    def _is_allowed(self, scope: Scope) -> bool:
        if not self.auth_config.require_auth:
            return True

        path = get_route_path(scope)
        if any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return True

        headers = Headers(scope=scope)

        # Accept a valid service token if one is configured.
        if self.auth_config.service_token:
            token = _extract_bearer_token(headers)
            if token and token == self.auth_config.service_token:
                return True

        # Otherwise require gateway-injected user identity.
        return bool(header(headers, "X-User-ID").strip())


def _extract_bearer_token(headers: Headers) -> str:
    auth_header = header(headers, "Authorization")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return ""


def _endpoint(scope: Scope) -> str:
    """Flask's ``request.endpoint``: the matched route's name, ``""`` on 404/405."""
    router = getattr(scope.get("app"), "router", None)
    match_rule = getattr(router, "match_rule", None)
    if match_rule is None:
        return ""
    route = match_rule(scope).route
    return getattr(route, "name", None) or ""
