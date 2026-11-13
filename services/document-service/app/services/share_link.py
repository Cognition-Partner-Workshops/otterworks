"""Share-link tokens for read-only document links.

A share link is stateless: the token is a keyed MAC over the document id so any
replica holding the key can validate a link without a shared lookup table, and
nobody without the key can derive one.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets

import structlog

logger = structlog.get_logger()

TOKEN_LENGTH = 32
_KEY_CONTEXT = b"otterworks/share-link/v1"
_ephemeral_key: bytes | None = None


def _share_link_key() -> bytes:
    """Resolve the MAC key: SHARE_LINK_SECRET, else a subkey of JWT_SECRET.

    Without either, fall back to a per-process random key: links then stop
    working on restart and across replicas, but can never be forged.
    """
    global _ephemeral_key
    secret = os.environ.get("SHARE_LINK_SECRET")
    if secret:
        return secret.encode()
    jwt_secret = os.environ.get("JWT_SECRET")
    if jwt_secret:
        return hmac.new(jwt_secret.encode(), _KEY_CONTEXT, hashlib.sha256).digest()
    if _ephemeral_key is None:
        logger.warning("share_link_secret_unset_using_ephemeral_key")
        _ephemeral_key = secrets.token_bytes(32)
    return _ephemeral_key


class ShareLinkService:
    """Mints and validates read-only share tokens for documents."""

    def __init__(self, salt: str | None = None, key: bytes | None = None):
        self.salt = salt or os.environ.get("SHARE_LINK_SALT", "otterworks-share")
        self._key = key or _share_link_key()

    def mint_token(self, document_id: str) -> str:
        """Return the share token for a document."""
        message = f"{document_id}:{self.salt}".encode()
        digest = hmac.new(self._key, message, hashlib.sha256).hexdigest()
        return digest[:TOKEN_LENGTH]

    def verify_token(self, document_id: str, token: str) -> bool:
        """Return True when the token is a valid share token for the document."""
        expected = self.mint_token(document_id)
        ok = hmac.compare_digest(expected.encode(), token.encode())
        if not ok:
            logger.info("share_token_rejected", document_id=document_id)
        return ok
