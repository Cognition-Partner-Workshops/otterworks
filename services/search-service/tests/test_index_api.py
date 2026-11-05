"""Tests for indexing API endpoints."""

from __future__ import annotations

import pytest

from tests.conftest import SERVICE_HEADERS


class TestIndexDocumentEndpoint:
    """Tests for POST /api/v1/search/index/document."""

    def test_index_document_success(self, client, mock_meilisearch_client):
        """Index a valid document returns 201."""
        response = client.post(
            "/api/v1/search/index/document",
            headers=SERVICE_HEADERS,
            json={
                "id": "doc-123",
                "title": "My Document",
                "content": "Document body text",
                "owner_id": "user-1",
                "tags": ["work"],
            },
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["status"] == "indexed"
        assert data["id"] == "doc-123"
        assert data["type"] == "document"

    def test_index_document_missing_body(self, client):
        """Index with empty body returns 400."""
        response = client.post(
            "/api/v1/search/index/document",
            headers=SERVICE_HEADERS,
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_index_document_missing_id(self, client, mock_meilisearch_client):
        """Index document without id returns 400."""
        response = client.post(
            "/api/v1/search/index/document",
            headers=SERVICE_HEADERS,
            json={"title": "No ID Doc"},
        )
        assert response.status_code == 400

    def test_index_document_missing_title(self, client, mock_meilisearch_client):
        """Index document without title returns 400."""
        response = client.post(
            "/api/v1/search/index/document",
            headers=SERVICE_HEADERS,
            json={"id": "doc-no-title"},
        )
        assert response.status_code == 400


class TestIndexFileEndpoint:
    """Tests for POST /api/v1/search/index/file."""

    def test_index_file_success(self, client, mock_meilisearch_client):
        """Index a valid file returns 201."""
        response = client.post(
            "/api/v1/search/index/file",
            headers=SERVICE_HEADERS,
            json={
                "id": "file-123",
                "name": "report.pdf",
                "mime_type": "application/pdf",
                "owner_id": "user-1",
                "folder_id": "folder-1",
                "tags": ["report"],
                "size": 1024,
            },
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["status"] == "indexed"
        assert data["id"] == "file-123"
        assert data["type"] == "file"

    def test_index_file_missing_name(self, client, mock_meilisearch_client):
        """Index file without name returns 400."""
        response = client.post(
            "/api/v1/search/index/file",
            headers=SERVICE_HEADERS,
            json={"id": "file-no-name"},
        )
        assert response.status_code == 400


class TestDeleteFromIndexEndpoint:
    """Tests for DELETE /api/v1/search/index/{type}/{id}."""

    def test_delete_document(self, client, mock_meilisearch_client):
        """Delete a document from index returns 200."""
        mock_index = mock_meilisearch_client.index.return_value
        mock_index.get_document.return_value = {"id": "doc-123"}
        response = client.delete("/api/v1/search/index/document/doc-123", headers=SERVICE_HEADERS)
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "deleted"

    def test_delete_invalid_type(self, client, mock_meilisearch_client):
        """Delete with invalid type returns 400."""
        response = client.delete("/api/v1/search/index/invalid/doc-123", headers=SERVICE_HEADERS)
        assert response.status_code == 400


class TestReindexEndpoint:
    """Tests for POST /api/v1/search/reindex."""

    def test_reindex_success(self, client, mock_meilisearch_client):
        """Reindex returns 200."""
        response = client.post("/api/v1/search/reindex", headers=SERVICE_HEADERS)
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "reindexed"


INTERNAL_ROUTES = [
    ("post", "/api/v1/search/reindex"),
    ("post", "/api/v1/search/index/document"),
    ("post", "/api/v1/search/index/file"),
    ("delete", "/api/v1/search/index/document/doc-1"),
]


@pytest.mark.parametrize(("method", "path"), INTERNAL_ROUTES)
def test_internal_routes_reject_user_identity(client, method, path):
    response = getattr(client, method)(
        path, json={"id": "x", "title": "t"}, headers={"X-User-ID": "user-1"}
    )
    assert response.status_code == 403


@pytest.mark.parametrize(("method", "path"), INTERNAL_ROUTES)
def test_internal_routes_reject_wrong_token(client, method, path):
    response = getattr(client, method)(
        path, json={"id": "x", "title": "t"}, headers={"Authorization": "Bearer nope"}
    )
    assert response.status_code == 403


def test_reindex_accepts_service_token(client, mock_meilisearch_client):
    response = client.post("/api/v1/search/reindex", headers=SERVICE_HEADERS)
    assert response.status_code == 200
