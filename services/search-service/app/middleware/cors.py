"""CORS middleware reproducing flask-cors 4.0 defaults.

Starlette's ``CORSMiddleware`` answers preflights itself and omits
``Access-Control-Allow-Origin`` when the request has no ``Origin``; flask-cors
does neither. This middleware decorates every response the app produces
(including preflights, which still reach routing and auth) exactly as
``CORS(app, origins=[...])`` did.
"""

from __future__ import annotations

from collections.abc import Sequence

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

ALL_METHODS = ("GET", "HEAD", "POST", "OPTIONS", "PUT", "PATCH", "DELETE")


class CORSMiddleware:
    """Pure ASGI CORS middleware with flask-cors semantics.

    Fixed flask-cors defaults: ``methods`` = all, ``allow_headers='*'``, no
    expose headers, no credentials, no max age, ``always_send=True``,
    ``vary_header=True``, ``allow_private_network=True``.
    """

    def __init__(self, app: ASGIApp, allow_origins: Sequence[str]) -> None:
        self.app = app
        self.allow_origins = list(allow_origins)
        self.methods = ", ".join(sorted(ALL_METHODS))

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_headers = Headers(scope=scope)
        cors_headers = self._cors_headers(request_headers, scope["method"])

        async def send_with_cors(message: Message) -> None:
            if message["type"] == "http.response.start" and cors_headers:
                headers = MutableHeaders(scope=message)
                if "access-control-allow-origin" not in headers:
                    for name, value in cors_headers:
                        headers.append(name, value)
            await send(message)

        await self.app(scope, receive, send_with_cors)

    def _origins_to_set(self, request_origin: str | None) -> list[str]:
        if request_origin:
            lowered = request_origin.lower()
            if any(lowered == o.lower() for o in self.allow_origins):
                return [request_origin]
            return []
        return sorted(self.allow_origins)

    def _cors_headers(self, request_headers: Headers, method: str) -> list[tuple[str, str]]:
        origins = self._origins_to_set(request_headers.get("origin"))
        if not origins:
            return []

        # flask-cors builds a MultiDict and emits only the first value per key.
        headers: list[tuple[str, str]] = [("Access-Control-Allow-Origin", origins[0])]

        if request_headers.get("access-control-request-private-network") == "true":
            headers.append(("Access-Control-Allow-Private-Network", "true"))

        if method == "OPTIONS":
            acl_request_method = request_headers.get("access-control-request-method", "").upper()
            # Substring test against the serialized method list, as flask-cors does.
            if acl_request_method and acl_request_method in self.methods:
                acl_request_headers = request_headers.get("access-control-request-headers")
                if acl_request_headers:
                    allow = ", ".join(
                        sorted(h.strip() for h in acl_request_headers.split(","))
                    )
                    if allow:
                        headers.append(("Access-Control-Allow-Headers", allow))
                headers.append(("Access-Control-Allow-Methods", self.methods))

        if len(self.allow_origins) > 1 or len(origins) > 1:
            headers.append(("Vary", "Origin"))

        return headers
