"""Database credentials must be provided by the deployment environment."""

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_database_url_from_environment(monkeypatch):
    url = "postgresql+asyncpg://runtime@localhost/otterworks"
    monkeypatch.setenv("DOC_SVC_DATABASE_URL", url)
    assert Settings(_env_file=None).database_url == url


@pytest.mark.parametrize("value", [None, ""])
def test_database_url_required(monkeypatch, value):
    monkeypatch.delenv("DOC_SVC_DATABASE_URL", raising=False)
    if value is not None:
        monkeypatch.setenv("DOC_SVC_DATABASE_URL", value)
    with pytest.raises(ValidationError, match="database_url"):
        Settings(_env_file=None)
