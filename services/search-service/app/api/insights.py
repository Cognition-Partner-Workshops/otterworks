"""Account search insight HTTP contract."""

import re
from datetime import date
from uuid import UUID

from flask import Blueprint, current_app, g, jsonify, request

from app.services.insights import InsightsTimeout, InsightsUnavailable

insights_bp = Blueprint("insights", __name__)


def error(code, message, status):
    return jsonify(error=code, message=message), status


@insights_bp.get("/accounts/<account_id>/top")
def top_items(account_id):
    try:
        if len(account_id) > 36:
            raise ValueError()
        account_id = str(UUID(account_id))
    except ValueError:
        return error("invalid_account_id", "account_id must be a UUID", 400)
    item_type = request.args.get("item_type")
    if item_type is not None and item_type not in ("term", "document"):
        return error("invalid_item_type", "item_type must be term or document", 400)
    window = request.args.get("window_end_date")
    if window is not None:
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", window):
                raise ValueError()
            date.fromisoformat(window)
        except ValueError:
            return error("invalid_window_end_date", "window_end_date must be YYYY-MM-DD", 400)
    user = g.user_id
    if user and not g.service_authenticated:
        try:
            same_account = UUID(user) == UUID(account_id)
        except ValueError:
            same_account = False
        if not same_account:
            return error("forbidden", "Cannot read another account", 403)
    try:
        window, rows = current_app.config["INSIGHTS_CLIENT"].fetch(account_id, item_type, window)
    except InsightsTimeout:
        return error("insights_timeout", "Search insights query timed out", 504)
    except InsightsUnavailable:
        response, status = error("insights_unavailable", "Search insights are temporarily unavailable", 503)
        response.headers["Retry-After"] = "5"
        return response, status
    return jsonify(account_id=account_id, window_end_date=window, window_days=28, item_type=item_type, rows=rows)
