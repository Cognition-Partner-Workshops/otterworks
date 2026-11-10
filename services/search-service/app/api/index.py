"""Indexing API endpoints for documents and files."""

from __future__ import annotations

import structlog
from flask import Blueprint, jsonify, request

from app.api.health import INDEX_COUNT
from app.middleware.auth import Caller, get_caller
from app.services.indexer import Indexer
from app.services.meilisearch_client import MeiliSearchService

logger = structlog.get_logger()

index_bp = Blueprint("index", __name__)


def _get_indexer() -> Indexer:
    """Get an Indexer instance from the current app config."""
    from flask import current_app

    search_service: MeiliSearchService = current_app.config["SEARCH_SERVICE"]
    return Indexer(search_service)


def _forbidden(message: str) -> tuple:
    return jsonify({"error": message}), 403


def _authorize_index_write(indexer: Indexer, caller: Caller, doc_type: str, data: dict) -> tuple | None:
    """Pin a user's index write to their own space; trusted callers may set any owner."""
    if caller.is_trusted:
        return None
    body_owner = str(data.get("owner_id") or "").strip()
    if body_owner and body_owner != caller.user_id:
        logger.warning("index_owner_mismatch", doc_type=doc_type, caller=caller.user_id)
        return _forbidden("owner_id must match the authenticated caller")
    if data.get("id"):
        existing_owner = indexer.owner_of(doc_type, str(data["id"]))
        if existing_owner is not None and existing_owner != caller.user_id:
            logger.warning("index_overwrite_denied", doc_type=doc_type, caller=caller.user_id)
            return _forbidden("cannot overwrite another user's index entry")
    data["owner_id"] = caller.user_id
    return None


@index_bp.route("/index/document", methods=["POST"])
def index_document() -> tuple:
    """Index a document (called by document-service or SQS)."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    try:
        indexer = _get_indexer()
        denied = _authorize_index_write(indexer, get_caller(), "document", data)
        if denied:
            return denied
        result = indexer.index_document(data)
        INDEX_COUNT.labels(operation="index", type="document").inc()
        logger.info("api_document_indexed", document_id=data.get("id"))
        return jsonify(result), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        logger.exception("api_index_document_failed")
        return jsonify({"error": "Failed to index document"}), 500


@index_bp.route("/index/file", methods=["POST"])
def index_file() -> tuple:
    """Index a file (called by file-service or SQS)."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    try:
        indexer = _get_indexer()
        denied = _authorize_index_write(indexer, get_caller(), "file", data)
        if denied:
            return denied
        result = indexer.index_file(data)
        INDEX_COUNT.labels(operation="index", type="file").inc()
        logger.info("api_file_indexed", file_id=data.get("id"))
        return jsonify(result), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        logger.exception("api_index_file_failed")
        return jsonify({"error": "Failed to index file"}), 500


@index_bp.route("/index/<doc_type>/<doc_id>", methods=["DELETE"])
def remove_from_index(doc_type: str, doc_id: str) -> tuple:
    """Remove a document or file from the search index."""
    try:
        indexer = _get_indexer()
        caller = get_caller()
        if not caller.is_trusted and indexer.owner_of(doc_type, doc_id) != caller.user_id:
            return jsonify({"status": "not_found", "id": doc_id, "type": doc_type}), 404
        result = indexer.remove(doc_type, doc_id)
        if result["status"] == "not_found":
            return jsonify(result), 404
        INDEX_COUNT.labels(operation="delete", type=doc_type).inc()
        logger.info("api_document_removed", doc_type=doc_type, doc_id=doc_id)
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        logger.exception("api_remove_from_index_failed")
        return jsonify({"error": "Failed to remove from index"}), 500


@index_bp.route("/reindex", methods=["POST"])
def reindex() -> tuple:
    """Reindex all data (admin operation)."""
    if not get_caller().is_trusted:
        return _forbidden("admin role required")
    try:
        indexer = _get_indexer()
        result = indexer.reindex()
        logger.info("api_reindex_triggered")
        return jsonify(result), 200
    except Exception:
        logger.exception("api_reindex_failed")
        return jsonify({"error": "Failed to reindex"}), 500
