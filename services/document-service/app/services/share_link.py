"""Share-link tokens for read-only document links.

A share link is stateless: the token is an HMAC of the document id keyed with
``SHARE_LINK_SECRET``, so any replica holding the secret can validate a link
without a shared lookup table, and nobody without it can derive one.
"""

from __future__ import annotations

import hashlib
import hmac
import os

import structlog

logger = structlog.get_logger()

TOKEN_LENGTH = 32
SECRET_ENV = "SHARE_LINK_SECRET"


class ShareLinkSecretMissingError(RuntimeError):
    """Raised when no share-link signing key is configured."""


def load_share_link_secret() -> str:
    """Return the configured share-link signing key, failing closed when unset."""
    secret = os.environ.get(SECRET_ENV, "")
    if not secret:
        raise ShareLinkSecretMissingError(
            f"{SECRET_ENV} must be set to mint or verify share links"
        )
    return secret


class ShareLinkService:
    """Mints and validates read-only share tokens for documents."""

    def __init__(self, secret: str | None = None):
        self._key = (secret or load_share_link_secret()).encode()

    def mint_token(self, document_id: str) -> str:
        """Return the share token for a document."""
        digest = hmac.new(
            self._key, f"share:{document_id}".encode(), hashlib.sha256
        ).hexdigest()
        return digest[:TOKEN_LENGTH]

    def verify_token(self, document_id: str, token: str) -> bool:
        """Return True when the token is a valid share token for the document."""
        expected = self.mint_token(document_id)
        ok = hmac.compare_digest(expected.encode(), token.encode())
        if not ok:
            logger.info("share_token_rejected", document_id=document_id)
        return ok
