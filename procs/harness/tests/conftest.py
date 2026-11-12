from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def signing_secret(monkeypatch) -> None:
    monkeypatch.setenv("PROCS_AUTH_SECRET", "unit-test-signing-key-not-used-anywhere-else")
