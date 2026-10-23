"""QA test pyramid (base layer) for search-service.

Failures are labelled in the test docstrings:
- [PLANTED] deliberate lab bug from scripts/bug-catalog.yaml -> marked xfail(strict).
- [REAL]    genuine defect found during QA -> left failing on purpose.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.sqs_consumer import SQSConsumer

MDB_KEYEXIST = RuntimeError(
    "MeiliSearch task 7 failed: {'message': 'internal: MDB_KEYEXIST: Key/data pair already exists.'}"
)


def _search_calls(mock_meilisearch_client: MagicMock) -> list[tuple[str, dict]]:
    index = mock_meilisearch_client.index.return_value
    return [(c.args[0], c.args[1] if len(c.args) > 1 else c.kwargs) for c in index.search.call_args_list]


def _hit(**fields):
    return {"hits": [fields], "estimatedTotalHits": 1}


# --------------------------------------------------------------------------- full-text query


class TestFullTextQuery:
    def test_query_is_passed_through_to_meilisearch(self, client, mock_meilisearch_client):
        response = client.get("/api/v1/search/?q=quarterly+report")
        assert response.status_code == 200
        assert any(q == "quarterly report" for q, _ in _search_calls(mock_meilisearch_client))

    def test_query_is_scoped_to_gateway_user(self, client, mock_meilisearch_client):
        client.get("/api/v1/search/?q=roadmap", headers={"X-User-ID": "user-42"})
        filters = [str(p.get("filter")) for _, p in _search_calls(mock_meilisearch_client)]
        assert filters and all("owner_id" in f and "user-42" in f for f in filters)

    def test_no_hits_returns_empty_result_set(self, client, mock_meilisearch_client):
        mock_meilisearch_client.index.return_value.search.return_value = {"hits": [], "estimatedTotalHits": 0}
        data = client.get("/api/v1/search/?q=zzxqv-nothing").get_json()
        assert data["results"] == []
        assert data["total"] == 0

    def test_hits_are_mapped_to_results(self, client, mock_meilisearch_client):
        mock_meilisearch_client.index.return_value.search.return_value = _hit(
            id="doc-1", title="Kestrel plan", type="document", owner_id="u1"
        )
        data = client.get("/api/v1/search/?q=kestrel&type=document").get_json()
        assert data["results"][0]["id"] == "doc-1"
        assert data["results"][0]["title"] == "Kestrel plan"
        assert data["results"][0]["type"] == "document"

    def test_blank_query_is_rejected(self, client):
        response = client.get("/api/v1/search/", query_string={"q": ""})
        assert response.status_code == 400
        assert "error" in response.get_json()


# --------------------------------------------------------------------------- filters


class TestFilters:
    @pytest.mark.parametrize("doc_type", ["document", "file"])
    def test_type_filter_is_applied(self, client, mock_meilisearch_client, doc_type):
        client.get(f"/api/v1/search/?q=x&type={doc_type}")
        filters = [str(p.get("filter")) for _, p in _search_calls(mock_meilisearch_client)]
        assert filters and all(f'type = "{doc_type}"' in f for f in filters)

    def test_no_type_has_no_type_filter(self, client, mock_meilisearch_client):
        client.get("/api/v1/search/?q=x")
        filters = [str(p.get("filter")) for _, p in _search_calls(mock_meilisearch_client)]
        assert filters and not any("type =" in f for f in filters)

    def test_advanced_search_applies_tag_filter(self, client, mock_meilisearch_client):
        response = client.post("/api/v1/search/advanced", json={"query": "x", "tags": ["finance"]})
        assert response.status_code == 200
        filters = " ".join(str(p.get("filter")) for _, p in _search_calls(mock_meilisearch_client))
        assert "tags" in filters and "finance" in filters

    def test_advanced_search_is_scoped_to_gateway_user(self, client, mock_meilisearch_client):
        client.post("/api/v1/search/advanced", json={"query": "x"}, headers={"X-User-ID": "user-42"})
        filters = [str(p.get("filter")) for _, p in _search_calls(mock_meilisearch_client)]
        assert filters and all("user-42" in f for f in filters)


# --------------------------------------------------------------------------- autocomplete


class TestSuggest:
    def test_suggest_returns_titles_and_names(self, client, mock_meilisearch_client):
        mock_meilisearch_client.index.return_value.search.side_effect = [
            _hit(title="Kestrel plan"),
            _hit(name="kestrel.png"),
        ]
        data = client.get("/api/v1/search/suggest?q=kes").get_json()
        assert data["suggestions"] == ["Kestrel plan", "kestrel.png"]

    def test_suggest_is_scoped_to_gateway_user(self, client, mock_meilisearch_client):
        """[REAL] suggest has no owner filter, leaking other users' titles/filenames."""
        client.get("/api/v1/search/suggest?q=kes", headers={"X-User-ID": "user-42"})
        filters = [str(p.get("filter")) for _, p in _search_calls(mock_meilisearch_client)]
        assert filters and all("user-42" in f for f in filters)

    @pytest.mark.xfail(
        strict=True,
        reason="[PLANTED] search-suggest-500 (scripts/bug-catalog.yaml): chaos flag "
        "chaos:search-service:suggest_500 makes /suggest return 500",
    )
    def test_suggest_with_chaos_flag_still_returns_200(self, client, mock_meilisearch_client):
        mock_meilisearch_client.index.return_value.search.return_value = _hit(title="Kestrel plan")
        with patch("app.api.search._chaos_active", return_value=True):
            response = client.get("/api/v1/search/suggest?q=kes")
        assert response.status_code == 200

    def test_suggest_without_chaos_flag_is_healthy(self, client, mock_meilisearch_client):
        mock_meilisearch_client.index.return_value.search.return_value = _hit(title="Kestrel plan")
        with patch("app.api.search._chaos_active", return_value=False):
            response = client.get("/api/v1/search/suggest?q=kes")
        assert response.status_code == 200


# --------------------------------------------------------------------------- indexing


class TestIndexing:
    def test_index_file_recovers_from_mdb_keyexist(self, meilisearch_service, mock_meilisearch_client):
        with patch.object(meilisearch_service, "_wait_and_check", side_effect=[MDB_KEYEXIST, None, None]):
            meilisearch_service.index_file({"id": "f-1", "name": "a.txt"})
        index = mock_meilisearch_client.index.return_value
        index.delete_document.assert_called_once_with("f-1")
        assert index.add_documents.call_count == 2

    def test_index_document_recovers_from_mdb_keyexist(self, meilisearch_service, mock_meilisearch_client):
        """[REAL] document re-index (update) has no MDB_KEYEXIST recovery, unlike index_file.

        Reproduced live: add -> update same id fails with 'MDB_KEYEXIST: Key/data pair already
        exists', so document_updated events never reach the index.
        """
        with patch.object(meilisearch_service, "_wait_and_check", side_effect=[MDB_KEYEXIST, None, None]):
            meilisearch_service.index_document({"id": "d-1", "title": "T"})
        assert mock_meilisearch_client.index.return_value.add_documents.call_count == 2

    def test_index_document_tags_type(self, meilisearch_service, mock_meilisearch_client):
        meilisearch_service.index_document({"id": "d-1", "title": "T"})
        doc = mock_meilisearch_client.index.return_value.add_documents.call_args.args[0][0]
        assert doc["type"] == "document"

    def test_index_owner_comes_from_gateway_user(self, client, mock_meilisearch_client):
        """[REAL] POST /index/document trusts body owner_id, so any user can plant docs in another tenant."""
        client.post(
            "/api/v1/search/index/document",
            json={"id": "d-9", "title": "Spoof", "owner_id": "victim"},
            headers={"X-User-ID": "attacker"},
        )
        add = mock_meilisearch_client.index.return_value.add_documents
        assert not add.called or add.call_args.args[0][0]["owner_id"] == "attacker"

    def test_delete_unknown_type_is_400(self, client):
        response = client.delete("/api/v1/search/index/folder/abc")
        assert response.status_code == 400


# --------------------------------------------------------------------------- event normalisation


class TestEventNormalisation:
    @pytest.mark.parametrize(
        ("event_type", "action"),
        [("document_created", "index_document"), ("document_updated", "index_document"), ("document_deleted", "delete")],
    )
    def test_document_service_events(self, event_type, action):
        out = SQSConsumer._normalize_event({"event_type": event_type, "payload": {"id": "d-1"}})
        assert out == {"action": action, "data": {"id": "d-1"}}

    def test_file_uploaded_camelcase_event(self):
        out = SQSConsumer._normalize_event(
            {"eventType": "file_uploaded", "fileId": "f-1", "ownerId": "u1", "name": "a.txt",
             "mimeType": "text/plain", "sizeBytes": 5, "timestamp": "2026-01-01T00:00:00Z"}
        )
        assert out["action"] == "index_file"
        assert out["data"]["id"] == "f-1"
        assert out["data"]["owner_id"] == "u1"
        assert out["data"]["mime_type"] == "text/plain"
        assert out["data"]["size"] == 5

    @pytest.mark.parametrize("event_type", ["file_deleted", "file_trashed"])
    def test_file_removal_events(self, event_type):
        out = SQSConsumer._normalize_event({"eventType": event_type, "fileId": "f-1"})
        assert out == {"action": "delete", "data": {"type": "file", "id": "f-1"}}

    def test_file_shared_event_is_not_indexed(self):
        body = {"eventType": "file_shared", "fileId": "f-1"}
        assert SQSConsumer._normalize_event(body) == body
