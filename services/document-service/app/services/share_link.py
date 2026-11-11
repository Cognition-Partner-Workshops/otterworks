"""Share-link tokens for read-only document links.

A share link is stateless: the token is an HMAC-SHA256 over the document id,
keyed with ``SHARE_LINK_SECRET``, so any replica holding the secret can validate
a link without a shared lookup table, and nobody without it can derive one.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets

import structlog

logger = structlog.get_logger()

# Used only when SHARE_LINK_SECRET is unset: links stay unforgeable but are valid
# only within this process, so they stop working on restart or another replica.
_EPHEMERAL_SECRET = secrets.token_bytes(32)
_warned_ephemeral = False


def _resolve_secret(explicit: str | None) -> bytes:
    global _warned_ephemeral
    configured = explicit or os.environ.get("SHARE_LINK_SECRET")
    if configured:
        return configured.encode()
    if not _warned_ephemeral:
        logger.warning(
            "share_link_secret_missing",
            detail="SHARE_LINK_SECRET is unset; share links are process-local",
        )
        _warned_ephemeral = True
    return _EPHEMERAL_SECRET


class ShareLinkService:
    """Mints and validates read-only share tokens for documents."""

    def __init__(self, secret: str | None = None, *, salt: str | None = None):
        # ``salt`` is the former name of the key argument, kept for existing callers.
        self._key = _resolve_secret(secret or salt)

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
