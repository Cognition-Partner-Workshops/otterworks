"""Regression tests for search-service authentication and tenant scoping.

A bare client-supplied ``X-User-ID`` must never authenticate a request or
select whose data is returned; identity comes only from a verified JWT or
from a caller holding the service token.
"""

from __future__ import annotations

import secrets
import time
from unittest.mock import MagicMock, patch

import jwt
import pytest

from app.config import AppConfig, AuthConfig, MeiliSearchConfig, SQSConfig
from app.main import create_app

# Generated per run so no literal secrets live in the repo.
JWT_SECRET = secrets.token_hex(32)
PEER_SECRET = secrets.token_hex(32)
WRONG_SECRET = secrets.token_hex(32)
SERVICE_TOKEN = secrets.token_hex(16)
VICTIM = "11111111-1111-1111-1111-111111111111"
ATTACKER = "22222222-2222-2222-2222-222222222222"


def _token(sub: str | None = ATTACKER, secret: str = JWT_SECRET, **extra) -> str:
    claims = {"exp": int(time.time()) + 300, **extra}
    if sub is not None:
        claims["sub"] = sub
    return jwt.encode(claims, secret, algorithm="HS256")


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def secure_client(mock_meilisearch_client: MagicMock):
    config = AppConfig(
        meilisearch=MeiliSearchConfig(url="http://localhost:7700", api_key=""),
        sqs=SQSConfig(enabled=False),
        auth=AuthConfig(
            service_token=SERVICE_TOKEN,
            require_auth=True,
            jwt_secret=JWT_SECRET,
            jwt_peer_secret=PEER_SECRET,
        ),
    )
    with patch("app.services.meilisearch_client.meilisearch.Client") as mock_cls:
        mock_cls.return_value = mock_meilisearch_client
        flask_app = create_app(config)
        flask_app.config["TESTING"] = True
        yield flask_app.test_client()


def _filters(mock_meilisearch_client: MagicMock) -> list[str]:
    index = mock_meilisearch_client.index.return_value
    return [c.args[1].get("filter", "") for c in index.search.call_args_list]


class TestBareHeaderRejected:
    @pytest.mark.parametrize(
        ("method", "path", "body"),
        [
            ("get", "/api/v1/search/?q=secret", None),
            ("get", "/api/v1/search/suggest?q=se", None),
            ("post", "/api/v1/search/advanced", {"q": "secret"}),
            ("get", "/api/v1/search/analytics", None),
            ("post", "/api/v1/search/index/document", {"id": "d1", "title": "x", "owner_id": VICTIM}),
            ("post", "/api/v1/search/index/file", {"id": "f1", "name": "x", "owner_id": VICTIM}),
            ("delete", "/api/v1/search/index/document/d1", None),
            ("post", "/api/v1/search/reindex", None),
        ],
    )
    def test_spoofed_x_user_id_without_token_is_401(
        self, secure_client, mock_meilisearch_client, method, path, body
    ):
        response = getattr(secure_client, method)(path, json=body, headers={"X-User-ID": VICTIM})
        assert response.status_code == 401
        mock_meilisearch_client.index.return_value.search.assert_not_called()
        mock_meilisearch_client.index.return_value.add_documents.assert_not_called()
        mock_meilisearch_client.delete_index.assert_not_called()

    def test_no_credentials_is_401(self, secure_client):
        assert secure_client.get("/api/v1/search/?q=x").status_code == 401

    @pytest.mark.parametrize(
        "token",
        [
            _token(secret=WRONG_SECRET),
            _token(exp=int(time.time()) - 60),
            _token(sub=None),
            jwt.encode({"sub": ATTACKER}, key=None, algorithm="none"),
            "not-a-jwt",
            SERVICE_TOKEN + "x",
        ],
        ids=["bad-signature", "expired", "no-subject", "alg-none", "garbage", "wrong-service-token"],
    )
    def test_invalid_bearer_is_401(self, secure_client, token):
        response = secure_client.get(
            "/api/v1/search/?q=x", headers={**_bearer(token), "X-User-ID": VICTIM}
        )
        assert response.status_code == 401

    def test_health_and_metrics_stay_public(self, secure_client):
        assert secure_client.get("/health").status_code == 200
        assert secure_client.get("/metrics").status_code == 200


class TestJwtScoping:
    def test_search_scoped_to_jwt_subject_not_header(self, secure_client, mock_meilisearch_client):
        response = secure_client.get(
            "/api/v1/search/?q=secret", headers={**_bearer(_token(ATTACKER)), "X-User-ID": VICTIM}
        )
        assert response.status_code == 200
        filters = _filters(mock_meilisearch_client)
        assert filters and all(f'owner_id = "{ATTACKER}"' in f for f in filters)
        assert not any(VICTIM in f for f in filters)

    def test_advanced_search_scoped_to_jwt_subject(self, secure_client, mock_meilisearch_client):
        response = secure_client.post(
            "/api/v1/search/advanced",
            json={"q": "secret", "owner_id": VICTIM},
            headers={**_bearer(_token(ATTACKER)), "X-User-ID": VICTIM},
        )
        assert response.status_code == 200
        filters = _filters(mock_meilisearch_client)
        assert filters and all(f'owner_id = "{ATTACKER}"' in f for f in filters)
        assert not any(VICTIM in f for f in filters)

    def test_suggest_scoped_to_jwt_subject(self, secure_client, mock_meilisearch_client):
        response = secure_client.get(
            "/api/v1/search/suggest?q=se", headers={**_bearer(_token(ATTACKER)), "X-User-ID": VICTIM}
        )
        assert response.status_code == 200
        filters = _filters(mock_meilisearch_client)
        assert filters and all(f == f'owner_id = "{ATTACKER}"' for f in filters)

    def test_user_id_claim_fallback(self, secure_client, mock_meilisearch_client):
        token = _token(sub=None, user_id=ATTACKER)
        assert secure_client.get("/api/v1/search/?q=x", headers=_bearer(token)).status_code == 200
        assert all(f'owner_id = "{ATTACKER}"' in f for f in _filters(mock_meilisearch_client))

    def test_peer_secret_token_accepted(self, secure_client, mock_meilisearch_client):
        token = _token(ATTACKER, secret=PEER_SECRET)
        assert secure_client.get("/api/v1/search/?q=x", headers=_bearer(token)).status_code == 200


class TestServiceToken:
    def test_service_token_may_assert_identity(self, secure_client, mock_meilisearch_client):
        response = secure_client.get(
            "/api/v1/search/?q=x", headers={**_bearer(SERVICE_TOKEN), "X-User-ID": VICTIM}
        )
        assert response.status_code == 200
        assert all(f'owner_id = "{VICTIM}"' in f for f in _filters(mock_meilisearch_client))

    def test_service_token_reaches_index_endpoints(self, secure_client):
        response = secure_client.post(
            "/api/v1/search/index/document",
            json={"id": "d1", "title": "t", "owner_id": VICTIM},
            headers=_bearer(SERVICE_TOKEN),
        )
        assert response.status_code == 201


def test_without_jwt_secret_user_requests_fail_closed(mock_meilisearch_client):
    config = AppConfig(
        sqs=SQSConfig(enabled=False),
        auth=AuthConfig(service_token="", require_auth=True, jwt_secret="", jwt_peer_secret=""),
    )
    with patch("app.services.meilisearch_client.meilisearch.Client") as mock_cls:
        mock_cls.return_value = mock_meilisearch_client
        client = create_app(config).test_client()
    unverifiable = _token(ATTACKER, secret=WRONG_SECRET)
    assert client.get("/api/v1/search/?q=x", headers={"X-User-ID": VICTIM}).status_code == 401
    assert client.get("/api/v1/search/?q=x", headers=_bearer(unverifiable)).status_code == 401
