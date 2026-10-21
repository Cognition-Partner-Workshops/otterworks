"""Indexing API endpoints for documents and files."""

from __future__ import annotations

import asyncio

import structlog
from fastapi import APIRouter, Request
from starlette.responses import Response

from app.api.health import INDEX_COUNT
from app.flask_compat import get_json, jsonify
from app.services.indexer import Indexer
from app.services.meilisearch_client import MeiliSearchService

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/search", tags=["index"])


def _get_indexer(request: Request) -> Indexer:
    """Get an Indexer instance from the app state."""
    search_service: MeiliSearchService = request.app.state.search_service
    return Indexer(search_service)


@router.post("/index/document")
async def index_document(request: Request) -> Response:
    """Index a document (called by document-service or SQS)."""
    data = await get_json(request)
    if not data:
        return jsonify({"error": "Request body is required"}, 400)

    try:
        indexer = _get_indexer(request)
        result = await asyncio.to_thread(indexer.index_document, data)
        INDEX_COUNT.labels(operation="index", type="document").inc()
        logger.info("api_document_indexed", document_id=data.get("id"))
        return jsonify(result, 201)
    except ValueError as e:
        return jsonify({"error": str(e)}, 400)
    except Exception:
        logger.exception("api_index_document_failed")
        return jsonify({"error": "Failed to index document"}, 500)


@router.post("/index/file")
async def index_file(request: Request) -> Response:
    """Index a file (called by file-service or SQS)."""
    data = await get_json(request)
    if not data:
        return jsonify({"error": "Request body is required"}, 400)

    try:
        indexer = _get_indexer(request)
        result = await asyncio.to_thread(indexer.index_file, data)
        INDEX_COUNT.labels(operation="index", type="file").inc()
        logger.info("api_file_indexed", file_id=data.get("id"))
        return jsonify(result, 201)
    except ValueError as e:
        return jsonify({"error": str(e)}, 400)
    except Exception:
        logger.exception("api_index_file_failed")
        return jsonify({"error": "Failed to index file"}, 500)


@router.delete("/index/{doc_type}/{doc_id}")
async def remove_from_index(request: Request, doc_type: str, doc_id: str) -> Response:
    """Remove a document or file from the search index."""
    try:
        indexer = _get_indexer(request)
        result = await asyncio.to_thread(indexer.remove, doc_type, doc_id)
        if result["status"] == "not_found":
            return jsonify(result, 404)
        INDEX_COUNT.labels(operation="delete", type=doc_type).inc()
        logger.info("api_document_removed", doc_type=doc_type, doc_id=doc_id)
        return jsonify(result, 200)
    except ValueError as e:
        return jsonify({"error": str(e)}, 400)
    except Exception:
        logger.exception("api_remove_from_index_failed")
        return jsonify({"error": "Failed to remove from index"}, 500)


@router.post("/reindex")
async def reindex(request: Request) -> Response:
    """Reindex all data (admin operation)."""
    try:
        indexer = _get_indexer(request)
        result = await asyncio.to_thread(indexer.reindex)
        logger.info("api_reindex_triggered")
        return jsonify(result, 200)
    except Exception:
        logger.exception("api_reindex_failed")
        return jsonify({"error": "Failed to reindex"}, 500)
