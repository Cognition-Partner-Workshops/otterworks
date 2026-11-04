"""Tests for read-only share-link tokens."""

import hashlib
import uuid

import pytest

from app.services.share_link import ShareLinkConfigError, ShareLinkService

DOC_ID = "11111111-1111-4111-8111-111111111111"
TEST_SECRET = "test-share-link-secret"


@pytest.fixture
def service():
    return ShareLinkService(secret=TEST_SECRET)


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
    assert service.verify_token(DOC_ID, "t\u00f6ken") is False


def test_missing_secret_is_refused(monkeypatch):
    monkeypatch.delenv("SHARE_LINK_SECRET", raising=False)
    with pytest.raises(ShareLinkConfigError):
        ShareLinkService()


def test_token_from_another_secret_is_rejected(service):
    other = ShareLinkService(secret="a-different-secret")
    assert service.verify_token(DOC_ID, other.mint_token(DOC_ID)) is False


@pytest.mark.parametrize("salt", ["otterworks-share", TEST_SECRET])
def test_legacy_md5_token_is_rejected(service, salt):
    # nosemgrep: python.lang.security.insecure-hash-algorithms-md5.insecure-hash-algorithm-md5
    legacy = hashlib.md5(f"{DOC_ID}:{salt}".encode(), usedforsecurity=False).hexdigest()
    assert service.verify_token(DOC_ID, legacy[:16]) is False
    assert service.verify_token(DOC_ID, legacy) is False


@pytest.mark.asyncio
async def test_share_endpoint_round_trip(client, owner_id: uuid.UUID, monkeypatch):
    # tests/test_documents_api.py sets JWT_SECRET at import time, which switches the
    # app off the X-User-ID fallback for the whole session. Drop it here so the
    # identity path this test exercises is the same whichever tests ran first.
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.setenv("SHARE_LINK_SECRET", TEST_SECRET)
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
async def test_share_endpoint_rejects_offline_md5_forgery(client, owner_id: uuid.UUID, monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.setenv("SHARE_LINK_SECRET", TEST_SECRET)
    created = await client.post(
        "/api/v1/documents/",
        json={"title": "Never shared", "content": "body", "owner_id": str(owner_id)},
    )
    doc_id = created.json()["id"]
    # nosemgrep: python.lang.security.insecure-hash-algorithms-md5.insecure-hash-algorithm-md5
    forged = hashlib.md5(f"{doc_id}:otterworks-share".encode(), usedforsecurity=False).hexdigest()[
        :16
    ]

    response = await client.get(
        "/api/v1/documents/shared", params={"document_id": doc_id, "token": forged}
    )
    assert response.status_code == 403
