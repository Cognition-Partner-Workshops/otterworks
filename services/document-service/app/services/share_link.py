"""Share-link token minting and validation."""

from __future__ import annotations

import hashlib
import hmac
import os

import structlog

logger = structlog.get_logger()

TOKEN_LENGTH = 32
SECRET_ENV_VAR = "SHARE_LINK_SECRET"


class ShareLinkConfigurationError(RuntimeError):
    """Raised when no share-link signing secret is configured."""


def _load_secret(secret: str | None) -> bytes:
    value = secret if secret is not None else os.environ.get(SECRET_ENV_VAR)
    if not value:
        raise ShareLinkConfigurationError(
            f"{SECRET_ENV_VAR} must be set to mint or verify share links"
        )
    return value.encode()


class ShareLinkService:
    """Mints and validates read-only share tokens for documents.

    Tokens are a truncated HMAC-SHA256 over the document id keyed with a
    server-side secret, so they cannot be derived from a document id alone.
    """

    def __init__(self, secret: str | None = None):
        self._key = _load_secret(secret)

    def mint_token(self, document_id: str) -> str:
        """Return the share token for a document."""
        digest = hmac.new(self._key, document_id.encode(), hashlib.sha256).hexdigest()
        return digest[:TOKEN_LENGTH]

    def verify_token(self, document_id: str, token: str) -> bool:
        """Return True when the share token is valid for the document."""
        expected = self.mint_token(document_id)
        ok = hmac.compare_digest(expected.encode(), token.encode())
        if not ok:
            logger.info("share_token_rejected", document_id=document_id)
        return ok
