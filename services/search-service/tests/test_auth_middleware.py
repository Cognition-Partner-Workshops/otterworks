"""Tests for the authentication middleware."""

from __future__ import annotations

from typing import ClassVar
from unittest.mock import MagicMock, patch

import pytest

from app.config import AppConfig, AuthConfig, MeiliSearchConfig, SQSConfig
from app.main import create_app

SERVICE_TOKEN = "test-service-token"

ADMIN_REQUESTS = (
    ("post", "/api/v1/search/index/document"),
    ("post", "/api/v1/search/index/file"),
    ("delete", "/api/v1/search/index/document/doc-123"),
    ("post", "/api/v1/search/reindex"),
)


def _config(service_token: str) -> AppConfig:
    return AppConfig(
        meilisearch=MeiliSearchConfig(url="http://localhost:7700", api_key=""),
        sqs=SQSConfig(enabled=False),
        auth=AuthConfig(service_token=service_token, require_auth=True),
    )


@pytest.fixture()
def auth_client(mock_meilisearch_client: MagicMock):
    """Flask test client with auth enforced and a service token configured."""
    with patch("app.services.meilisearch_client.meilisearch.Client") as mock_cls:
        mock_cls.return_value = mock_meilisearch_client
        app = create_app(_config(SERVICE_TOKEN))
        app.config["TESTING"] = True
        yield app.test_client()


@pytest.fixture()
def no_token_client(mock_meilisearch_client: MagicMock):
    """Flask test client with auth enforced and no service token (local dev)."""
    with patch("app.services.meilisearch_client.meilisearch.Client") as mock_cls:
        mock_cls.return_value = mock_meilisearch_client
        app = create_app(_config(""))
        app.config["TESTING"] = True
        yield app.test_client()


class TestAnonymous:
    def test_health_is_public(self, auth_client):
        assert auth_client.get("/health").status_code == 200

    def test_search_requires_identity(self, auth_client):
        assert auth_client.get("/api/v1/search/?q=test").status_code == 401

    @pytest.mark.parametrize(("method", "path"), ADMIN_REQUESTS)
    def test_admin_paths_require_identity(self, auth_client, method, path):
        response = getattr(auth_client, method)(path, json={})
        assert response.status_code == 401


class TestPlainUser:
    HEADERS: ClassVar[dict[str, str]] = {"X-User-ID": "user-1", "X-User-Roles": "USER"}

    def test_user_can_search(self, auth_client):
        response = auth_client.get("/api/v1/search/?q=test", headers=self.HEADERS)
        assert response.status_code == 200

    @pytest.mark.parametrize(("method", "path"), ADMIN_REQUESTS)
    def test_user_cannot_mutate_index(self, auth_client, method, path):
        response = getattr(auth_client, method)(path, headers=self.HEADERS, json={})
        assert response.status_code == 403
        assert response.get_json() == {"error": "forbidden"}

    @pytest.mark.parametrize(("method", "path"), ADMIN_REQUESTS)
    def test_user_without_roles_header_cannot_mutate_index(self, no_token_client, method, path):
        response = getattr(no_token_client, method)(path, headers={"X-User-ID": "user-1"}, json={})
        assert response.status_code == 403

    def test_bearer_that_is_not_the_service_token_is_not_enough(self, auth_client):
        headers = {**self.HEADERS, "Authorization": "Bearer not-the-service-token"}
        response = auth_client.post("/api/v1/search/reindex", headers=headers)
        assert response.status_code == 403


class TestAdminAndServiceToken:
    def test_admin_role_can_reindex(self, auth_client):
        headers = {"X-User-ID": "admin-1", "X-User-Roles": "ADMIN,USER"}
        response = auth_client.post("/api/v1/search/reindex", headers=headers)
        assert response.status_code == 200

    def test_admin_role_can_index_document(self, no_token_client):
        headers = {"X-User-ID": "admin-1", "X-User-Roles": "USER,ADMIN"}
        response = no_token_client.post(
            "/api/v1/search/index/document",
            headers=headers,
            json={"id": "doc-1", "title": "Doc", "owner_id": "admin-1"},
        )
        assert response.status_code == 201

    def test_service_token_can_reindex(self, auth_client):
        headers = {"Authorization": f"Bearer {SERVICE_TOKEN}"}
        response = auth_client.post("/api/v1/search/reindex", headers=headers)
        assert response.status_code == 200

    def test_service_token_can_delete_from_index(self, auth_client, mock_meilisearch_client):
        mock_meilisearch_client.index.return_value.get_document.return_value = {"id": "doc-123"}
        headers = {"Authorization": f"Bearer {SERVICE_TOKEN}"}
        response = auth_client.delete("/api/v1/search/index/document/doc-123", headers=headers)
        assert response.status_code == 200
