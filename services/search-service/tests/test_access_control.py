"""Tests for caller scoping of search and the internal indexing endpoints."""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import patch

import pytest

from app.config import AuthConfig
from app.main import create_app
from app.services.indexer import Indexer, share_recipients

SERVICE_TOKEN = "test-service-token"
ACCESS_FILTER = '(owner_id = "user-b" OR shared_with = "user-b")'


def _make_client(app_config, mock_meilisearch_client, service_token):
    config = replace(
        app_config, auth=AuthConfig(service_token=service_token, require_auth=True)
    )
    with patch("app.services.meilisearch_client.meilisearch.Client") as mock_cls:
        mock_cls.return_value = mock_meilisearch_client
        flask_app = create_app(config)
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


@pytest.fixture()
def auth_client(app_config, mock_meilisearch_client):
    return _make_client(app_config, mock_meilisearch_client, SERVICE_TOKEN)


@pytest.fixture()
def no_token_client(app_config, mock_meilisearch_client):
    return _make_client(app_config, mock_meilisearch_client, "")


INTERNAL_REQUESTS = [
    ("post", "/api/v1/search/index/document", {"id": "doc-1", "title": "T", "owner_id": "user-a"}),
    ("post", "/api/v1/search/index/file", {"id": "file-1", "name": "f.pdf", "owner_id": "user-a"}),
    ("delete", "/api/v1/search/index/document/doc-1", None),
    ("post", "/api/v1/search/reindex", None),
]


class TestInternalEndpoints:
    @pytest.mark.parametrize(("method", "path", "body"), INTERNAL_REQUESTS)
    def test_gateway_user_is_forbidden(self, auth_client, mock_meilisearch_client, method, path, body):
        response = getattr(auth_client, method)(path, json=body, headers={"X-User-ID": "user-b"})
        assert response.status_code == 403
        assert response.get_json() == {"error": "forbidden"}
        mock_meilisearch_client.index.return_value.add_documents.assert_not_called()
        mock_meilisearch_client.index.return_value.delete_document.assert_not_called()
        mock_meilisearch_client.delete_index.assert_not_called()

    @pytest.mark.parametrize(("method", "path", "body"), INTERNAL_REQUESTS)
    def test_wrong_token_is_forbidden(self, auth_client, method, path, body):
        response = getattr(auth_client, method)(
            path, json=body, headers={"Authorization": "Bearer nope", "X-User-ID": "user-b"}
        )
        assert response.status_code == 403

    @pytest.mark.parametrize(("method", "path", "body"), INTERNAL_REQUESTS)
    def test_closed_when_no_token_configured(self, no_token_client, method, path, body):
        response = getattr(no_token_client, method)(path, json=body, headers={"X-User-ID": "user-b"})
        assert response.status_code == 403

    def test_service_token_can_index(self, auth_client):
        response = auth_client.post(
            "/api/v1/search/index/document",
            json={"id": "doc-1", "title": "T", "owner_id": "user-a"},
            headers={"Authorization": f"Bearer {SERVICE_TOKEN}"},
        )
        assert response.status_code == 201
        assert response.get_json() == {"id": "doc-1", "status": "indexed", "type": "document"}

    def test_service_token_can_reindex(self, auth_client):
        with patch.object(Indexer, "_fetch_all_documents", return_value=[]), patch.object(
            Indexer, "_fetch_all_files", return_value=[]
        ):
            response = auth_client.post(
                "/api/v1/search/reindex", headers={"Authorization": f"Bearer {SERVICE_TOKEN}"}
            )
        assert response.status_code == 200
        assert response.get_json()["status"] == "reindexed"

    def test_user_search_still_allowed(self, auth_client):
        response = auth_client.get("/api/v1/search/?q=x", headers={"X-User-ID": "user-b"})
        assert response.status_code == 200

    def test_anonymous_search_rejected(self, auth_client):
        response = auth_client.get("/api/v1/search/?q=x")
        assert response.status_code == 401


class TestSearchScoping:
    def _filters(self, mock_meilisearch_client):
        calls = mock_meilisearch_client.index.return_value.search.call_args_list
        assert calls
        return [c.args[1].get("filter") for c in calls]

    def test_search_scoped_to_owned_or_shared(self, client, mock_meilisearch_client):
        response = client.get("/api/v1/search/?q=plan", headers={"X-User-ID": "user-b"})
        assert response.status_code == 200
        assert self._filters(mock_meilisearch_client) == [ACCESS_FILTER, ACCESS_FILTER]

    def test_advanced_search_scoped_to_owned_or_shared(self, client, mock_meilisearch_client):
        response = client.post(
            "/api/v1/search/advanced",
            json={"q": "plan", "owner_id": "user-a", "type": "document"},
            headers={"X-User-ID": "user-b"},
        )
        assert response.status_code == 200
        assert self._filters(mock_meilisearch_client) == [f'type = "document" AND {ACCESS_FILTER}']

    def test_suggest_scoped_to_owned_or_shared(self, client, mock_meilisearch_client):
        response = client.get("/api/v1/search/suggest?q=pl", headers={"X-User-ID": "user-b"})
        assert response.status_code == 200
        assert self._filters(mock_meilisearch_client) == [ACCESS_FILTER, ACCESS_FILTER]

    def test_filter_value_is_escaped(self, client, mock_meilisearch_client):
        client.get("/api/v1/search/?q=x", headers={"X-User-ID": 'u" OR owner_id != "'})
        flt = self._filters(mock_meilisearch_client)[0]
        assert flt == '(owner_id = "u\\" OR owner_id != \\"" OR shared_with = "u\\" OR owner_id != \\"")'

    def test_shared_with_is_filterable(self, meilisearch_service, mock_meilisearch_client):
        meilisearch_service.ensure_indices()
        for call in mock_meilisearch_client.index.return_value.update_filterable_attributes.call_args_list:
            assert "shared_with" in call.args[0]

    def test_hit_shape_unchanged(self, client, mock_meilisearch_client):
        mock_meilisearch_client.index.return_value.search.return_value = {
            "estimatedTotalHits": 1,
            "hits": [{"id": "d1", "title": "T", "owner_id": "user-a", "shared_with": ["user-b"], "type": "document"}],
        }
        data = client.get("/api/v1/search/?q=t&type=document", headers={"X-User-ID": "user-b"}).get_json()
        assert "shared_with" not in data["results"][0]
        assert data["results"][0]["owner_id"] == "user-a"


class TestShareRecipients:
    def test_indexer_stores_shared_with(self, meilisearch_service, mock_meilisearch_client):
        Indexer(meilisearch_service).index_document(
            {"id": "d1", "title": "T", "owner_id": "user-a", "shared_with": ["user-b"]}
        )
        stored = mock_meilisearch_client.index.return_value.add_documents.call_args.args[0][0]
        assert stored["owner_id"] == "user-a"
        assert stored["shared_with"] == ["user-b"]

    def test_indexer_defaults_shared_with_to_empty(self, meilisearch_service, mock_meilisearch_client):
        Indexer(meilisearch_service).index_file({"id": "f1", "name": "f.pdf", "owner_id": "user-a"})
        stored = mock_meilisearch_client.index.return_value.add_documents.call_args.args[0][0]
        assert stored["shared_with"] == []

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (None, []),
            ("user-b", []),
            (["user-b", " user-c ", "", "user-b"], ["user-b", "user-c"]),
            ([{"shared_with": "user-b", "permission": "viewer"}, {"sharedWith": "user-c"}], ["user-b", "user-c"]),
            ([42, {"permission": "viewer"}], []),
        ],
    )
    def test_share_recipients(self, value, expected):
        assert share_recipients(value) == expected
