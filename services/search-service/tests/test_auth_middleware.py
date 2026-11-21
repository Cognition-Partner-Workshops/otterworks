"""Tests for JWT authentication middleware."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt
import pytest

from app.config import AppConfig, AuthConfig, MeiliSearchConfig, SQSConfig
from app.main import create_app

TEST_SECRET = "search-service-test-jwt-secret"
SERVICE_TOKEN = "search-service-internal-test-token"
VICTIM_ID = "victim-user-id"
ATTACKER_ID = "attacker-user-id"


def _token(claims: dict, secret: str = TEST_SECRET) -> str:
    return jwt.encode(claims, secret, algorithm="HS384")


def _auth_app(
    mock_meilisearch_client: MagicMock,
    *,
    service_token: str = "",
    jwt_secret: str = TEST_SECRET,
):
    config = AppConfig(
        service_name="search-service-auth-test",
        meilisearch=MeiliSearchConfig(
            url="http://localhost:7700",
            api_key="",
            documents_index="test-otterworks-documents",
            files_index="test-otterworks-files",
        ),
        sqs=SQSConfig(enabled=False),
        auth=AuthConfig(
            service_token=service_token,
            jwt_secret=jwt_secret,
            require_auth=True,
        ),
    )
    with patch("app.services.meilisearch_client.meilisearch.Client") as mock_cls:
        mock_cls.return_value = mock_meilisearch_client
        flask_app = create_app(config)
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture()
def auth_app(mock_meilisearch_client: MagicMock):
    """Create an auth-enabled Flask app with mocked MeiliSearch."""
    return _auth_app(mock_meilisearch_client)


@pytest.fixture()
def auth_client(auth_app):
    """Create an auth-enabled Flask test client."""
    return auth_app.test_client()


def _valid_claims(subject: str = ATTACKER_ID) -> dict:
    return {
        "sub": subject,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }


def test_rejects_spoofed_x_user_id_without_jwt(auth_client):
    response = auth_client.get(
        "/api/v1/search/?q=private&type=document",
        headers={"X-User-ID": VICTIM_ID},
    )
    assert response.status_code == 401


def test_rejects_request_without_credentials(auth_client):
    response = auth_client.get("/api/v1/search/?q=private&type=document")
    assert response.status_code == 401


@pytest.mark.parametrize(
    "token",
    [
        "not-a-jwt",
        _token(_valid_claims(), secret="different-test-secret"),
        _token({"exp": datetime.now(timezone.utc) + timedelta(hours=1)}),
    ],
    ids=["garbage-token", "wrong-signing-secret", "missing-subject"],
)
def test_rejects_invalid_or_unidentified_jwt(auth_client, token):
    response = auth_client.get(
        "/api/v1/search/?q=private&type=document",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


def test_valid_jwt_search_succeeds(auth_client, mock_meilisearch_client):
    mock_index = mock_meilisearch_client.index.return_value
    mock_index.search.return_value = {"hits": [], "estimatedTotalHits": 0}

    response = auth_client.get(
        "/api/v1/search/?q=private&type=document",
        headers={"Authorization": f"Bearer {_token(_valid_claims())}"},
    )

    assert response.status_code == 200
    assert response.get_json()["query"] == "private"
    mock_index.search.assert_called_once()


def test_valid_jwt_ignores_spoofed_x_user_id_for_search_scope(
    auth_client,
    mock_meilisearch_client,
):
    mock_index = mock_meilisearch_client.index.return_value
    mock_index.search.return_value = {"hits": [], "estimatedTotalHits": 0}

    response = auth_client.get(
        "/api/v1/search/?q=private&type=document",
        headers={
            "Authorization": f"Bearer {_token(_valid_claims())}",
            "X-User-ID": VICTIM_ID,
        },
    )

    assert response.status_code == 200
    search_params = mock_index.search.call_args.args[1]
    assert search_params["filter"] == f'type = "document" AND owner_id = "{ATTACKER_ID}"'
    assert VICTIM_ID not in search_params["filter"]


def test_missing_jwt_secret_fails_closed_but_health_remains_public(
    mock_meilisearch_client,
):
    client = _auth_app(mock_meilisearch_client, jwt_secret="").test_client()

    protected = client.get("/api/v1/search/?q=private&type=document")
    health = client.get("/health")

    assert protected.status_code == 503
    assert protected.get_json() == {
        "error": "service unavailable: authentication is not configured"
    }
    assert health.status_code == 200


def test_configured_service_token_is_accepted(mock_meilisearch_client):
    client = _auth_app(
        mock_meilisearch_client,
        service_token=SERVICE_TOKEN,
        jwt_secret="",
    ).test_client()

    response = client.get(
        "/api/v1/search/?q=private&type=document",
        headers={"Authorization": f"Bearer {SERVICE_TOKEN}"},
    )

    assert response.status_code == 200
