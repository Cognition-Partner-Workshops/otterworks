"""Shared fixture helpers: locality checks for the offline Oracle fixture."""

from __future__ import annotations

import sys


def require_local_dsn(easy_connect: str) -> None:
    """The fixture DSN must be local: host is the text before the first ':'
    or '/' and must be exactly 127.0.0.1 or localhost."""
    host = easy_connect.split(":", 1)[0].split("/", 1)[0]
    if host not in ("127.0.0.1", "localhost"):
        sys.exit("offline fixture must be local (127.0.0.1 or localhost)")
