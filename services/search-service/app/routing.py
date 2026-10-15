"""Werkzeug-style URL matching for the FastAPI application router.

Starlette's router answers 405 with only the matched route's methods, never
adds ``HEAD``/``OPTIONS`` and redirects (307) on a trailing-slash mismatch.
Flask/Werkzeug instead:

* adds ``HEAD`` to every ``GET`` rule and ``OPTIONS`` to every rule; an
  ``OPTIONS`` request is answered with an empty 200 whose ``Allow`` header
  lists the methods of every rule matching the path;
* answers 405 with ``Allow`` = union of those methods, and 404 otherwise, both
  as Werkzeug HTML pages;
* lets a rule ending in ``/`` registered with ``strict_slashes=False`` answer
  the path without the slash directly; a path that only differs by a trailing
  slash from a rule without one is a 404.

``FlaskRouter`` reproduces that. Overlapping rules are tried in registration
order (Werkzeug orders by rule weight); none of this service's rules overlap.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from fastapi.routing import APIRouter
from starlette.responses import Response
from starlette.routing import BaseRoute, Match, Route
from starlette.types import Receive, Scope, Send

from app.flask_compat import werkzeug_error_response

F = TypeVar("F", bound=Callable[..., Any])


def strict_slashes(enabled: bool) -> Callable[[F], F]:
    """Flask's ``strict_slashes`` rule option, set on the endpoint function.

    ``@router.get("/")`` stacked on ``@strict_slashes(False)`` serves both
    ``<prefix>/`` and ``<prefix>`` without a redirect.
    """

    def decorator(endpoint: F) -> F:
        endpoint.strict_slashes = enabled  # type: ignore[attr-defined]
        return endpoint

    return decorator


@dataclass
class RuleMatch:
    """Result of matching a request the way ``MapAdapter.match`` does."""

    route: BaseRoute | None
    child_scope: Scope = field(default_factory=dict)
    allowed_methods: frozenset[str] = frozenset()


def _flask_methods(route: BaseRoute) -> frozenset[str] | None:
    """Methods Werkzeug would register for the rule; ``None`` matches any method."""
    if isinstance(route, Route) and route.methods:
        return frozenset(route.methods | {"OPTIONS"})
    return None


def _match_path(route: BaseRoute, scope: Scope) -> tuple[Match, Scope]:
    match, child_scope = route.matches(scope)
    if (
        match is Match.NONE
        and isinstance(route, Route)
        and route.path.endswith("/")
        and not getattr(route.endpoint, "strict_slashes", True)
        and not scope["path"].endswith("/")
    ):
        match, child_scope = route.matches({**scope, "path": scope["path"] + "/"})
    return match, child_scope


def default_options_response(methods: Iterable[str]) -> Response:
    """``Flask.make_default_options_response()``."""
    return Response(b"", status_code=200, headers={"Allow": ", ".join(sorted(methods))}, media_type="text/html")


class FlaskRouter(APIRouter):
    """``APIRouter`` with Werkzeug's method, ``OPTIONS`` and slash semantics."""

    def add_api_route(self, path: str, endpoint: Callable[..., Any], **kwargs: Any) -> None:
        methods = {m.upper() for m in (kwargs.pop("methods", None) or ("GET",))}
        if "GET" in methods:
            methods.add("HEAD")
        super().add_api_route(path, endpoint, methods=methods, **kwargs)

    def match_rule(self, scope: Scope) -> RuleMatch:
        """First route matching path and method, else the union of methods valid for the path."""
        method = scope["method"]
        allowed: set[str] = set()
        for route in self.routes:
            match, child_scope = _match_path(route, scope)
            if match is Match.NONE:
                continue
            methods = _flask_methods(route)
            if methods is None:
                if match is Match.FULL:
                    return RuleMatch(route, child_scope)
                continue
            if method in methods:
                return RuleMatch(route, child_scope, methods)
            allowed |= methods
        return RuleMatch(None, allowed_methods=frozenset(allowed))

    def allowed_methods(self, scope: Scope) -> frozenset[str]:
        """``MapAdapter.allowed_methods()``: methods of every rule matching the path."""
        return self.match_rule({**scope, "method": ""}).allowed_methods

    async def app(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await super().app(scope, receive, send)
            return
        if "router" not in scope:
            scope["router"] = self

        rule = self.match_rule(scope)
        route = rule.route
        if route is None:
            if rule.allowed_methods:
                allow = ", ".join(sorted(rule.allowed_methods))
                response = werkzeug_error_response(405, headers={"Allow": allow})
            else:
                response = werkzeug_error_response(404)
            await response(scope, receive, send)
            return

        if scope["method"] == "OPTIONS" and isinstance(route, Route) and "OPTIONS" not in (route.methods or ()):
            await default_options_response(self.allowed_methods(scope))(scope, receive, send)
            return

        scope.update(rule.child_scope)
        await route.handle(scope, receive, send)


def install_flask_router(router: APIRouter) -> FlaskRouter:
    """Retype FastAPI's application router in place (``FastAPI`` hard-codes ``APIRouter``)."""
    router.__class__ = FlaskRouter
    router.redirect_slashes = False
    # Router.__init__ bound middleware_stack to the base class's ``app``.
    router.middleware_stack = router.app
    assert isinstance(router, FlaskRouter)
    return router
