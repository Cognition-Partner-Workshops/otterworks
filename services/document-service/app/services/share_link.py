"""Share-link tokens for read-only document links.

A share link is stateless: the token is derived from the document id so any
replica can validate a link without a shared lookup table. The derivation is
an HMAC-SHA256 keyed with a deployment secret, so a token cannot be computed
from the document id and the published source alone.
"""

from __future__ import annotations

import hashlib
import hmac
import os

import structlog

logger = structlog.get_logger()

SHARE_KEY_CONTEXT = b"otterworks/document-service/share-link/v1"


class ShareLinkNotConfiguredError(RuntimeError):
    """Raised when no secret is available to key share tokens."""


def _resolve_key(secret: str | None) -> bytes | None:
    if secret:
        return secret.encode()
    configured = os.environ.get("SHARE_LINK_SECRET")
    if configured:
        return configured.encode()
    # Fall back to a key derived from the service's JWT secret, domain-separated
    # so a share token never doubles as anything the JWT secret signs.
    jwt_secret = os.environ.get("JWT_SECRET")
    if jwt_secret:
        return hmac.new(jwt_secret.encode(), SHARE_KEY_CONTEXT, hashlib.sha256).digest()
    return None


class ShareLinkService:
    """Mints and validates read-only share tokens for documents."""

    def __init__(self, secret: str | None = None, *, salt: str | None = None):
        self._key = _resolve_key(secret or salt)

    def mint_token(self, document_id: str) -> str:
        """Return the share token for a document."""
        if self._key is None:
            raise ShareLinkNotConfiguredError(
                "SHARE_LINK_SECRET (or JWT_SECRET) must be set to mint share links"
            )
        return hmac.new(self._key, document_id.encode(), hashlib.sha256).hexdigest()

    def verify_token(self, document_id: str, token: str) -> bool:
        """Return True when the token is a valid share token for the document."""
        if self._key is None:
            logger.warning("share_link_secret_missing", document_id=document_id)
            return False
        expected = self.mint_token(document_id)
        ok = hmac.compare_digest(expected.encode(), token.encode())
        if not ok:
            logger.info("share_token_rejected", document_id=document_id)
        return ok
