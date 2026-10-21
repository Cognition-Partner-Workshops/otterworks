"""Flask-compatible exception handlers.

Flask answers routing errors, ``abort()``, ``get_json()`` failures and
unhandled exceptions with Werkzeug's HTML error page; handlers return their
own ``{"error": ...}`` JSON. These handlers keep both shapes so FastAPI never
emits its ``{"detail": ...}`` bodies or 422s.
"""

from __future__ import annotations

from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

from app.flask_compat import WerkzeugHTTPError, jsonify, werkzeug_error_response

PAGE_SIZE_FIELDS = frozenset({"page", "size"})


async def _werkzeug_error_handler(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, WerkzeugHTTPError)
    return werkzeug_error_response(exc.code, exc.description, exc.headers)


async def _http_exception_handler(request: Request, exc: Exception) -> Response:
    """``HTTPException(code)`` renders like ``abort(code)``; a custom detail like a handler's JSON error."""
    assert isinstance(exc, StarletteHTTPException)
    if exc.detail == HTTPStatus(exc.status_code).phrase:
        return werkzeug_error_response(exc.status_code, headers=exc.headers)
    return jsonify({"error": exc.detail}, exc.status_code, headers=exc.headers)


async def _validation_error_handler(request: Request, exc: Exception) -> Response:
    """Safety net only: Flask had no validation layer, routes should parse inputs by hand."""
    assert isinstance(exc, RequestValidationError)
    fields = {err["loc"][-1] for err in exc.errors() if err.get("loc")}
    if fields and fields <= PAGE_SIZE_FIELDS:
        return jsonify({"error": "Invalid page or size parameter"}, 400)
    return jsonify({"error": "Invalid request"}, 400)


async def _internal_error_handler(request: Request, exc: Exception) -> Response:
    return werkzeug_error_response(500)


def register_exception_handlers(app: FastAPI) -> None:
    """Install the Flask-compatible handlers (``Exception`` goes to ServerErrorMiddleware)."""
    app.add_exception_handler(WerkzeugHTTPError, _werkzeug_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(Exception, _internal_error_handler)
