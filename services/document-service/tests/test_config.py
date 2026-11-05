"""Settings must not fall back to a baked-in database credential."""

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_database_url_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DOC_SVC_DATABASE_URL", raising=False)
    with pytest.raises(ValidationError, match="database_url"):
        Settings(_env_file=None)


def test_database_url_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOC_SVC_DATABASE_URL", "postgresql+asyncpg://u@db:5432/x")
    assert Settings(_env_file=None).database_url == "postgresql+asyncpg://u@db:5432/x"
