"""QA unit tests for document share links and share endpoints."""

import uuid

import pytest

from app.services.share_link import TOKEN_LENGTH, ShareLinkService

DOC_ID = "11111111-1111-4111-8111-111111111111"


def test_token_has_fixed_hex_length():
    token = ShareLinkService(salt="s").mint_token(DOC_ID)
    assert len(token) == TOKEN_LENGTH
    int(token, 16)


def test_different_salts_mint_different_tokens():
    assert ShareLinkService(salt="a").mint_token(DOC_ID) != ShareLinkService(salt="b").mint_token(DOC_ID)


def test_token_from_other_salt_is_rejected():
    token = ShareLinkService(salt="a").mint_token(DOC_ID)
    assert ShareLinkService(salt="b").verify_token(DOC_ID, token) is False


def test_salt_defaults_from_env(monkeypatch):
    monkeypatch.setenv("SHARE_LINK_SALT", "env-salt")
    assert ShareLinkService().mint_token(DOC_ID) == ShareLinkService(salt="env-salt").mint_token(DOC_ID)


def test_empty_token_is_rejected():
    assert ShareLinkService(salt="s").verify_token(DOC_ID, "") is False


def test_truncated_token_is_rejected():
    svc = ShareLinkService(salt="s")
    assert svc.verify_token(DOC_ID, svc.mint_token(DOC_ID)[:-1]) is False


def test_uppercased_token_is_rejected():
    svc = ShareLinkService(salt="s")
    token = svc.mint_token(DOC_ID)
    if token.upper() != token:
        assert svc.verify_token(DOC_ID, token.upper()) is False


def test_tokens_are_distinct_across_many_documents():
    svc = ShareLinkService(salt="s")
    tokens = {svc.mint_token(str(uuid.uuid4())) for _ in range(200)}
    assert len(tokens) == 200


async def _create_doc(client, owner_id):
    resp = await client.post(
        "/api/v1/documents/",
        json={"title": "QA shared", "content": "body", "owner_id": str(owner_id)},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_non_owner_cannot_mint_share_link(client, owner_id, monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    doc_id = await _create_doc(client, owner_id)
    stranger = {"Authorization": "Bearer t", "X-User-ID": str(uuid.uuid4())}
    resp = await client.post(f"/api/v1/documents/{doc_id}/share", headers=stranger)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_unauthenticated_cannot_mint_share_link(client, owner_id, monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    doc_id = await _create_doc(client, owner_id)
    resp = await client.post(f"/api/v1/documents/{doc_id}/share")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_share_link_for_missing_document_is_404(client, owner_id, monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    headers = {"Authorization": "Bearer t", "X-User-ID": str(owner_id)}
    resp = await client.post(f"/api/v1/documents/{uuid.uuid4()}/share", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_shared_endpoint_requires_token(client, owner_id, monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    doc_id = await _create_doc(client, owner_id)
    resp = await client.get("/api/v1/documents/shared", params={"document_id": doc_id})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_token_for_one_document_does_not_open_another(client, owner_id, monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    headers = {"Authorization": "Bearer t", "X-User-ID": str(owner_id)}
    doc_a = await _create_doc(client, owner_id)
    doc_b = await _create_doc(client, owner_id)
    token_a = (await client.post(f"/api/v1/documents/{doc_a}/share", headers=headers)).json()["token"]
    resp = await client.get("/api/v1/documents/shared", params={"document_id": doc_b, "token": token_a})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_non_owner_cannot_read_document_directly(client, owner_id, monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    doc_id = await _create_doc(client, owner_id)
    stranger = {"Authorization": "Bearer t", "X-User-ID": str(uuid.uuid4())}
    resp = await client.get(f"/api/v1/documents/{doc_id}", headers=stranger)
    assert resp.status_code == 403
