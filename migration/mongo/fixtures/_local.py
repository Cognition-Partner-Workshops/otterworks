"""Shared fixture helpers: locality checks for the offline Oracle fixture.

`require_local_dsn` is the spec_loader implementation re-exported so fixture
seeders and unit loaders share one definition.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "loaders"))

from spec_loader import require_local_oracle_dsn  # noqa: E402


def require_local_dsn(easy_connect: str) -> None:
    try:
        require_local_oracle_dsn(easy_connect)
    except ValueError as exc:
        sys.exit(str(exc))
