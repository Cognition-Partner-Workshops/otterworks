"""Share-link tokens for read-only document links.

A share link is stateless: the token is an HMAC-SHA256 of the document id keyed
with ``SHARE_LINK_SECRET``, so any replica can validate a link without a shared
lookup table, and nobody without the key can derive one.
"""

from __future__ import annotations

import hashlib
import hmac
import os

import structlog

logger = structlog.get_logger()

SECRET_ENV = "SHARE_LINK_SECRET"  # noqa: S105


def share_link_secret() -> str:
    """Return the share-link signing key, failing when it is not configured."""
    secret = os.environ.get(SECRET_ENV, "")
    if not secret:
        raise RuntimeError(f"{SECRET_ENV} must be set to sign document share links")
    return secret


class ShareLinkService:
    """Mints and validates read-only share tokens for documents."""

    def __init__(self, secret: str | None = None):
        self._key = (secret or share_link_secret()).encode()

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
