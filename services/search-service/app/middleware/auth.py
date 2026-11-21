"""Authentication middleware for the search service.

Public endpoints (health, metrics) are exempt. All other endpoints accept
either of two authentication modes:

* A valid service-to-service token via ``Authorization: Bearer <token>``
  (used by trusted internal callers such as the SQS indexer or admin
  reindex jobs).
* A gateway-attested identity: the ``X-User-ID`` header together with
  ``X-Gateway-Signature``, which the API gateway sets to
  ``hex(HMAC-SHA256(INTERNAL_AUTH_SECRET, X-User-ID))`` after validating the
  caller's JWT. A bare ``X-User-ID`` (no signature, or a signature made with
  another key) is never trusted, so reaching this service without going
  through the gateway does not let a caller pick who they are.

Both comparisons are constant-time. If ``INTERNAL_AUTH_SECRET`` is not
configured the gateway identity path is closed rather than open.
"""

from __future__ import annotations

import hashlib
import hmac

import structlog
from flask import jsonify, request

logger = structlog.get_logger()

PUBLIC_PREFIXES = ("/health", "/metrics")
USER_ID_HEADER = "X-User-ID"
SIGNATURE_HEADER = "X-Gateway-Signature"


def sign_identity(secret: str, user_id: str) -> str:
    """Return the attestation the gateway attaches to ``user_id``."""
    return hmac.new(secret.encode(), user_id.encode(), hashlib.sha256).hexdigest()


def verify_gateway_identity(secret: str, user_id: str, signature: str) -> bool:
    """True only when ``signature`` attests ``user_id`` under ``secret``."""
    if not secret or not user_id or not signature:
        return False
    return hmac.compare_digest(sign_identity(secret, user_id), signature.strip().lower())


def require_auth(app):
    """Register a ``before_request`` hook that enforces authentication.

    * Requests to health/metrics paths are always allowed.
    * All other requests must present either a valid service token in
      the ``Authorization`` header or a gateway-signed ``X-User-ID``.
    """
    auth_config = app.config["APP_CONFIG"].auth
    if auth_config.require_auth and not auth_config.internal_auth_secret:
        logger.warning(
            "internal_auth_secret_missing",
            detail="INTERNAL_AUTH_SECRET is unset; gateway identity headers will be rejected",
        )

    @app.before_request
    def _check_auth():
        if not auth_config.require_auth:
            return None

        path = request.path
        if any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return None

        # Accept a valid service token if one is configured.
        if auth_config.service_token:
            token = _extract_bearer_token()
            if token and hmac.compare_digest(token, auth_config.service_token):
                return None

        # Otherwise require a gateway-attested user identity.
        user_id = request.headers.get(USER_ID_HEADER, "").strip()
        signature = request.headers.get(SIGNATURE_HEADER, "")
        if verify_gateway_identity(auth_config.internal_auth_secret, user_id, signature):
            return None

        endpoint = request.endpoint or ""
        logger.warning(
            "auth_rejected",
            endpoint=endpoint,
            path=path,
            has_user_id=bool(user_id),
            has_signature=bool(signature),
        )
        return jsonify({"error": "unauthorized"}), 401


def _extract_bearer_token() -> str:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return ""
