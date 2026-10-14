"""QA unit tests for search-service search/index logic (MeiliSearch mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import meilisearch
import pytest
from app.config import AppConfig, AuthConfig, MeiliSearchConfig, SQSConfig
from app.main import create_app
from app.services import meilisearch_client as mc
from app.services.indexer import Indexer
from app.services.meilisearch_client import MeiliSearchService
from app.services.sqs_consumer import SQSConsumer

DOCS = "test-otterworks-documents"
FILES = "test-otterworks-files"


def _hit(doc_id: str, title: str = "T", content: str = "", owner: str = "u1", **extra):
    hit = {"id": doc_id, "title": title, "content": content, "owner_id": owner, "type": "document"}
    hit.update(extra)
    hit.setdefault("_formatted", {"title": title, "content": content})
    return hit


def _file_hit(file_id: str, name: str = "f.txt", owner: str = "u1", **extra):
    hit = {"id": file_id, "name": name, "owner_id": owner, "type": "file", "mime_type": "text/plain"}
    hit.update(extra)
    hit.setdefault("_formatted", {"name": name})
    return hit


@pytest.fixture()
def indices(mock_meilisearch_client):
    """Give each index name its own mock so per-index calls can be asserted."""
    per_index: dict[str, MagicMock] = {}
    task = MagicMock()
    task.task_uid = 7

    def _index(name):
        if name not in per_index:
            idx = MagicMock()
            idx.search.return_value = {"hits": [], "estimatedTotalHits": 0}
            idx.add_documents.return_value = task
            idx.delete_document.return_value = task
            per_index[name] = idx
        return per_index[name]

    mock_meilisearch_client.index.side_effect = _index
    return _index


@pytest.fixture(autouse=True)
def _reset_analytics():
    with mc._analytics_lock:
        mc._search_analytics["queries"] = []
        mc._search_analytics["total_searches"] = 0
        mc._search_analytics["total_results"] = 0
    yield


# ---------------------------------------------------------------- filter escaping


class TestEscape:
    def test_plain_value_unchanged(self):
        assert MeiliSearchService._escape("abc-123") == "abc-123"

    def test_double_quote_escaped(self):
        assert MeiliSearchService._escape('a"b') == 'a\\"b'

    def test_backslash_escaped_before_quote(self):
        assert MeiliSearchService._escape('a\\"') == 'a\\\\\\"'

    def test_injection_attempt_stays_inside_quotes(self):
        escaped = MeiliSearchService._escape('x" OR owner_id != "y')
        assert '\\"' in escaped
        assert f'owner_id = "{escaped}"'.count('"') - escaped.count('\\"') == 2


# ---------------------------------------------------------------- search params


class TestBuildSearchParams:
    def test_single_index_offset_and_limit(self, meilisearch_service):
        params = meilisearch_service._build_search_params(3, 10, [], multi_index=False)
        assert params["offset"] == 20
        assert params["limit"] == 10
        assert "filter" not in params

    def test_multi_index_fetches_all_pages_up_to_requested(self, meilisearch_service):
        params = meilisearch_service._build_search_params(3, 10, [], multi_index=True)
        assert params["offset"] == 0
        assert params["limit"] == 30

    def test_filters_joined_with_and(self, meilisearch_service):
        params = meilisearch_service._build_search_params(1, 5, ['a = "1"', 'b = "2"'], False)
        assert params["filter"] == 'a = "1" AND b = "2"'

    def test_highlight_and_crop_configured(self, meilisearch_service):
        params = meilisearch_service._build_search_params(1, 5, [], False)
        assert params["highlightPreTag"] == "<em>"
        assert params["highlightPostTag"] == "</em>"
        assert "content" in params["attributesToCrop"]
        assert set(params["attributesToHighlight"]) >= {"title", "name", "content"}


class TestResolveIndices:
    @pytest.mark.parametrize(
        ("doc_type", "expected"),
        [("document", [DOCS]), ("file", [FILES]), (None, [DOCS, FILES]), ("folder", [DOCS, FILES])],
    )
    def test_resolve(self, meilisearch_service, doc_type, expected):
        assert meilisearch_service._resolve_indices(doc_type) == expected


# ---------------------------------------------------------------- search()


class TestSearch:
    def test_owner_and_type_filter_applied(self, meilisearch_service, indices):
        meilisearch_service.search("q", doc_type="document", owner_id="user-9")
        _, params = indices(DOCS).search.call_args.args
        assert params["filter"] == 'type = "document" AND owner_id = "user-9"'
        indices(FILES).search.assert_not_called()

    def test_no_owner_means_no_filter(self, meilisearch_service, indices):
        meilisearch_service.search("q")
        _, params = indices(DOCS).search.call_args.args
        assert "filter" not in params

    def test_merges_documents_and_files_and_sums_totals(self, meilisearch_service, indices):
        indices(DOCS).search.return_value = {"hits": [_hit("d1")], "estimatedTotalHits": 1}
        indices(FILES).search.return_value = {"hits": [_file_hit("f1")], "estimatedTotalHits": 1}
        resp = meilisearch_service.search("q")
        assert resp.total == 2
        assert {h.id for h in resp.results} == {"d1", "f1"}
        assert {h.type for h in resp.results} == {"document", "file"}

    def test_multi_index_page_two_slices_merged_hits(self, meilisearch_service, indices):
        indices(DOCS).search.return_value = {
            "hits": [_hit("d1"), _hit("d2"), _hit("d3")],
            "estimatedTotalHits": 3,
        }
        indices(FILES).search.return_value = {"hits": [_file_hit("f1")], "estimatedTotalHits": 1}
        resp = meilisearch_service.search("q", page=2, page_size=2)
        assert [h.id for h in resp.results] == ["d3", "f1"]
        assert resp.total == 4
        assert resp.page == 2 and resp.page_size == 2

    def test_single_index_returns_page_as_given(self, meilisearch_service, indices):
        indices(FILES).search.return_value = {"hits": [_file_hit("f9")], "estimatedTotalHits": 11}
        resp = meilisearch_service.search("q", doc_type="file", page=2, page_size=10)
        assert [h.id for h in resp.results] == ["f9"]
        assert resp.total == 11

    def test_filter_error_becomes_value_error(self, meilisearch_service, indices):
        err = meilisearch.errors.MeilisearchApiError("bad filter", MagicMock(status_code=400, text="{}"))
        indices(DOCS).search.side_effect = err
        with pytest.raises(ValueError, match="Invalid search filter"):
            meilisearch_service.search("q")

    def test_records_analytics(self, meilisearch_service, indices):
        indices(DOCS).search.side_effect = [
            {"hits": [_hit("d1")], "estimatedTotalHits": 1},
            {"hits": [], "estimatedTotalHits": 0},
        ]
        meilisearch_service.search("otters")
        meilisearch_service.search("nothing")
        data = mc.get_search_analytics().to_dict()
        assert data["total_searches"] == 2
        assert {"query": "nothing", "count": 1} in data["zero_result_queries"]


class TestParseHit:
    def test_document_hit_maps_title_snippet_and_highlights(self, meilisearch_service):
        hit = _hit(
            "d1",
            title="Otter Plan",
            content="the otter plan",
            _formatted={"title": "<em>Otter</em> Plan", "content": "the <em>otter</em> plan"},
            tags=["x"],
            updated_at="2026-01-01",
        )
        parsed = meilisearch_service._parse_hit(hit, DOCS)
        assert parsed.title == "Otter Plan"
        assert parsed.content_snippet == "the <em>otter</em> plan"
        assert parsed.highlights == {
            "title": ["<em>Otter</em> Plan"],
            "content": ["the <em>otter</em> plan"],
        }
        assert parsed.tags == ["x"]
        assert parsed.to_dict()["updated_at"] == "2026-01-01"

    def test_file_hit_uses_name_and_no_snippet(self, meilisearch_service):
        parsed = meilisearch_service._parse_hit(_file_hit("f1", name="report.pdf", size=42), FILES)
        assert parsed.title == "report.pdf"
        assert parsed.content_snippet == ""
        assert parsed.type == "file"
        assert parsed.to_dict()["size"] == 42

    def test_snippet_truncated_to_200(self, meilisearch_service):
        long = "a" * 500
        parsed = meilisearch_service._parse_hit(_hit("d1", content=long), DOCS)
        assert len(parsed.content_snippet) == 200

    def test_optional_fields_omitted_from_dict(self, meilisearch_service):
        out = meilisearch_service._parse_hit({"id": "d1", "title": "t"}, DOCS).to_dict()
        for key in ("created_at", "updated_at", "mime_type", "folder_id", "size"):
            assert key not in out
        assert out["type"] == "document"


# ---------------------------------------------------------------- advanced search


class TestAdvancedSearch:
    def test_builds_tag_and_date_filters(self, meilisearch_service, indices):
        meilisearch_service.advanced_search(
            query="q",
            doc_type="document",
            owner_id="u1",
            tags=["a", "b"],
            date_from="2026-01-01",
            date_to="2026-12-31",
        )
        _, params = indices(DOCS).search.call_args.args
        assert params["filter"] == (
            'type = "document" AND owner_id = "u1" AND (tags = "a" OR tags = "b") '
            'AND created_at >= "2026-01-01" AND created_at <= "2026-12-31"'
        )

    def test_empty_query_reported_as_star(self, meilisearch_service, indices):
        resp = meilisearch_service.advanced_search()
        assert resp.query == "*"
        assert indices(DOCS).search.call_args.args[0] == ""


# ---------------------------------------------------------------- suggest


class TestSuggest:
    def test_dedupes_across_indices(self, meilisearch_service, indices):
        indices(DOCS).search.return_value = {"hits": [{"title": "Otter"}, {"title": "Otter"}]}
        indices(FILES).search.return_value = {"hits": [{"name": "Otter"}, {"name": "otter.png"}]}
        assert meilisearch_service.suggest("ot") == ["Otter", "otter.png"]

    def test_respects_size_limit(self, meilisearch_service, indices):
        indices(DOCS).search.return_value = {"hits": [{"title": f"t{i}"} for i in range(5)]}
        assert meilisearch_service.suggest("t", size=3) == ["t0", "t1", "t2"]
        indices(FILES).search.assert_not_called()

    def test_skips_empty_titles(self, meilisearch_service, indices):
        indices(DOCS).search.return_value = {"hits": [{"title": ""}, {}]}
        assert meilisearch_service.suggest("zz") == []


# ---------------------------------------------------------------- index / delete


class TestIndexing:
    def test_index_document_sets_type(self, meilisearch_service, indices):
        meilisearch_service.index_document({"id": "d1", "title": "t"})
        assert indices(DOCS).add_documents.call_args.args[0] == [{"id": "d1", "title": "t", "type": "document"}]

    def test_failed_task_raises(self, meilisearch_service, indices, mock_meilisearch_client):
        failed = MagicMock(status="failed", error={"code": "x"})
        mock_meilisearch_client.wait_for_task.return_value = failed
        with pytest.raises(RuntimeError, match="failed"):
            meilisearch_service.index_document({"id": "d1", "title": "t"})

    def test_index_file_retries_on_mdb_keyexist(self, meilisearch_service, indices, mock_meilisearch_client):
        ok = MagicMock(status="succeeded")
        bad = MagicMock(status="failed", error="MDB_KEYEXIST")
        mock_meilisearch_client.wait_for_task.side_effect = [bad, ok, ok]
        meilisearch_service.index_file({"id": "f1", "name": "n"})
        assert indices(FILES).add_documents.call_count == 2
        indices(FILES).delete_document.assert_called_once_with("f1")

    def test_delete_missing_returns_false(self, meilisearch_service, indices):
        indices(DOCS).get_document.side_effect = meilisearch.errors.MeilisearchApiError(
            "nf", MagicMock(status_code=404, text="{}")
        )
        assert meilisearch_service.delete_document("document", "nope") is False

    def test_delete_file_targets_files_index(self, meilisearch_service, indices):
        assert meilisearch_service.delete_document("file", "f1") is True
        indices(FILES).delete_document.assert_called_once_with("f1")


class TestIndexer:
    @pytest.fixture()
    def search(self):
        return MagicMock()

    def test_document_requires_id_and_title(self, search):
        with pytest.raises(ValueError, match="id"):
            Indexer(search).index_document({"title": "t"})
        with pytest.raises(ValueError, match="title"):
            Indexer(search).index_document({"id": "1"})

    def test_file_requires_id_and_name(self, search):
        with pytest.raises(ValueError, match="id"):
            Indexer(search).index_file({"name": "n"})
        with pytest.raises(ValueError, match="name"):
            Indexer(search).index_file({"id": "1"})

    def test_document_defaults(self, search):
        result = Indexer(search).index_document({"id": "1", "title": "t"})
        assert result == {"status": "indexed", "id": "1", "type": "document"}
        doc = search.index_document.call_args.args[0]
        assert doc["content"] == "" and doc["tags"] == [] and doc["owner_id"] == ""

    def test_file_defaults(self, search):
        Indexer(search).index_file({"id": "1", "name": "n"})
        f = search.index_file.call_args.args[0]
        assert f["size"] == 0 and f["mime_type"] == "" and f["folder_id"] == ""

    def test_remove_rejects_unknown_type(self, search):
        with pytest.raises(ValueError, match="Invalid type"):
            Indexer(search).remove("folder", "1")

    @pytest.mark.parametrize(("deleted", "status"), [(True, "deleted"), (False, "not_found")])
    def test_remove_status(self, search, deleted, status):
        search.delete_document.return_value = deleted
        assert Indexer(search).remove("file", "1")["status"] == status

    def test_process_event_dispatch(self, search):
        ix = Indexer(search)
        ix.process_event({"action": "index_document", "data": {"id": "1", "title": "t"}})
        ix.process_event({"action": "index_file", "data": {"id": "2", "name": "n"}})
        search.delete_document.return_value = True
        ix.process_event({"action": "delete", "data": {"type": "file", "id": "2"}})
        assert ix.process_event({"action": "bogus"}) is None
        search.index_document.assert_called_once()
        search.index_file.assert_called_once()
        search.delete_document.assert_called_once_with("file", "2")


# ---------------------------------------------------------------- SQS normalisation


class TestNormalizeEvent:
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
    def test_document_service_format(self, event_type, action):
        out = SQSConsumer._normalize_event({"event_type": event_type, "payload": {"id": "1"}})
        assert out == {"action": action, "data": {"id": "1"}}

    def test_file_service_upload_maps_camel_case(self):
        out = SQSConsumer._normalize_event({
            "eventType": "file_uploaded",
            "fileId": "f1",
            "name": "a.txt",
            "mimeType": "text/plain",
            "ownerId": "u1",
            "folderId": "fo",
            "sizeBytes": 9,
            "timestamp": "2026-01-01T00:00:00Z",
        })
        assert out["action"] == "index_file"
        assert out["data"] == {
            "id": "f1", "name": "a.txt", "mime_type": "text/plain", "owner_id": "u1",
            "folder_id": "fo", "size": 9, "tags": [],
            "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z",
        }

    def test_file_service_delete(self):
        out = SQSConsumer._normalize_event({"eventType": "file_deleted", "fileId": "f1"})
        assert out == {"action": "delete", "data": {"type": "file", "id": "f1"}}

    def test_file_shared_passes_through_unindexed(self):
        body = {"eventType": "file_shared", "fileId": "f1"}
        assert SQSConsumer._normalize_event(body) is body

    def test_indexer_format_passthrough(self):
        body = {"action": "index_document", "data": {}}
        assert SQSConsumer._normalize_event(body) is body


# ---------------------------------------------------------------- HTTP layer


@pytest.fixture()
def auth_client(mock_meilisearch_client):
    cfg = AppConfig(
        service_name="search-service-test",
        meilisearch=MeiliSearchConfig(url="http://x", api_key="", documents_index=DOCS, files_index=FILES),
        sqs=SQSConfig(enabled=False),
        auth=AuthConfig(service_token="svc-token", require_auth=True),
    )
    with patch("app.services.meilisearch_client.meilisearch.Client", return_value=mock_meilisearch_client):
        app = create_app(cfg)
    app.config["TESTING"] = True
    return app.test_client()


class TestHttpLayer:
    def test_search_scopes_to_gateway_user_header(self, client, indices):
        client.get("/api/v1/search/?q=x&owner_id=someone-else", headers={"X-User-ID": "me"})
        _, params = indices(DOCS).search.call_args.args
        assert params["filter"] == 'owner_id = "me"'

    @pytest.mark.parametrize("qs", ["page=0", "size=1000", "page=-5&size=0"])
    def test_page_and_size_are_clamped(self, client, indices, qs):
        resp = client.get(f"/api/v1/search/?q=x&{qs}")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["page"] >= 1
        assert 1 <= body["page_size"] <= 100

    def test_invalid_size_is_400(self, client):
        assert client.get("/api/v1/search/?q=x&size=abc").status_code == 400

    def test_search_filter_error_is_400(self, client, indices):
        indices(DOCS).search.side_effect = meilisearch.errors.MeilisearchApiError(
            "bad", MagicMock(status_code=400, text="{}")
        )
        assert client.get("/api/v1/search/?q=x").status_code == 400

    def test_search_backend_error_is_500_without_leak(self, client, indices):
        indices(DOCS).search.side_effect = RuntimeError("meili down secret")
        resp = client.get("/api/v1/search/?q=x")
        assert resp.status_code == 500
        assert "secret" not in resp.get_data(as_text=True)

    def test_suggest_short_prefix_short_circuits(self, client, indices):
        resp = client.get("/api/v1/search/suggest?q=a")
        assert resp.get_json() == {"suggestions": [], "query": "a"}
        indices(DOCS).search.assert_not_called()

    def test_suggest_backend_failure_degrades_to_empty(self, client, indices):
        indices(DOCS).search.side_effect = RuntimeError("down")
        resp = client.get("/api/v1/search/suggest?q=ott")
        assert resp.status_code == 200
        assert resp.get_json()["suggestions"] == []

    def test_advanced_scopes_owner_from_header_not_body(self, client, indices):
        client.post("/api/v1/search/advanced", json={"q": "x", "owner_id": "evil"}, headers={"X-User-ID": "me"})
        _, params = indices(DOCS).search.call_args.args
        assert 'owner_id = "me"' in params["filter"]
        assert "evil" not in params["filter"]

    def test_advanced_invalid_page_is_400(self, client):
        assert client.post("/api/v1/search/advanced", json={"page": "x"}).status_code == 400

    def test_delete_unknown_type_is_400(self, client):
        assert client.delete("/api/v1/search/index/folder/1").status_code == 400

    def test_index_file_missing_name_is_400(self, client):
        assert client.post("/api/v1/search/index/file", json={"id": "1"}).status_code == 400

    def test_analytics_endpoint_shape(self, client, indices):
        client.get("/api/v1/search/?q=hello")
        body = client.get("/api/v1/search/analytics").get_json()
        assert set(body) == {"popular_queries", "zero_result_queries", "total_searches", "avg_results_per_query"}

    def test_auth_rejects_anonymous(self, auth_client):
        assert auth_client.get("/api/v1/search/?q=x").status_code == 401

    def test_auth_accepts_gateway_header(self, auth_client):
        assert auth_client.get("/api/v1/search/?q=x", headers={"X-User-ID": "u"}).status_code == 200

    def test_auth_accepts_service_token(self, auth_client):
        resp = auth_client.get("/api/v1/search/?q=x", headers={"Authorization": "Bearer svc-token"})
        assert resp.status_code == 200

    def test_auth_rejects_wrong_service_token(self, auth_client):
        resp = auth_client.get("/api/v1/search/?q=x", headers={"Authorization": "Bearer nope"})
        assert resp.status_code == 401

    def test_health_is_public(self, auth_client):
        assert auth_client.get("/health").status_code == 200
