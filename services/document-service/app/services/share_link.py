"""Share-link tokens for read-only document links.

A share link is stateless: the token is an HMAC over the document id keyed with
a server-held secret, so any replica holding the secret can validate a link
without a shared lookup table, and nobody without it can derive one.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets

import structlog

logger = structlog.get_logger()

TOKEN_LENGTH = 32

_EPHEMERAL_SECRET: str | None = None


def _configured_secret() -> str:
    """SHARE_LINK_SECRET, else the service's JWT_SECRET, else a per-process key."""
    global _EPHEMERAL_SECRET
    secret = os.environ.get("SHARE_LINK_SECRET") or os.environ.get("JWT_SECRET")
    if secret:
        return secret
    if _EPHEMERAL_SECRET is None:
        logger.warning(
            "share_link_secret_missing",
            detail="SHARE_LINK_SECRET and JWT_SECRET are unset; share links will not "
            "survive a restart or validate on other replicas",
        )
        _EPHEMERAL_SECRET = secrets.token_hex(32)
    return _EPHEMERAL_SECRET


class ShareLinkService:
    """Mints and validates read-only share tokens for documents."""

    def __init__(self, salt: str | None = None, secret: str | None = None):
        self.salt = salt or os.environ.get("SHARE_LINK_SALT", "otterworks-share")
        self._key = (secret or _configured_secret()).encode()

    def mint_token(self, document_id: str) -> str:
        """Return the share token for a document."""
        message = f"share-link:{self.salt}:{document_id}".encode()
        return hmac.new(self._key, message, hashlib.sha256).hexdigest()[:TOKEN_LENGTH]

    def verify_token(self, document_id: str, token: str) -> bool:
        """Return True when the token is a valid share token for the document."""
        expected = self.mint_token(document_id)
        ok = hmac.compare_digest(expected.encode(), token.encode())
        if not ok:
            logger.info("share_token_rejected", document_id=document_id)
        return ok
