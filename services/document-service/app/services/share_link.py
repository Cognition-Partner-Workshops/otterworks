"""Share-link tokens for read-only document links.

A share link is stateless: the token is a keyed MAC over the document id, so
any replica holding the same ``SHARE_LINK_SECRET`` can validate a link without
a shared lookup table, while nobody without the secret can derive one.
"""

from __future__ import annotations

import hashlib
import hmac
import os

import structlog

logger = structlog.get_logger()

SECRET_ENV = "SHARE_LINK_SECRET"
MIN_SECRET_LENGTH = 16
_MESSAGE_PREFIX = b"otterworks-share-link:v1:"


class ShareLinkSecretMissingError(RuntimeError):
    """Raised when no usable share-link secret is configured."""


class ShareLinkService:
    """Mints and validates read-only share tokens for documents."""

    def __init__(self, secret: str | None = None):
        secret = secret if secret is not None else os.environ.get(SECRET_ENV, "")
        if len(secret) < MIN_SECRET_LENGTH:
            logger.error("share_link_secret_missing", env=SECRET_ENV)
            raise ShareLinkSecretMissingError(
                f"{SECRET_ENV} must be set to at least {MIN_SECRET_LENGTH} characters"
            )
        self._key = secret.encode()

    def mint_token(self, document_id: str) -> str:
        """Return the share token for a document."""
        message = _MESSAGE_PREFIX + document_id.encode()
        return hmac.new(self._key, message, hashlib.sha256).hexdigest()

    def verify_token(self, document_id: str, token: str) -> bool:
        """Return True when the token is a valid share token for the document."""
        expected = self.mint_token(document_id)
        ok = hmac.compare_digest(expected.encode(), token.encode())
        if not ok:
            logger.info("share_token_rejected", document_id=document_id)
        return ok
