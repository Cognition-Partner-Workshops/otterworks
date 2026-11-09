"""Tests for the gateway-attestation auth middleware."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.config import AppConfig, AuthConfig, MeiliSearchConfig, SQSConfig
from app.main import create_app
from app.middleware.auth import sign_identity, verify_gateway_identity

INTERNAL_SECRET = "test-internal-auth-secret"
SERVICE_TOKEN = "test-service-token"
VICTIM = "11111111-1111-4111-8111-111111111111"


@pytest.fixture()
def secured_client(mock_meilisearch_client: MagicMock):
    """A client against an app with auth enabled and both credentials configured."""
    config = AppConfig(
        meilisearch=MeiliSearchConfig(url="http://localhost:7700", api_key=""),
        sqs=SQSConfig(enabled=False),
        auth=AuthConfig(
            service_token=SERVICE_TOKEN,
            internal_auth_secret=INTERNAL_SECRET,
            require_auth=True,
        ),
    )
    with patch("app.services.meilisearch_client.meilisearch.Client") as mock_cls:
        mock_cls.return_value = mock_meilisearch_client
        flask_app = create_app(config)
        flask_app.config["TESTING"] = True
        yield flask_app.test_client()


@pytest.fixture()
def unconfigured_client(mock_meilisearch_client: MagicMock):
    """Auth enabled but INTERNAL_AUTH_SECRET unset: the identity path must fail closed."""
    config = AppConfig(
        meilisearch=MeiliSearchConfig(url="http://localhost:7700", api_key=""),
        sqs=SQSConfig(enabled=False),
        auth=AuthConfig(service_token="", internal_auth_secret="", require_auth=True),
    )
    with patch("app.services.meilisearch_client.meilisearch.Client") as mock_cls:
        mock_cls.return_value = mock_meilisearch_client
        flask_app = create_app(config)
        flask_app.config["TESTING"] = True
        yield flask_app.test_client()


def gateway_headers(user_id: str, secret: str = INTERNAL_SECRET) -> dict[str, str]:
    return {"X-User-ID": user_id, "X-Gateway-Signature": sign_identity(secret, user_id)}


class TestVerifyGatewayIdentity:
    def test_round_trip(self):
        assert verify_gateway_identity(INTERNAL_SECRET, VICTIM, sign_identity(INTERNAL_SECRET, VICTIM))

    def test_rejects_other_key_or_user(self):
        assert not verify_gateway_identity(INTERNAL_SECRET, VICTIM, sign_identity("other", VICTIM))
        assert not verify_gateway_identity(INTERNAL_SECRET, VICTIM, sign_identity(INTERNAL_SECRET, "x"))

    def test_rejects_empty_inputs(self):
        sig = sign_identity(INTERNAL_SECRET, VICTIM)
        assert not verify_gateway_identity("", VICTIM, sig)
        assert not verify_gateway_identity(INTERNAL_SECRET, "", sig)
        assert not verify_gateway_identity(INTERNAL_SECRET, VICTIM, "")


class TestGatewayAttestation:
    """The previously exploitable requests: a bare X-User-ID straight at the service."""

    def test_public_paths_open(self, secured_client):
        assert secured_client.get("/health").status_code == 200
        assert secured_client.get("/metrics").status_code == 200

    def test_no_identity_rejected(self, secured_client):
        response = secured_client.get("/api/v1/search/?q=test")
        assert response.status_code == 401
        assert response.get_json() == {"error": "unauthorized"}

    def test_bare_x_user_id_rejected(self, secured_client):
        response = secured_client.get("/api/v1/search/?q=test", headers={"X-User-ID": VICTIM})
        assert response.status_code == 401

    def test_forged_signature_rejected(self, secured_client):
        response = secured_client.get(
            "/api/v1/search/?q=test", headers=gateway_headers(VICTIM, secret="attacker-key")
        )
        assert response.status_code == 401

    def test_signature_for_other_user_rejected(self, secured_client):
        headers = gateway_headers("22222222-2222-4222-8222-222222222222")
        headers["X-User-ID"] = VICTIM
        response = secured_client.get("/api/v1/search/?q=test", headers=headers)
        assert response.status_code == 401

    def test_internal_endpoints_need_attestation_too(self, secured_client):
        response = secured_client.post("/api/v1/search/reindex", headers={"X-User-ID": VICTIM})
        assert response.status_code == 401

    def test_gateway_signed_identity_accepted(self, secured_client, mock_meilisearch_client):
        mock_meilisearch_client.index.return_value.search.return_value = {
            "estimatedTotalHits": 0,
            "hits": [],
        }
        response = secured_client.get("/api/v1/search/?q=test", headers=gateway_headers(VICTIM))
        assert response.status_code == 200
        search_kwargs = mock_meilisearch_client.index.return_value.search.call_args
        assert f'owner_id = "{VICTIM}"' in str(search_kwargs)


class TestServiceToken:
    def test_valid_token_accepted(self, secured_client, mock_meilisearch_client):
        response = secured_client.post(
            "/api/v1/search/reindex", headers={"Authorization": f"Bearer {SERVICE_TOKEN}"}
        )
        assert response.status_code != 401

    def test_wrong_token_rejected(self, secured_client):
        response = secured_client.get(
            "/api/v1/search/?q=test", headers={"Authorization": "Bearer nope"}
        )
        assert response.status_code == 401


class TestFailClosed:
    def test_identity_rejected_when_secret_unconfigured(self, unconfigured_client):
        response = unconfigured_client.get(
            "/api/v1/search/?q=test", headers={"X-User-ID": VICTIM}
        )
        assert response.status_code == 401
