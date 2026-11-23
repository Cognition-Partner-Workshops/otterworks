import pytest
from pydantic import ValidationError

from app.config import Settings


def test_database_url_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DOC_SVC_DATABASE_URL", raising=False)

    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None)

    assert [(error["loc"], error["type"]) for error in exc.value.errors()] == [
        (("database_url",), "missing"),
    ]
