"""document-service refuses to start without its signing secrets."""

import pytest

from app.main import app, lifespan


@pytest.mark.parametrize("variable", ["JWT_SECRET", "SHARE_LINK_SECRET"])
async def test_startup_fails_without_secret(monkeypatch, variable):
    monkeypatch.setenv(variable, "")
    with pytest.raises(RuntimeError, match=variable):
        async with lifespan(app):
            pass
