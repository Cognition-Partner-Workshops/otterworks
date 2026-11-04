"""Tests for the authentication middleware."""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import patch

import pytest
from app.config import AuthConfig
from app.main import create_app

from tests.conftest import TEST_SERVICE_TOKEN

INTERNAL_ROUTES = [
    ("post", "/api/v1/search/index/document", {"id": "doc-1", "title": "t", "owner_id": "victim"}),
    ("post", "/api/v1/search/index/file", {"id": "file-1", "name": "f", "owner_id": "victim"}),
    ("delete", "/api/v1/search/index/document/doc-1", None),
    ("delete", "/api/v1/search/index/file/file-1", None),
    ("post", "/api/v1/search/reindex", None),
]


def _client(app_config, mock_meilisearch_client, **auth):
    config = replace(app_config, auth=AuthConfig(**auth))
    with patch("app.services.meilisearch_client.meilisearch.Client") as mock_cls:
        mock_cls.return_value = mock_meilisearch_client
        flask_app = create_app(config)
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


def _call(client, method, path, body, headers=None):
    return getattr(client, method)(path, json=body, headers=headers or {})


@pytest.mark.parametrize("require_auth", [True, False])
@pytest.mark.parametrize(("method", "path", "body"), INTERNAL_ROUTES)
class TestInternalRoutes:
    def test_gateway_user_identity_rejected(
        self, app_config, mock_meilisearch_client, require_auth, method, path, body
    ):
        client = _client(
            app_config, mock_meilisearch_client,
            service_token=TEST_SERVICE_TOKEN, require_auth=require_auth,
        )
        response = _call(client, method, path, body, {"X-User-ID": "mallory"})
        assert response.status_code == 401
        mock_meilisearch_client.delete_index.assert_not_called()
        mock_meilisearch_client.index.return_value.add_documents.assert_not_called()
        mock_meilisearch_client.index.return_value.delete_document.assert_not_called()

    def test_user_jwt_rejected(
        self, app_config, mock_meilisearch_client, require_auth, method, path, body
    ):
        client = _client(
            app_config, mock_meilisearch_client,
            service_token=TEST_SERVICE_TOKEN, require_auth=require_auth,
        )
        headers = {"Authorization": "Bearer some.user.jwt", "X-User-ID": "mallory"}
        assert _call(client, method, path, body, headers).status_code == 401

    def test_fails_closed_without_configured_token(
        self, app_config, mock_meilisearch_client, require_auth, method, path, body
    ):
        client = _client(
            app_config, mock_meilisearch_client, service_token="", require_auth=require_auth
        )
        for headers in ({}, {"Authorization": "Bearer "}, {"X-User-ID": "mallory"}):
            assert _call(client, method, path, body, headers).status_code == 401

    def test_service_token_accepted(
        self, app_config, mock_meilisearch_client, require_auth, method, path, body
    ):
        client = _client(
            app_config, mock_meilisearch_client,
            service_token=TEST_SERVICE_TOKEN, require_auth=require_auth,
        )
        headers = {"Authorization": f"Bearer {TEST_SERVICE_TOKEN}"}
        assert _call(client, method, path, body, headers).status_code != 401


class TestUserRoutes:
    def test_require_auth_accepts_gateway_identity(self, app_config, mock_meilisearch_client):
        client = _client(
            app_config, mock_meilisearch_client,
            service_token=TEST_SERVICE_TOKEN, require_auth=True,
        )
        response = client.get("/api/v1/search/?q=hello", headers={"X-User-ID": "alice"})
        assert response.status_code == 200

    def test_require_auth_rejects_anonymous(self, app_config, mock_meilisearch_client):
        client = _client(
            app_config, mock_meilisearch_client,
            service_token=TEST_SERVICE_TOKEN, require_auth=True,
        )
        assert client.get("/api/v1/search/?q=hello").status_code == 401

    def test_health_is_public(self, app_config, mock_meilisearch_client):
        client = _client(app_config, mock_meilisearch_client, service_token="", require_auth=True)
        assert client.get("/health").status_code == 200
