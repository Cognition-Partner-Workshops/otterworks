"""Settings must not ship database credentials in code."""

import pytest
from sqlalchemy.engine import make_url

from app.config import Settings


def test_default_database_url_has_no_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DOC_SVC_DATABASE_URL", raising=False)

    url = make_url(Settings(_env_file=None).database_url)

    assert url.password is None
    assert url.username is None


def test_database_url_is_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    configured = "postgresql+asyncpg://svc:from-env@db.internal:5432/otterworks"
    monkeypatch.setenv("DOC_SVC_DATABASE_URL", configured)

    assert Settings(_env_file=None).database_url == configured
