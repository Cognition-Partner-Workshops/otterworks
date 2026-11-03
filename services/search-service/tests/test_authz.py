"""Object- and function-level authorization for search-service routes."""

from __future__ import annotations

import secrets
from unittest.mock import MagicMock, patch

import jwt
import meilisearch
import pytest

from app.config import AppConfig, AuthConfig
from app.main import create_app

OWNER = "user-owner"
ATTACKER = "user-attacker"
ADMIN = "user-admin"


def _not_found() -> meilisearch.errors.MeilisearchApiError:
    response = MagicMock(status_code=404, text='{"message": "Document not found", "code": "document_not_found"}')
    return meilisearch.errors.MeilisearchApiError("not found", response)


@pytest.fixture()
def jwt_secret() -> str:
    return secrets.token_hex(32)


@pytest.fixture()
def service_token() -> str:
    return secrets.token_hex(16)


@pytest.fixture()
def auth_client(app_config: AppConfig, mock_meilisearch_client: MagicMock, jwt_secret: str, service_token: str):
    config = AppConfig(
        service_name=app_config.service_name,
        meilisearch=app_config.meilisearch,
        sqs=app_config.sqs,
        auth=AuthConfig(service_token=service_token, require_auth=True, jwt_secret=jwt_secret),
    )
    with patch("app.services.meilisearch_client.meilisearch.Client") as mock_cls:
        mock_cls.return_value = mock_meilisearch_client
        flask_app = create_app(config)
        flask_app.config["TESTING"] = True
        yield flask_app.test_client()


def _user(user_id: str, secret: str, roles: list[str] | None = None, token_type: str = "access") -> dict[str, str]:
    token = jwt.encode({"sub": user_id, "roles": roles or ["USER"], "type": token_type}, secret, algorithm="HS256")
    return {"X-User-ID": user_id, "Authorization": f"Bearer {token}"}


def _index(mock_meilisearch_client: MagicMock) -> MagicMock:
    return mock_meilisearch_client.index.return_value


def _search_filters(mock_meilisearch_client: MagicMock) -> list[str]:
    return [str(c.args[1].get("filter")) for c in _index(mock_meilisearch_client).search.call_args_list]


class TestSuggestScoping:
    def test_suggest_is_filtered_to_caller(self, auth_client, mock_meilisearch_client, jwt_secret):
        response = auth_client.get("/api/v1/search/suggest?q=acq", headers=_user(ATTACKER, jwt_secret))
        assert response.status_code == 200
        filters = _search_filters(mock_meilisearch_client)
        assert filters and all(f == f'owner_id = "{ATTACKER}"' for f in filters)

    def test_owner_still_gets_own_suggestions(self, auth_client, mock_meilisearch_client, jwt_secret):
        _index(mock_meilisearch_client).search.side_effect = [
            {"hits": [{"title": "Acquisition plan"}]},
            {"hits": []},
        ]
        response = auth_client.get("/api/v1/search/suggest?q=acq", headers=_user(OWNER, jwt_secret))
        assert response.get_json()["suggestions"] == ["Acquisition plan"]
        assert all(OWNER in f for f in _search_filters(mock_meilisearch_client))


class TestIndexWriteOwnership:
    @pytest.mark.parametrize("kind,body", [
        ("document", {"id": "d-1", "title": "Reset password"}),
        ("file", {"id": "f-1", "name": "payroll.xlsx"}),
    ])
    def test_user_cannot_index_into_another_users_space(
        self, auth_client, mock_meilisearch_client, jwt_secret, kind, body
    ):
        response = auth_client.post(
            f"/api/v1/search/index/{kind}",
            json={**body, "owner_id": OWNER},
            headers=_user(ATTACKER, jwt_secret),
        )
        assert response.status_code == 403
        _index(mock_meilisearch_client).add_documents.assert_not_called()

    def test_user_cannot_overwrite_another_users_entry(self, auth_client, mock_meilisearch_client, jwt_secret):
        _index(mock_meilisearch_client).get_document.return_value = {"id": "d-1", "owner_id": OWNER}
        response = auth_client.post(
            "/api/v1/search/index/document",
            json={"id": "d-1", "title": "Hijacked"},
            headers=_user(ATTACKER, jwt_secret),
        )
        assert response.status_code == 403
        _index(mock_meilisearch_client).add_documents.assert_not_called()

    @pytest.mark.parametrize("body_owner", [OWNER, None])
    def test_owner_indexes_own_entry(self, auth_client, mock_meilisearch_client, jwt_secret, body_owner):
        _index(mock_meilisearch_client).get_document.side_effect = _not_found()
        body = {"id": "d-1", "title": "Roadmap"}
        if body_owner:
            body["owner_id"] = body_owner
        response = auth_client.post("/api/v1/search/index/document", json=body, headers=_user(OWNER, jwt_secret))
        assert response.status_code == 201
        assert _index(mock_meilisearch_client).add_documents.call_args.args[0][0]["owner_id"] == OWNER

    def test_owner_reindexes_existing_entry(self, auth_client, mock_meilisearch_client, jwt_secret):
        _index(mock_meilisearch_client).get_document.return_value = {"id": "f-1", "owner_id": OWNER}
        response = auth_client.post(
            "/api/v1/search/index/file", json={"id": "f-1", "name": "v2.txt"}, headers=_user(OWNER, jwt_secret)
        )
        assert response.status_code == 201

    def test_service_token_may_index_for_any_owner(self, auth_client, mock_meilisearch_client, service_token):
        response = auth_client.post(
            "/api/v1/search/index/document",
            json={"id": "d-1", "title": "From document-service", "owner_id": OWNER},
            headers={"Authorization": f"Bearer {service_token}"},
        )
        assert response.status_code == 201
        assert _index(mock_meilisearch_client).add_documents.call_args.args[0][0]["owner_id"] == OWNER

    def test_admin_may_index_for_any_owner(self, auth_client, mock_meilisearch_client, jwt_secret):
        response = auth_client.post(
            "/api/v1/search/index/document",
            json={"id": "d-1", "title": "Restored", "owner_id": OWNER},
            headers=_user(ADMIN, jwt_secret, roles=["ADMIN", "USER"]),
        )
        assert response.status_code == 201


class TestDeleteOwnership:
    def test_user_cannot_delete_another_users_entry(self, auth_client, mock_meilisearch_client, jwt_secret):
        _index(mock_meilisearch_client).get_document.return_value = {"id": "f-1", "owner_id": OWNER}
        response = auth_client.delete("/api/v1/search/index/file/f-1", headers=_user(ATTACKER, jwt_secret))
        assert response.status_code == 404
        _index(mock_meilisearch_client).delete_document.assert_not_called()

    def test_owner_deletes_own_entry(self, auth_client, mock_meilisearch_client, jwt_secret):
        _index(mock_meilisearch_client).get_document.return_value = {"id": "f-1", "owner_id": OWNER}
        response = auth_client.delete("/api/v1/search/index/file/f-1", headers=_user(OWNER, jwt_secret))
        assert response.status_code == 200
        _index(mock_meilisearch_client).delete_document.assert_called_once_with("f-1")

    def test_admin_deletes_any_entry(self, auth_client, mock_meilisearch_client, jwt_secret):
        _index(mock_meilisearch_client).get_document.return_value = {"id": "f-1", "owner_id": OWNER}
        response = auth_client.delete(
            "/api/v1/search/index/file/f-1", headers=_user(ADMIN, jwt_secret, roles=["ADMIN"])
        )
        assert response.status_code == 200

    def test_invalid_type_is_still_400(self, auth_client, jwt_secret):
        response = auth_client.delete("/api/v1/search/index/folder/x", headers=_user(OWNER, jwt_secret))
        assert response.status_code == 400


class TestAdminOnlyRoutes:
    @pytest.mark.parametrize("method,path", [("post", "/api/v1/search/reindex"), ("get", "/api/v1/search/analytics")])
    def test_regular_user_is_forbidden(self, auth_client, mock_meilisearch_client, jwt_secret, method, path):
        response = getattr(auth_client, method)(path, headers=_user(OWNER, jwt_secret))
        assert response.status_code == 403
        mock_meilisearch_client.delete_index.assert_not_called()

    @pytest.mark.parametrize("headers", [
        pytest.param(lambda s: {"X-User-ID": ADMIN}, id="no-token"),
        pytest.param(lambda s: _user(ADMIN, secrets.token_hex(32), roles=["ADMIN"]), id="forged-signature"),
        pytest.param(lambda s: _user(ADMIN, s, roles=["ADMIN"], token_type="refresh"), id="refresh-token"),
        pytest.param(lambda s: {**_user(ADMIN, s, roles=["ADMIN"]), "X-User-ID": OWNER}, id="other-users-token"),
    ])
    def test_admin_claim_must_be_verified(self, auth_client, jwt_secret, headers):
        response = auth_client.get("/api/v1/search/analytics", headers=headers(jwt_secret))
        assert response.status_code == 403

    def test_admin_can_read_analytics(self, auth_client, jwt_secret):
        response = auth_client.get("/api/v1/search/analytics", headers=_user(ADMIN, jwt_secret, roles=["ADMIN"]))
        assert response.status_code == 200

    def test_admin_can_reindex(self, auth_client, jwt_secret):
        with patch("app.services.indexer.Indexer._fetch_all_documents", return_value=[]), \
             patch("app.services.indexer.Indexer._fetch_all_files", return_value=[]):
            response = auth_client.post("/api/v1/search/reindex", headers=_user(ADMIN, jwt_secret, roles=["ADMIN"]))
        assert response.status_code == 200

    def test_service_token_can_reindex(self, auth_client, service_token):
        with patch("app.services.indexer.Indexer._fetch_all_documents", return_value=[]), \
             patch("app.services.indexer.Indexer._fetch_all_files", return_value=[]):
            response = auth_client.post(
                "/api/v1/search/reindex", headers={"Authorization": f"Bearer {service_token}"}
            )
        assert response.status_code == 200
