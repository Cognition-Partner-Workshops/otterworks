"""Tests for read-only share-link tokens."""

import hashlib
import uuid

import pytest

from app.services.share_link import ShareLinkService

DOC_ID = "11111111-1111-4111-8111-111111111111"


@pytest.fixture
def service():
    return ShareLinkService(salt="test-salt")


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
    monkeypatch.setenv("SHARE_LINK_SECRET", "endpoint-test-secret")
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


def test_token_cannot_be_derived_from_public_inputs(monkeypatch):
    monkeypatch.setenv("SHARE_LINK_SECRET", "deployment-secret")
    monkeypatch.delenv("SHARE_LINK_SALT", raising=False)
    service = ShareLinkService()
    for salt in ("otterworks-share", "deployment-secret"):
        digest = hashlib.md5(f"{DOC_ID}:{salt}".encode(), usedforsecurity=False).hexdigest()
        for length in (16, 32):
            assert service.verify_token(DOC_ID, digest[:length]) is False


def test_token_depends_on_the_secret():
    assert ShareLinkService(secret="one").mint_token(DOC_ID) != ShareLinkService(
        secret="two"
    ).mint_token(DOC_ID)


def test_unconfigured_service_fails_closed(monkeypatch):
    monkeypatch.delenv("SHARE_LINK_SECRET", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.setenv("SHARE_LINK_SALT", "otterworks-share")
    service = ShareLinkService()
    forged = hashlib.md5(f"{DOC_ID}:otterworks-share".encode(), usedforsecurity=False).hexdigest()
    assert service.verify_token(DOC_ID, forged[:16]) is False
    with pytest.raises(RuntimeError):
        service.mint_token(DOC_ID)
