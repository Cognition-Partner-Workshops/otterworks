"""Per-account search insights endpoints."""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

import structlog
from flask import Blueprint, current_app, jsonify, request

from app.services.insights_repository import DocSearchInsightsRepository
from app.services.snowflake_pool import BackendUnavailable, PoolTimeout, QueryTimeout

logger = structlog.get_logger()

insights_bp = Blueprint("insights", __name__)


def _repository() -> DocSearchInsightsRepository:
    repository = current_app.config.get("INSIGHTS_REPOSITORY")
    if repository is None:
        repository = DocSearchInsightsRepository.from_config(current_app.config["APP_CONFIG"].snowflake)
        current_app.config["INSIGHTS_REPOSITORY"] = repository
    return repository


def _format_timestamp(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    elif isinstance(value, datetime):
        timestamp = value
    else:
        return str(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc).isoformat(timespec="auto").replace("+00:00", "Z")


@insights_bp.route("/accounts/<account_id>/top", methods=["GET"])
def top_items(account_id: str):
    try:
        account_uuid = UUID(account_id)
    except (ValueError, AttributeError):
        return jsonify({"error": "invalid account_id"}), 400

    item_type = request.args.get("type")
    if item_type not in {"term", "document"}:
        return jsonify({"error": "type must be term or document"}), 400

    limit_value = request.args.get("limit", "10")
    try:
        if not limit_value or str(int(limit_value)) != limit_value:
            raise ValueError
        limit = int(limit_value)
    except (ValueError, TypeError):
        return jsonify({"error": "limit must be an integer from 1 to 10"}), 400
    if not 1 <= limit <= 10:
        return jsonify({"error": "limit must be an integer from 1 to 10"}), 400

    window_value = request.args.get("window_end_date")
    window_end_date = None
    if window_value is not None:
        try:
            window_end_date = date.fromisoformat(window_value)
            if window_end_date.isoformat() != window_value:
                raise ValueError
        except ValueError:
            return jsonify({"error": "window_end_date must be YYYY-MM-DD"}), 400

    auth_config = current_app.config["APP_CONFIG"].auth
    if auth_config.require_auth:
        token = request.headers.get("Authorization", "")
        bearer = token[7:].strip() if token.lower().startswith("bearer ") else ""
        service_token_valid = bool(auth_config.service_token and bearer == auth_config.service_token)
        user_id = request.headers.get("X-User-ID", "").strip()
        user_matches = False
        try:
            user_matches = UUID(user_id) == account_uuid
        except (ValueError, AttributeError):
            pass
        # Search-service cannot currently resolve an admin role from user_roles.
        if not service_token_valid and not user_matches:
            return jsonify({"error": "forbidden"}), 403

    snowflake_config = current_app.config["APP_CONFIG"].snowflake
    if not snowflake_config.account:
        return jsonify({"error": "insights backend not configured"}), 503

    try:
        rows = _repository().top_items(str(account_uuid), window_end_date)
    except (PoolTimeout, BackendUnavailable):
        logger.exception("insights_backend_unavailable", account_id=str(account_uuid))
        return jsonify({"error": "insights backend unavailable"}), 503
    except QueryTimeout:
        logger.exception("insights_query_timed_out", account_id=str(account_uuid))
        return jsonify({"error": "insights query timed out"}), 504
    except Exception:
        logger.exception("insights_query_failed", account_id=str(account_uuid))
        return jsonify({"error": "insights query failed"}), 500

    if rows is None:
        return jsonify({"error": "no search window for this account"}), 404

    selected = sorted(
        (row for row in rows if row["item_type"] == item_type and int(row["rank"]) <= limit),
        key=lambda row: int(row["rank"]),
    )
    items = []
    for row in selected:
        item = {
            "rank": int(row["rank"]),
            "search_count": int(row["search_count"]),
            "zero_result_count": (
                None if row.get("zero_result_count") is None else int(row["zero_result_count"])
            ),
            "last_searched_at": _format_timestamp(row.get("last_searched_at")),
        }
        if item_type == "term":
            item["term"] = row.get("term")
        else:
            item["document_id"] = row.get("document_id")
            item["document_title"] = row.get("document_title")
        items.append(item)

    first = rows[0]
    result_window = first["window_end_date"]
    if isinstance(result_window, (date, datetime)):
        result_window = result_window.isoformat()[:10]
    return jsonify(
        {
            "window_end_date": result_window,
            "window_days": int(first["window_days"]),
            "account_id": str(first["account_id"]),
            "items": items,
        }
    ), 200
