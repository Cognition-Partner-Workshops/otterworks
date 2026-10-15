"""Share-link tokens for read-only document links.

A share link is stateless: the token is a keyed MAC over the document id, so any
replica holding the same ``SHARE_LINK_SECRET`` can validate a link without a
shared lookup table, while nobody without the key can derive one.
"""

from __future__ import annotations

import hashlib
import hmac
import os

import structlog

logger = structlog.get_logger()

SECRET_ENV = "SHARE_LINK_SECRET"


class ShareLinkService:
    """Mints and validates read-only share tokens for documents."""

    def __init__(self, secret: str | None = None):
        secret = secret or os.environ.get(SECRET_ENV)
        if not secret:
            raise RuntimeError(f"{SECRET_ENV} must be set to mint or verify share links")
        self._key = secret.encode()

    def mint_token(self, document_id: str) -> str:
        """Return the share token for a document."""
        return hmac.new(self._key, document_id.encode(), hashlib.sha256).hexdigest()

    def verify_token(self, document_id: str, token: str) -> bool:
        """Return True when the token is a valid share token for the document."""
        ok = hmac.compare_digest(self.mint_token(document_id), token)
        if not ok:
            logger.info("share_token_rejected", document_id=document_id)
        return ok
