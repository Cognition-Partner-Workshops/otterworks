from flask import request
from itsdangerous import BadData, URLSafeSerializer

from .errors import InvalidRequest

_cursor = URLSafeSerializer("billing-pagination-v1", salt="offset")


def paginate(items, args=None):
    """Slice entrypoint order; cursors are scoped to the path and query filters."""
    args = request.args if args is None else args
    raw_limit = args.get("limit", "50")
    try:
        if not str(raw_limit).isascii() or not str(raw_limit).isdecimal():
            raise ValueError
        limit = int(raw_limit)
        if not 1 <= limit <= 200:
            raise ValueError
    except (ValueError, TypeError):
        raise InvalidRequest("limit", "must be an integer between 1 and 200") from None
    scope = [request.path, sorted((key, value) for key, value in args.items() if key not in ("cursor", "limit"))]
    offset = 0
    if "cursor" in args:
        try:
            payload = _cursor.loads(args["cursor"])
            offset = payload["offset"]
            if payload["scope"] != [scope[0], [list(pair) for pair in scope[1]]] or type(offset) is not int or offset < 0:
                raise ValueError
        except (BadData, KeyError, ValueError, TypeError):
            raise InvalidRequest("cursor", "is invalid") from None
    page = items[offset:offset + limit]
    next_cursor = None
    if offset + limit < len(items):
        next_cursor = _cursor.dumps({"offset": offset + limit, "scope": scope})
    return {"data": page, "pagination": {"limit": limit, "next_cursor": next_cursor}}
