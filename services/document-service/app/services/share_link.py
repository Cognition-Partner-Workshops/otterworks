"""Share-link tokens for read-only document links.

A share link is stateless: the token is an HMAC-SHA256 of the document id keyed
with SHARE_LINK_SECRET, so any replica holding the secret can validate a link
without a shared lookup table, and nobody without it can derive one.
"""

from __future__ import annotations

import hashlib
import hmac
import os

import structlog

logger = structlog.get_logger()

SECRET_ENV = "SHARE_LINK_SECRET"


class ShareLinkConfigError(RuntimeError):
    """Raised when the share-link signing secret is not configured."""


class ShareLinkService:
    """Mints and validates read-only share tokens for documents."""

    def __init__(self, secret: str | None = None):
        key = secret if secret is not None else os.environ.get(SECRET_ENV, "")
        if not key:
            raise ShareLinkConfigError(f"{SECRET_ENV} must be set to mint or verify share links")
        self._key = key.encode()

    def mint_token(self, document_id: str) -> str:
        """Return the share token for a document."""
        return hmac.new(self._key, document_id.encode(), hashlib.sha256).hexdigest()

    def verify_token(self, document_id: str, token: str) -> bool:
        """Return True when the token is a valid share token for the document."""
        expected = self.mint_token(document_id)
        ok = hmac.compare_digest(expected.encode(), token.encode())
        if not ok:
            logger.info("share_token_rejected", document_id=document_id)
        return ok
