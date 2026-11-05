"""Tests for the Indexer service."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from app.config import MeiliSearchConfig
from app.services.indexer import Indexer
from app.services.meilisearch_client import MeiliSearchService


@pytest.fixture()
def mock_ms_service() -> MeiliSearchService:
    """Create a MeiliSearchService with mocked client."""
    with patch("app.services.meilisearch_client.meilisearch.Client") as mock_cls:
        mock_client = MagicMock()

        mock_task = MagicMock()
        mock_task.task_uid = 1
        mock_task_result = MagicMock()
        mock_task_result.status = "succeeded"
        mock_client.wait_for_task.return_value = mock_task_result

        mock_index = MagicMock()
        mock_index.add_documents.return_value = mock_task
        mock_index.delete_document.return_value = mock_task
        mock_index.get_document.return_value = {"id": "doc-1"}
        mock_client.index.return_value = mock_index

        mock_client.create_index.return_value = mock_task
        mock_client.delete_index.return_value = mock_task
        mock_client.get_index.side_effect = None
        mock_client.health.return_value = {"status": "available"}

        mock_cls.return_value = mock_client
        service = MeiliSearchService(
            MeiliSearchConfig(
                documents_index="test-docs",
                files_index="test-files",
            )
        )
        yield service


@pytest.fixture()
def indexer(mock_ms_service: MeiliSearchService) -> Indexer:
    return Indexer(mock_ms_service)


class TestIndexer:
    """Tests for Indexer logic."""

    def test_index_document_success(self, indexer: Indexer):
        result = indexer.index_document(
            {
                "id": "doc-1",
                "title": "Test Doc",
                "content": "Hello world",
                "owner_id": "user-1",
            }
        )
        assert result["status"] == "indexed"
        assert result["type"] == "document"

    @pytest.mark.parametrize("status", [401, 403, 500])
    def test_reindex_preserves_indexes_on_partial_fetch(
        self, indexer, monkeypatch, status
    ):
        monkeypatch.setenv("FILE_REINDEX_TOKEN", "test-service-credential")
        first = requests.Response()
        first.status_code = 200
        first._content = b'{"files":[{"id":"file-1","name":"report.pdf"}]}'
        failure = requests.Response()
        failure.status_code = status
        with (
            patch.object(indexer, "_fetch_all_documents", return_value=[]),
            patch("app.services.indexer.requests.get", side_effect=[first, failure]),
            patch.object(indexer.search, "reindex") as rebuild,
        ):
            with pytest.raises(requests.HTTPError):
                indexer.reindex()
            rebuild.assert_not_called()

    def test_reindex_preserves_indexes_on_document_failure(self, indexer):
        with (
            patch("app.services.indexer.requests.get", side_effect=requests.Timeout),
            patch.object(indexer.search, "reindex") as rebuild,
        ):
            with pytest.raises(requests.Timeout):
                indexer.reindex()
            rebuild.assert_not_called()

    @pytest.mark.parametrize("payload", [{}, {"files": None}, {"files": "invalid"}])
    def test_reindex_rejects_invalid_snapshots(self, indexer, monkeypatch, payload):
        monkeypatch.setenv("FILE_REINDEX_TOKEN", "test-service-credential")
        response = MagicMock(status_code=200)
        response.json.return_value = payload
        with (
            patch.object(indexer, "_fetch_all_documents", return_value=[]),
            patch("app.services.indexer.requests.get", return_value=response),
            patch.object(indexer.search, "reindex") as rebuild,
        ):
            with pytest.raises(ValueError):
                indexer.reindex()
            rebuild.assert_not_called()

    def test_service_reindex_succeeds_without_user_header(self, indexer, monkeypatch):
        monkeypatch.setenv("FILE_REINDEX_TOKEN", "test-service-credential")
        first = MagicMock(status_code=200)
        first.json.return_value = {"files": [{"id": "file-1", "name": "report.pdf"}]}
        last = MagicMock(status_code=200)
        last.json.return_value = {"files": []}
        with (
            patch.object(indexer, "_fetch_all_documents", return_value=[]),
            patch(
                "app.services.indexer.requests.get", side_effect=[first, last]
            ) as get,
            patch.object(indexer.search, "reindex") as rebuild,
        ):
            indexer.reindex()
            assert get.call_args_list[0].args[0].endswith("/internal/files/reindex")
            assert get.call_args_list[0].kwargs["headers"] == {
                "Authorization": "Bearer test-service-credential"
            }
            assert rebuild.call_args.kwargs["files"][0]["id"] == "file-1"

    def test_missing_service_key_never_rebuilds(self, indexer, monkeypatch):
        monkeypatch.delenv("FILE_REINDEX_TOKEN", raising=False)
        with (
            patch.object(indexer, "_fetch_all_documents", return_value=[]),
            patch.object(indexer.search, "reindex") as rebuild,
        ):
            with pytest.raises(ValueError, match="credential"):
                indexer.reindex()
            rebuild.assert_not_called()

    def test_index_document_missing_id(self, indexer: Indexer):
        with pytest.raises(ValueError, match="id"):
            indexer.index_document({"title": "No ID"})

    def test_index_document_missing_title(self, indexer: Indexer):
        with pytest.raises(ValueError, match="title"):
            indexer.index_document({"id": "doc-1"})

    def test_index_file_success(self, indexer: Indexer):
        result = indexer.index_file(
            {
                "id": "file-1",
                "name": "report.pdf",
                "mime_type": "application/pdf",
                "owner_id": "user-1",
            }
        )
        assert result["status"] == "indexed"
        assert result["type"] == "file"

    def test_index_file_missing_id(self, indexer: Indexer):
        with pytest.raises(ValueError, match="id"):
            indexer.index_file({"name": "report.pdf"})

    def test_index_file_missing_name(self, indexer: Indexer):
        with pytest.raises(ValueError, match="name"):
            indexer.index_file({"id": "file-1"})

    def test_remove_document(self, indexer: Indexer):
        result = indexer.remove("document", "doc-1")
        assert result["status"] == "deleted"
        assert result["type"] == "document"

    def test_remove_invalid_type(self, indexer: Indexer):
        with pytest.raises(ValueError, match="Invalid type"):
            indexer.remove("invalid", "id-1")

    def test_process_event_index_document(self, indexer: Indexer):
        result = indexer.process_event(
            {
                "action": "index_document",
                "data": {"id": "doc-1", "title": "Test"},
            }
        )
        assert result is not None
        assert result["status"] == "indexed"

    def test_process_event_index_file(self, indexer: Indexer):
        result = indexer.process_event(
            {
                "action": "index_file",
                "data": {"id": "file-1", "name": "test.pdf"},
            }
        )
        assert result is not None
        assert result["status"] == "indexed"

    def test_process_event_delete(self, indexer: Indexer):
        result = indexer.process_event(
            {
                "action": "delete",
                "data": {"id": "doc-1", "type": "document"},
            }
        )
        assert result is not None
        assert result["status"] == "deleted"

    def test_process_event_unknown_action(self, indexer: Indexer):
        result = indexer.process_event({"action": "unknown", "data": {}})
        assert result is None
