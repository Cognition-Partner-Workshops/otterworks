"""Share-link tokens for read-only document links.

A share link is stateless: the token is a keyed MAC over the document id, so any
replica holding the same key can validate a link without a shared lookup table,
and nobody without the key can derive one.

The key is ``SHARE_LINK_SECRET``. Deployments that do not set it derive a
dedicated key from ``JWT_SECRET``, which every replica already shares. Without
either, a per-process random key keeps links unforgeable at the cost of links
not surviving a restart.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets

import structlog

logger = structlog.get_logger()

TOKEN_LENGTH = 32
_DERIVATION_LABEL = b"otterworks-share-link-v1"
_PROCESS_KEY = secrets.token_bytes(32)


def _resolve_key(secret: str | None) -> bytes:
    if secret:
        return secret.encode()
    configured = os.environ.get("SHARE_LINK_SECRET")
    if configured:
        return configured.encode()
    jwt_secret = os.environ.get("JWT_SECRET")
    if jwt_secret:
        return hmac.new(jwt_secret.encode(), _DERIVATION_LABEL, hashlib.sha256).digest()
    logger.warning("share_link_secret_unset", detail="share links will not survive a restart")
    return _PROCESS_KEY


class ShareLinkService:
    """Mints and validates read-only share tokens for documents."""

    def __init__(self, salt: str | None = None, secret: str | None = None):
        self.salt = salt or os.environ.get("SHARE_LINK_SALT", "otterworks-share")
        self._key = _resolve_key(secret)

    def mint_token(self, document_id: str) -> str:
        """Return the share token for a document."""
        message = f"{document_id}:{self.salt}".encode()
        return hmac.new(self._key, message, hashlib.sha256).hexdigest()[:TOKEN_LENGTH]

    def verify_token(self, document_id: str, token: str) -> bool:
        """Return True when the token is a valid share token for the document."""
        ok = hmac.compare_digest(self.mint_token(document_id).encode(), token.encode())
        if not ok:
            logger.info("share_token_rejected", document_id=document_id)
        return ok
