"""QA test pyramid (unit layer) for the search area.

Tests that expose a known defect are marked ``xfail(strict=True)`` with a
[PLANTED] or [REAL] tag so the suite stays green while the defect exists and
flags the change once it is fixed.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.services.indexer import Indexer
from app.services.sqs_consumer import SQSConsumer


def _failed_task(message: str) -> MagicMock:
    result = MagicMock()
    result.status = "failed"
    result.error = {"message": message}
    return result


def _ok_task() -> MagicMock:
    result = MagicMock()
    result.status = "succeeded"
    return result


class TestSearchScoping:
    def test_search_scopes_to_gateway_user(self, client, mock_meilisearch_client):
        client.get("/api/v1/search/?q=otter", headers={"X-User-ID": "user-a"})
        params = mock_meilisearch_client.index.return_value.search.call_args[0][1]
        assert 'owner_id = "user-a"' in params["filter"]

    def test_search_ignores_owner_id_query_param(self, client, mock_meilisearch_client):
        client.get("/api/v1/search/?q=otter&owner_id=victim", headers={"X-User-ID": "user-a"})
        params = mock_meilisearch_client.index.return_value.search.call_args[0][1]
        assert "victim" not in params["filter"]

    def test_advanced_search_ignores_body_owner_id(self, client, mock_meilisearch_client):
        client.post(
            "/api/v1/search/advanced",
            json={"q": "otter", "owner_id": "victim"},
            headers={"X-User-ID": "user-a"},
        )
        params = mock_meilisearch_client.index.return_value.search.call_args[0][1]
        assert 'owner_id = "user-a"' in params["filter"]
        assert "victim" not in params["filter"]

    def test_type_filter_value_is_escaped(self, client, mock_meilisearch_client):
        client.get(
            '/api/v1/search/?q=x&type=document" OR owner_id != "z',
            headers={"X-User-ID": "user-a"},
        )
        params = mock_meilisearch_client.index.return_value.search.call_args[0][1]
        assert 'type = "document\\" OR owner_id != \\"z"' in params["filter"]

    def test_document_type_searches_only_documents_index(self, meilisearch_service):
        assert meilisearch_service._resolve_indices("document") == ["test-otterworks-documents"]
        assert meilisearch_service._resolve_indices("file") == ["test-otterworks-files"]

    @pytest.mark.xfail(strict=True, reason="[REAL] /suggest is not owner-scoped: suggest() takes no owner and applies no filter")
    def test_suggest_is_owner_scoped(self, client, mock_meilisearch_client):
        client.get("/api/v1/search/suggest?q=sec", headers={"X-User-ID": "user-a"})
        params = mock_meilisearch_client.index.return_value.search.call_args[0][1]
        assert 'owner_id = "user-a"' in params.get("filter", "")


class TestSuggestChaos:
    def test_suggest_ok_when_chaos_flag_off(self, client, mock_meilisearch_client):
        mock_meilisearch_client.index.return_value.search.return_value = {"hits": [{"title": "Otter plan"}]}
        with patch("app.api.search._chaos_active", return_value=False):
            response = client.get("/api/v1/search/suggest?q=ot", headers={"X-User-ID": "u"})
        assert response.status_code == 200
        assert response.get_json()["suggestions"] == ["Otter plan"]

    @pytest.mark.xfail(strict=True, reason="[PLANTED] chaos flag search-suggest-500 (chaos:search-service:suggest_500)")
    def test_suggest_ok_when_chaos_flag_on(self, client):
        with patch("app.api.search._chaos_active", return_value=True):
            response = client.get("/api/v1/search/suggest?q=ot", headers={"X-User-ID": "u"})
        assert response.status_code == 200


class TestIndexOwnership:
    @pytest.mark.xfail(strict=True, reason="[REAL] /index/document trusts body owner_id instead of X-User-ID")
    def test_index_document_rejects_foreign_owner(self, client):
        response = client.post(
            "/api/v1/search/index/document",
            json={"id": "d1", "title": "Phish", "owner_id": "victim"},
            headers={"X-User-ID": "attacker"},
        )
        assert response.status_code in (400, 403)

    @pytest.mark.xfail(strict=True, reason="[REAL] DELETE /index/<type>/<id> does no ownership check")
    def test_delete_rejects_foreign_entry(self, client, mock_meilisearch_client):
        mock_meilisearch_client.index.return_value.get_document.return_value = {"id": "d1", "owner_id": "victim"}
        response = client.delete("/api/v1/search/index/document/d1", headers={"X-User-ID": "attacker"})
        assert response.status_code in (403, 404)


class TestKeyExistRetry:
    def test_index_file_retries_on_mdb_keyexist(self, meilisearch_service, mock_meilisearch_client):
        mock_meilisearch_client.wait_for_task.side_effect = [
            _failed_task("internal: MDB_KEYEXIST: Key/data pair already exists."),
            _ok_task(),
            _ok_task(),
        ]
        meilisearch_service.index_file({"id": "f1", "name": "a.txt"})
        assert mock_meilisearch_client.index.return_value.add_documents.call_count == 2

    @pytest.mark.xfail(strict=True, reason="[REAL] index_document does not retry on MDB_KEYEXIST (index_file does)")
    def test_index_document_retries_on_mdb_keyexist(self, meilisearch_service, mock_meilisearch_client):
        mock_meilisearch_client.wait_for_task.side_effect = [
            _failed_task("internal: MDB_KEYEXIST: Key/data pair already exists."),
            _ok_task(),
            _ok_task(),
        ]
        meilisearch_service.index_document({"id": "d1", "title": "Doc"})
        assert mock_meilisearch_client.index.return_value.add_documents.call_count == 2

    def test_index_document_raises_on_other_failures(self, meilisearch_service, mock_meilisearch_client):
        mock_meilisearch_client.wait_for_task.return_value = _failed_task("invalid_document_id")
        with pytest.raises(RuntimeError):
            meilisearch_service.index_document({"id": "d1", "title": "Doc"})


class TestEventNormalization:
    @pytest.mark.parametrize(
        ("event_type", "action"),
        [
            ("document_created", "index_document"),
            ("document_updated", "index_document"),
            ("document_deleted", "delete"),
            ("file_trashed", "delete"),
            ("file_restored", "index_file"),
        ],
    )
    def test_snake_case_events(self, event_type, action):
        out = SQSConsumer._normalize_event({"event_type": event_type, "payload": {"id": "x"}})
        assert out == {"action": action, "data": {"id": "x"}}

    def test_file_service_upload_event_maps_fields(self):
        out = SQSConsumer._normalize_event({
            "eventType": "file_uploaded", "fileId": "f1", "name": "a.txt",
            "mimeType": "text/plain", "ownerId": "u1", "sizeBytes": 5, "timestamp": "t",
        })
        assert out["action"] == "index_file"
        assert out["data"]["id"] == "f1"
        assert out["data"]["owner_id"] == "u1"
        assert out["data"]["mime_type"] == "text/plain"

    def test_file_service_delete_event(self):
        out = SQSConsumer._normalize_event({"eventType": "file_deleted", "fileId": "f1"})
        assert out == {"action": "delete", "data": {"type": "file", "id": "f1"}}

    def test_sns_wrapped_message_is_unwrapped_and_processed(self):
        consumer = SQSConsumer.__new__(SQSConsumer)
        consumer.queue_url = "q"
        consumer.indexer = MagicMock()
        sqs = MagicMock()
        inner = {"event_type": "document_deleted", "payload": {"type": "document", "id": "d1"}}
        body = {"Message": json.dumps(inner), "TopicArn": "arn"}
        consumer._process_message(sqs, {"Body": json.dumps(body), "ReceiptHandle": "r"})
        consumer.indexer.process_event.assert_called_once_with(
            {"action": "delete", "data": {"type": "document", "id": "d1"}}
        )
        sqs.delete_message.assert_called_once()

    @pytest.mark.xfail(strict=True, reason="[REAL] folders are never indexed: no folder_* event mapping or indexer path")
    def test_folder_created_event_is_indexed(self):
        indexer = Indexer(MagicMock())
        event = SQSConsumer._normalize_event({"event_type": "folder_created", "payload": {"id": "fo1", "name": "Q3"}})
        assert indexer.process_event(event) is not None
