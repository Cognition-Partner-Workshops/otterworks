"""Tests for read-only share-link tokens."""

import hashlib
import uuid

import pytest

from app.services.share_link import ShareLinkService
from tests.conftest import auth_headers

DOC_ID = "11111111-1111-4111-8111-111111111111"


@pytest.fixture
def service():
    return ShareLinkService(secret="test-secret")


def test_minted_token_verifies(service):
    assert service.verify_token(DOC_ID, service.mint_token(DOC_ID)) is True


def test_token_is_stable_across_calls(service):
    assert service.mint_token(DOC_ID) == service.mint_token(DOC_ID)


def test_token_of_another_document_is_rejected(service):
    other = "22222222-2222-4222-8222-222222222222"
    assert service.verify_token(DOC_ID, service.mint_token(other)) is False


def test_garbage_token_is_rejected(service):
    assert service.verify_token(DOC_ID, "not-a-token") is False
    assert service.verify_token(DOC_ID, "n\u00f6n-ascii") is False


def test_token_depends_on_the_secret(service):
    assert (
        ShareLinkService(secret="other-secret").verify_token(DOC_ID, service.mint_token(DOC_ID))
        is False
    )


def test_legacy_md5_token_is_rejected(service):
    # nosemgrep: python.lang.security.insecure-hash-algorithms-md5.insecure-hash-algorithm-md5
    forged = hashlib.md5(f"{DOC_ID}:otterworks-share".encode()).hexdigest()[:16]  # noqa: S324
    assert service.verify_token(DOC_ID, forged) is False


def test_missing_secret_is_refused(monkeypatch):
    monkeypatch.delenv("SHARE_LINK_SECRET", raising=False)
    with pytest.raises(RuntimeError):
        ShareLinkService()


@pytest.mark.asyncio
async def test_share_endpoint_round_trip(client, owner_id: uuid.UUID):
    created = await client.post(
        "/api/v1/documents/",
        json={"title": "Shared", "content": "body", "owner_id": str(owner_id)},
    )
    doc_id = created.json()["id"]

    minted = await client.post(f"/api/v1/documents/{doc_id}/share", headers=auth_headers(owner_id))
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
