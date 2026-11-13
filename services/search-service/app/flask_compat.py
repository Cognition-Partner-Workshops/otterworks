"""Request/response helpers that reproduce Flask 3.0 behaviour under FastAPI.

Route handlers ported from Flask should use these instead of FastAPI's
parameter parsing so inputs and outputs stay byte-compatible:

* ``query_arg`` - ``request.args.get``: first value wins (Starlette keeps the last).
* ``header`` - ``request.headers.get`` behind gunicorn: repeated headers are
  joined with ``","`` (Starlette returns the first).
* ``get_json`` - ``request.get_json()``: 415 HTML unless the Content-Type is
  JSON, 400 HTML for an empty or undecodable body, otherwise ``json.loads``
  (so ``null`` gives ``None``).
* ``jsonify`` - ``flask.jsonify``: sorted keys, ASCII, compact, trailing newline.
* ``WerkzeugHTTPError`` / ``werkzeug_error_response`` - Werkzeug's HTML error
  page, as sent for ``abort(code)``, routing errors and unhandled exceptions.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.responses import Response

UNSUPPORTED_JSON_MEDIA_TYPE = (
    "Did not attempt to load JSON data because the request Content-Type was not 'application/json'."
)

# Werkzeug 3.0 ``HTTPException`` names and default descriptions.
WERKZEUG_ERRORS: dict[int, tuple[str, str]] = {
    400: ("Bad Request", "The browser (or proxy) sent a request that this server could not understand."),
    401: (
        "Unauthorized",
        (
            "The server could not verify that you are authorized to access the URL requested. You either"
            " supplied the wrong credentials (e.g. a bad password), or your browser doesn't understand how"
            " to supply the credentials required."
        ),
    ),
    403: (
        "Forbidden",
        (
            "You don't have the permission to access the requested resource. It is either read-protected"
            " or not readable by the server."
        ),
    ),
    404: (
        "Not Found",
        (
            "The requested URL was not found on the server. If you entered the URL manually please check"
            " your spelling and try again."
        ),
    ),
    405: ("Method Not Allowed", "The method is not allowed for the requested URL."),
    413: ("Request Entity Too Large", "The data value transmitted exceeds the capacity limit."),
    415: ("Unsupported Media Type", "The server does not support the media type transmitted in the request."),
    422: (
        "Unprocessable Entity",
        "The request was well-formed but was unable to be followed due to semantic errors.",
    ),
    429: ("Too Many Requests", "This user has exceeded an allotted request count. Try again later."),
    500: (
        "Internal Server Error",
        (
            "The server encountered an internal error and was unable to complete your request. Either the"
            " server is overloaded or there is an error in the application."
        ),
    ),
    501: ("Not Implemented", "The server does not support the action requested by the browser."),
    502: ("Bad Gateway", "The proxy server received an invalid response from an upstream server."),
    503: (
        "Service Unavailable",
        (
            "The server is temporarily unable to service your request due to maintenance downtime or"
            " capacity problems. Please try again later."
        ),
    ),
    504: ("Gateway Timeout", "The connection to an upstream server timed out."),
}


class WerkzeugHTTPError(Exception):
    """Raise to answer with Werkzeug's HTML error page, like ``abort(code)``."""

    def __init__(
        self,
        code: int,
        description: str | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(code, description)
        self.code = code
        self.description = description
        self.headers = dict(headers or {})


def _escape(text: str) -> str:
    """``markupsafe.escape``: Werkzeug's escaping of names and descriptions."""
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&#34;").replace("'", "&#39;")
    )


def werkzeug_error_body(code: int, description: str | None = None) -> str:
    """Byte-for-byte ``werkzeug.exceptions.HTTPException.get_body()``."""
    name, default_description = WERKZEUG_ERRORS.get(code, (HTTPStatus(code).phrase, ""))
    text = _escape(default_description if description is None else description).replace("\n", "<br>")
    return (
        "<!doctype html>\n"
        "<html lang=en>\n"
        f"<title>{code} {_escape(name)}</title>\n"
        f"<h1>{_escape(name)}</h1>\n"
        f"<p>{text}</p>\n"
    )


def werkzeug_error_response(
    code: int,
    description: str | None = None,
    headers: Mapping[str, str] | None = None,
) -> Response:
    """Werkzeug's HTML error response (``Content-Type: text/html; charset=utf-8``)."""
    return Response(
        werkzeug_error_body(code, description),
        status_code=code,
        headers=dict(headers or {}),
        media_type="text/html",
    )


def jsonify(obj: Any, status_code: int = 200, headers: Mapping[str, str] | None = None) -> Response:
    """``flask.jsonify(obj), status_code`` for plain JSON types."""
    body = json.dumps(obj, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"
    return Response(body, status_code=status_code, headers=dict(headers or {}), media_type="application/json")


def query_arg(request: Request, name: str, default: Any = None) -> Any:
    """``request.args.get(name, default)``."""
    values = request.query_params.getlist(name)
    return values[0] if values else default


def header(headers: Headers, name: str, default: str = "") -> str:
    """``request.headers.get(name, default)`` as seen through gunicorn's WSGI environ."""
    values = headers.getlist(name)
    return ",".join(values) if values else default


def is_json_mimetype(headers: Headers) -> bool:
    """``Request.is_json``; gunicorn keeps the last ``Content-Type`` header."""
    values = headers.getlist("content-type")
    mimetype = values[-1].split(";", 1)[0].strip().lower() if values else ""
    return mimetype == "application/json" or (mimetype.startswith("application/") and mimetype.endswith("+json"))


async def get_json(request: Request) -> Any:
    """``request.get_json()`` with Flask's non-debug error behaviour."""
    if not is_json_mimetype(request.headers):
        raise WerkzeugHTTPError(415, UNSUPPORTED_JSON_MEDIA_TYPE)
    body = await request.body()
    try:
        return json.loads(body)
    except ValueError as exc:
        raise WerkzeugHTTPError(400) from exc
