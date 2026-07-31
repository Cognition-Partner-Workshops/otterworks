"""Unit tests for the OpenSearch backend adapter.

Mirrors the behavioural contract exercised for the MeiliSearch adapter, using a
mocked opensearch-py client so no live cluster is required.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.config import OpenSearchConfig
from app.services.opensearch_client import OpenSearchService


def _hit(source: dict, score: float = 1.0, highlight: dict | None = None) -> dict:
    hit = {"_id": source.get("id", ""), "_score": score, "_source": source}
    if highlight:
        hit["highlight"] = highlight
    return hit


@pytest.fixture()
def mock_client() -> MagicMock:
    client = MagicMock()
    client.indices.exists.return_value = True
    client.search.return_value = {"hits": {"total": {"value": 0}, "hits": []}}
    return client


@pytest.fixture()
def service(mock_client: MagicMock) -> OpenSearchService:
    with patch("app.services.opensearch_client.OpenSearch", return_value=mock_client):
        svc = OpenSearchService(
            OpenSearchConfig(
                endpoint="http://localhost:9200",
                use_aws_auth=False,
                service="es",
                documents_index="test-docs",
                files_index="test-files",
            )
        )
        svc.client = mock_client
        return svc


class TestLifecycle:
    def test_ping_true_when_reachable(self, service: OpenSearchService, mock_client: MagicMock) -> None:
        assert service.ping() is True

    def test_ping_false_on_error(self, service: OpenSearchService, mock_client: MagicMock) -> None:
        mock_client.indices.exists.side_effect = Exception("down")
        assert service.ping() is False

    def test_ensure_indices_creates_when_missing(self, service: OpenSearchService, mock_client: MagicMock) -> None:
        mock_client.indices.exists.return_value = False
        service.ensure_indices()
        created = {c.kwargs["index"] for c in mock_client.indices.create.call_args_list}
        assert created == {"test-docs", "test-files"}


class TestIndexing:
    def test_index_document_sets_type_and_id_and_refresh(self, service: OpenSearchService, mock_client: MagicMock) -> None:
        service.index_document({"id": "doc-1", "title": "Hello"})
        _, kwargs = mock_client.index.call_args
        assert kwargs["index"] == "test-docs"
        assert kwargs["id"] == "doc-1"
        assert kwargs["body"]["type"] == "document"
        assert kwargs["refresh"] == "wait_for"  # non-serverless

    def test_index_file_sets_type_file(self, service: OpenSearchService, mock_client: MagicMock) -> None:
        service.index_file({"id": "file-1", "name": "a.txt"})
        _, kwargs = mock_client.index.call_args
        assert kwargs["index"] == "test-files"
        assert kwargs["body"]["type"] == "file"

    def test_serverless_omits_refresh(self, mock_client: MagicMock) -> None:
        with patch("app.services.opensearch_client.OpenSearch", return_value=mock_client):
            svc = OpenSearchService(
                OpenSearchConfig(endpoint="https://x.aoss.amazonaws.com", use_aws_auth=False, service="aoss")
            )
            svc.client = mock_client
        svc.index_document({"id": "d", "title": "t"})
        _, kwargs = mock_client.index.call_args
        assert "refresh" not in kwargs

    def test_delete_returns_false_when_absent(self, service: OpenSearchService, mock_client: MagicMock) -> None:
        mock_client.search.return_value = {"hits": {"total": {"value": 0}, "hits": []}}
        assert service.delete_document("document", "missing") is False
        mock_client.delete.assert_not_called()

    def test_delete_returns_true_when_present(self, service: OpenSearchService, mock_client: MagicMock) -> None:
        mock_client.search.return_value = {"hits": {"total": {"value": 1}, "hits": []}}
        assert service.delete_document("document", "doc-1") is True
        mock_client.delete.assert_called_once()


class TestSearch:
    def test_search_parses_document_hit(self, service: OpenSearchService, mock_client: MagicMock) -> None:
        mock_client.search.return_value = {
            "hits": {
                "total": {"value": 1},
                "hits": [
                    _hit(
                        {"id": "doc-1", "title": "Quarterly", "content": "revenue up", "owner_id": "u1", "tags": ["fin"], "type": "document"},
                        score=2.5,
                        highlight={"content": ["revenue <em>up</em>"]},
                    )
                ],
            }
        }
        resp = service.search("revenue", doc_type="document", owner_id="u1", page=1, page_size=10)
        assert resp.total == 1
        hit = resp.results[0]
        assert hit.id == "doc-1"
        assert hit.title == "Quarterly"
        assert hit.type == "document"
        assert hit.content_snippet == "revenue <em>up</em>"
        assert hit.highlights == {"content": ["revenue <em>up</em>"]}
        assert hit.score == 2.5

    def test_search_empty_query_uses_match_all(self, service: OpenSearchService, mock_client: MagicMock) -> None:
        service.advanced_search(query=None, page=1, page_size=5)
        body = mock_client.search.call_args.kwargs["body"]
        assert body["query"]["bool"]["must"][0] == {"match_all": {}}

    def test_advanced_search_builds_filters(self, service: OpenSearchService, mock_client: MagicMock) -> None:
        service.advanced_search(
            query="x", doc_type="document", owner_id="u1", tags=["a", "b"],
            date_from="2024-01-01", date_to="2024-12-31",
        )
        body = mock_client.search.call_args.kwargs["body"]
        filters = body["query"]["bool"]["filter"]
        assert {"term": {"type": "document"}} in filters
        assert {"term": {"owner_id": "u1"}} in filters
        assert {"terms": {"tags": ["a", "b"]}} in filters
        assert {"range": {"created_at": {"gte": "2024-01-01", "lte": "2024-12-31"}}} in filters

    def test_suggest_uses_bool_prefix_and_returns_titles(self, service: OpenSearchService, mock_client: MagicMock) -> None:
        def _search(index: str, body: dict):
            if index == "test-docs":
                return {"hits": {"total": {"value": 1}, "hits": [{"_source": {"title": "Unique Report"}}]}}
            return {"hits": {"total": {"value": 0}, "hits": []}}

        mock_client.search.side_effect = _search
        out = service.suggest("uni")
        assert out == ["Unique Report"]
        first_body = mock_client.search.call_args_list[0].kwargs["body"]
        assert first_body["query"]["multi_match"]["type"] == "bool_prefix"


class TestReindex:
    def test_reindex_recreates_and_reports_counts(self, service: OpenSearchService, mock_client: MagicMock) -> None:
        mock_client.indices.exists.return_value = False
        with patch("app.services.opensearch_client.bulk") as mock_bulk:
            result = service.reindex(documents=[{"id": "d1", "title": "t"}], files=[])
        assert result["status"] == "reindexed"
        assert result["indices"] == ["test-docs", "test-files"]
        assert result["indexed_counts"] == {"documents": 1, "files": 0}
        mock_bulk.assert_called_once()
