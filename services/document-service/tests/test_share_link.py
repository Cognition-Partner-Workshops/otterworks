"""Tests for read-only share-link tokens."""

import hashlib
import uuid

import pytest

from app.main import app, lifespan
from app.services.share_link import ShareLinkSecretError, ShareLinkService

DOC_ID = "11111111-1111-4111-8111-111111111111"


@pytest.fixture
def service():
    return ShareLinkService(secret="share-link-test-key")


def test_minted_token_verifies(service):
    assert service.verify_token(DOC_ID, service.mint_token(DOC_ID)) is True


def test_token_is_stable_across_calls(service):
    assert service.mint_token(DOC_ID) == service.mint_token(DOC_ID)


def test_token_of_another_document_is_rejected(service):
    other = "22222222-2222-4222-8222-222222222222"
    assert service.verify_token(DOC_ID, service.mint_token(other)) is False


def test_garbage_token_is_rejected(service):
    assert service.verify_token(DOC_ID, "not-a-token") is False


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


def _legacy_default_salt_token(document_id: str) -> str:
    """The token the old unkeyed scheme derived from the id and the public salt."""
    return hashlib.md5(
        f"{document_id}:otterworks-share".encode(), usedforsecurity=False
    ).hexdigest()[:16]


def test_token_depends_on_the_secret():
    assert ShareLinkService(secret="share-link-key-one").mint_token(DOC_ID) != ShareLinkService(
        secret="share-link-key-two"
    ).mint_token(DOC_ID)


def test_legacy_default_salt_token_is_rejected():
    assert ShareLinkService().verify_token(DOC_ID, _legacy_default_salt_token(DOC_ID)) is False


def test_missing_secret_is_refused(monkeypatch):
    monkeypatch.delenv("SHARE_LINK_SECRET", raising=False)
    with pytest.raises(ShareLinkSecretError):
        ShareLinkService()


@pytest.mark.parametrize("secret", ["", "otterworks-share", "short"])
def test_public_or_weak_secret_is_refused(monkeypatch, secret):
    monkeypatch.setenv("SHARE_LINK_SECRET", secret)
    with pytest.raises(ShareLinkSecretError):
        ShareLinkService()


@pytest.mark.asyncio
async def test_startup_fails_without_secret(monkeypatch):
    monkeypatch.delenv("SHARE_LINK_SECRET", raising=False)
    with pytest.raises(ShareLinkSecretError):
        async with lifespan(app):
            pass


@pytest.mark.asyncio
async def test_share_endpoint_rejects_legacy_default_salt_token(
    client, owner_id: uuid.UUID, monkeypatch
):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    created = await client.post(
        "/api/v1/documents/",
        json={"title": "Private", "content": "secret body", "owner_id": str(owner_id)},
    )
    doc_id = created.json()["id"]

    forged = await client.get(
        "/api/v1/documents/shared",
        params={"document_id": doc_id, "token": _legacy_default_salt_token(doc_id)},
    )
    assert forged.status_code == 403
    assert "secret body" not in forged.text
