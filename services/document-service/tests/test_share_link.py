"""Tests for read-only share-link tokens."""

import hashlib
import uuid

import pytest

from app.services.share_link import ShareLinkSecretMissingError, ShareLinkService

DOC_ID = "11111111-1111-4111-8111-111111111111"
TEST_SECRET = "test-share-link-secret-0123456789"


@pytest.fixture
def service():
    return ShareLinkService(secret=TEST_SECRET)


@pytest.fixture(autouse=True)
def share_link_secret(monkeypatch):
    monkeypatch.setenv("SHARE_LINK_SECRET", TEST_SECRET)


def test_minted_token_verifies(service):
    assert service.verify_token(DOC_ID, service.mint_token(DOC_ID)) is True


def test_token_is_stable_across_calls(service):
    assert service.mint_token(DOC_ID) == service.mint_token(DOC_ID)


def test_token_of_another_document_is_rejected(service):
    other = "22222222-2222-4222-8222-222222222222"
    assert service.verify_token(DOC_ID, service.mint_token(other)) is False


def test_garbage_token_is_rejected(service):
    assert service.verify_token(DOC_ID, "not-a-token") is False


def test_non_ascii_token_is_rejected(service):
    assert service.verify_token(DOC_ID, "tökén") is False


def test_offline_md5_derivation_is_rejected(service):
    """An attacker who reads the source must not be able to derive a token.

    Before the fix the token was ``md5(f"{document_id}:otterworks-share")[:16]``,
    computable by anyone who knows the document id.
    """
    for salt in ("otterworks-share", ""):
        forged = hashlib.md5(
            f"{DOC_ID}:{salt}".encode(), usedforsecurity=False
        ).hexdigest()[:16]
        assert service.verify_token(DOC_ID, forged) is False


def test_token_is_not_derivable_without_the_secret():
    minted = ShareLinkService(secret=TEST_SECRET).mint_token(DOC_ID)
    other_key = ShareLinkService(secret="a-different-secret-0123456789").mint_token(DOC_ID)
    assert minted != other_key
    assert ShareLinkService(secret="a-different-secret-0123456789").verify_token(
        DOC_ID, minted
    ) is False


def test_missing_secret_is_rejected(monkeypatch):
    monkeypatch.delenv("SHARE_LINK_SECRET", raising=False)
    with pytest.raises(ShareLinkSecretMissingError):
        ShareLinkService()


def test_short_secret_is_rejected(monkeypatch):
    monkeypatch.setenv("SHARE_LINK_SECRET", "short")
    with pytest.raises(ShareLinkSecretMissingError):
        ShareLinkService()


def test_default_salt_is_not_used_as_a_key(monkeypatch):
    """SHARE_LINK_SALT (the old, source-visible knob) must not key tokens."""
    monkeypatch.delenv("SHARE_LINK_SECRET", raising=False)
    monkeypatch.setenv("SHARE_LINK_SALT", "otterworks-share")
    with pytest.raises(ShareLinkSecretMissingError):
        ShareLinkService()


@pytest.mark.asyncio
async def test_share_endpoint_round_trip(client, owner_id: uuid.UUID, monkeypatch):
    # tests/test_documents_api.py sets JWT_SECRET at import time, which switches the
    # app off the X-User-ID fallback for the whole session. Drop it here so the
    # identity path this test exercises is the same whichever tests ran first.
    monkeypatch.delenv("JWT_SECRET", raising=False)
    created = await client.post(
        "/api/v1/documents/",
        json={"title": "Shared", "content": "body", "owner_id": str(owner_id)},
    )
    doc_id = created.json()["id"]
    headers = {"Authorization": "Bearer token", "X-User-ID": str(owner_id)}

    minted = await client.post(f"/api/v1/documents/{doc_id}/share", headers=headers)
    assert minted.status_code == 200
    token = minted.json()["token"]

    shared = await client.get(
        "/api/v1/documents/shared", params={"document_id": doc_id, "token": token}
    )
    assert shared.status_code == 200
    assert shared.json()["id"] == doc_id

    denied = await client.get(
        "/api/v1/documents/shared", params={"document_id": doc_id, "token": "wrong"}
    )
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_shared_endpoint_rejects_offline_md5_token(client, owner_id: uuid.UUID):
    created = await client.post(
        "/api/v1/documents/",
        json={"title": "Private", "content": "secret body", "owner_id": str(owner_id)},
    )
    doc_id = created.json()["id"]
    forged = hashlib.md5(
        f"{doc_id}:otterworks-share".encode(), usedforsecurity=False
    ).hexdigest()[:16]

    response = await client.get(
        "/api/v1/documents/shared", params={"document_id": doc_id, "token": forged}
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_share_endpoints_fail_closed_without_secret(
    client, owner_id: uuid.UUID, monkeypatch
):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("SHARE_LINK_SECRET", raising=False)
    created = await client.post(
        "/api/v1/documents/",
        json={"title": "Unconfigured", "content": "body", "owner_id": str(owner_id)},
    )
    doc_id = created.json()["id"]
    headers = {"Authorization": "Bearer token", "X-User-ID": str(owner_id)}

    minted = await client.post(f"/api/v1/documents/{doc_id}/share", headers=headers)
    assert minted.status_code == 503

    shared = await client.get(
        "/api/v1/documents/shared", params={"document_id": doc_id, "token": "anything"}
    )
    assert shared.status_code == 503
