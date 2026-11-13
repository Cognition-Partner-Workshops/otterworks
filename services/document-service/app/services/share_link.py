"""Share-link tokens for read-only document links.

A share link is stateless: the token is an HMAC-SHA256 of the document id keyed
with ``SHARE_LINK_SECRET``, so any replica holding the secret can validate a link
without a shared lookup table, and nobody without it can derive one.
"""

from __future__ import annotations

import hashlib
import hmac
import os

import structlog

logger = structlog.get_logger()

SECRET_ENV_VAR = "SHARE_LINK_SECRET"
MIN_SECRET_LENGTH = 16
# Values that have been published in this repository and so can never key a MAC.
_PUBLIC_SECRETS = frozenset({"otterworks-share"})


class ShareLinkSecretError(RuntimeError):
    """Raised when no usable share-link secret is configured."""


def load_share_link_secret() -> bytes:
    """Return the configured share-link secret, refusing missing or public values."""
    return _validate_secret(os.environ.get(SECRET_ENV_VAR, ""))


def _validate_secret(secret: str) -> bytes:
    if not secret:
        raise ShareLinkSecretError(f"{SECRET_ENV_VAR} must be set")
    if secret in _PUBLIC_SECRETS or len(secret) < MIN_SECRET_LENGTH:
        raise ShareLinkSecretError(
            f"{SECRET_ENV_VAR} must be a private random value of at least "
            f"{MIN_SECRET_LENGTH} characters"
        )
    return secret.encode()


class ShareLinkService:
    """Mints and validates read-only share tokens for documents."""

    def __init__(self, secret: str | None = None):
        self._key = _validate_secret(secret) if secret is not None else load_share_link_secret()

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
