"""Prometheus request instrumentation (Flask's ``before_request``/``after_request`` timer).

Wraps the whole Starlette stack (inside the CORS wrapper) so every response
Flask's ``after_request`` saw is counted: auth 401s, routing 404/405/OPTIONS,
handler responses and unhandled-error 500s. ``endpoint`` is the matched rule
as Flask spells it (``/api/v1/search/index/<doc_type>/<doc_id>``), or
``unknown`` when no rule matched the path and method.
"""

from __future__ import annotations

import re
import time

from starlette.routing import get_route_path
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.health import REQUEST_COUNT, REQUEST_LATENCY

UNINSTRUMENTED_PATHS = frozenset({"/metrics", "/health"})

_PARAM = re.compile(r"\{(\w+)(?::(\w+))?\}")
_CONVERTERS = {"str": "", "path": "path", "int": "int", "float": "float", "uuid": "uuid"}


def flask_rule(path: str) -> str:
    """Starlette path template -> Werkzeug rule string (``{a}`` -> ``<a>``, ``{a:int}`` -> ``<int:a>``)."""

    def repl(m: re.Match[str]) -> str:
        converter = _CONVERTERS.get(m.group(2) or "str", m.group(2))
        return f"<{converter}:{m.group(1)}>" if converter else f"<{m.group(1)}>"

    return _PARAM.sub(repl, path)


def _endpoint(scope: Scope) -> str:
    """Flask's ``request.url_rule.rule``, else ``"unknown"`` (404/405)."""
    match_rule = getattr(getattr(scope.get("app"), "router", None), "match_rule", None)
    route = match_rule(scope).route if match_rule else None
    path = getattr(route, "path", None)
    return flask_rule(path) if path else "unknown"


class MetricsMiddleware:
    """Record ``search_service_requests_total`` / ``search_service_request_duration_seconds``."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or get_route_path(scope) in UNINSTRUMENTED_PATHS:
            await self.app(scope, receive, send)
            return

        start = time.monotonic()
        method = scope["method"]
        endpoint = _endpoint(scope)
        status = 500

        async def send_with_status(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_with_status)
        finally:
            elapsed = time.monotonic() - start
            REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
            REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(elapsed)
