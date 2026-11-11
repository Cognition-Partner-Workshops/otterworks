"""Share-link tokens for read-only document links.

A share link is stateless: the token is derived from the document id so any
replica can validate a link without a shared lookup table.
"""

from __future__ import annotations

import hashlib
import hmac
import os

import structlog

logger = structlog.get_logger()

TOKEN_LENGTH = 16


class ShareLinkService:
    """Mints and validates read-only share tokens for documents."""

    def __init__(self, salt: str | None = None):
        self.salt = salt or os.environ.get("SHARE_LINK_SALT", "otterworks-share")

    def mint_token(self, document_id: str) -> str:
        """Return the share token for a document."""
        secret = os.environ.get("SHARE_LINK_SECRET")
        if not secret:
            raise ValueError("SHARE_LINK_SECRET is required")
        digest = hmac.new(
            secret.encode(), f"{document_id}:{self.salt}".encode(), hashlib.sha256
        ).hexdigest()
        return digest[:TOKEN_LENGTH]

    def verify_token(self, document_id: str, token: str) -> bool:
        """Return True when the token is a valid share token for the document."""
        expected = self.mint_token(document_id)
        ok = isinstance(token, str) and hmac.compare_digest(expected.encode(), token.encode())
        if not ok:
            logger.info("share_token_rejected", document_id=document_id)
        return ok
