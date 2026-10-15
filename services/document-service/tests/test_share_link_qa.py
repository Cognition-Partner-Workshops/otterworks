"""QA coverage for document share-link tokens (sharing area)."""

import secrets
import uuid

import pytest

from app.services.share_link import TOKEN_LENGTH, ShareLinkService


def test_token_is_fixed_length_hex():
    token = ShareLinkService(salt=secrets.token_hex(8)).mint_token(str(uuid.uuid4()))
    assert len(token) == TOKEN_LENGTH
    int(token, 16)


def test_tokens_differ_per_document():
    service = ShareLinkService(salt=secrets.token_hex(8))
    assert service.mint_token(str(uuid.uuid4())) != service.mint_token(str(uuid.uuid4()))


def test_tokens_differ_per_salt():
    doc_id = str(uuid.uuid4())
    first = ShareLinkService(salt=secrets.token_hex(8)).mint_token(doc_id)
    second = ShareLinkService(salt=secrets.token_hex(8)).mint_token(doc_id)
    assert first != second


def test_token_from_other_salt_is_rejected():
    doc_id = str(uuid.uuid4())
    foreign = ShareLinkService(salt=secrets.token_hex(8)).mint_token(doc_id)
    assert ShareLinkService(salt=secrets.token_hex(8)).verify_token(doc_id, foreign) is False


def test_env_salt_is_used(monkeypatch):
    salt = secrets.token_hex(8)
    monkeypatch.setenv("SHARE_LINK_SALT", salt)
    doc_id = str(uuid.uuid4())
    assert ShareLinkService().mint_token(doc_id) == ShareLinkService(salt=salt).mint_token(doc_id)


@pytest.mark.xfail(
    strict=True,
    reason="[REAL] SHARE_LINK_SALT is never set in compose/helm, so the source-visible default "
    "salt applies and anyone who knows a document id can forge its share token "
    "(MD5 derivation itself is the planted OW-SEC-403 lab).",
)
def test_token_cannot_be_forged_without_configured_secret(monkeypatch):
    monkeypatch.delenv("SHARE_LINK_SALT", raising=False)
    doc_id = str(uuid.uuid4())
    forged = ShareLinkService(salt="otterworks-share").mint_token(doc_id)
    assert ShareLinkService().verify_token(doc_id, forged) is False
