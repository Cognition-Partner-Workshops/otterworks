import re
from datetime import date
from uuid import UUID

from flask import request
from werkzeug.exceptions import BadRequest

from .errors import InvalidRequest


def required(values, field):
    if field not in values or values[field] is None or values[field] == "":
        raise InvalidRequest(field, "is required")
    return values[field]


def uuid_value(value, field):
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise InvalidRequest(field, "must be a UUID") from None


def date_value(value, field):
    try:
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        raise InvalidRequest(field, "must be YYYY-MM-DD") from None


def json_body():
    if not request.is_json:
        raise InvalidRequest("body", "must be a JSON object")
    try:
        payload = request.get_json()
    except BadRequest:
        raise InvalidRequest("body", "must be valid JSON") from None
    if not isinstance(payload, dict):
        raise InvalidRequest("body", "must be a JSON object")
    return payload
