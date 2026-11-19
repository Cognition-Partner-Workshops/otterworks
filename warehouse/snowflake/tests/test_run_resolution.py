from contextlib import nullcontext
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ledger
from sfx_conn import query_tag
from warehouse.run_config import RunConfig


@pytest.mark.parametrize("current,legacy,expected", [
    (None, None, "sfx1119"),
    (None, "sfx-d1110", "sfx-d1110"),
    (None, "sfx-d1110-test'quote", "sfx1119"),
    (None, "", "sfx1119"),
    (None, "free-text attribution", "sfx1119"),
    ("sfx2220", None, "sfx2220"),
    ("sfx2220", "sfx-d1110", "sfx2220"),
    ("sfx2220", "sfx-d1110-test'quote", "sfx2220"),
])
@pytest.mark.parametrize("override", [None, "sfx3330"])
def test_query_tag_and_ledger_resolve_the_same_run(monkeypatch, capsys, current, legacy, expected, override):
    for key, value in (("RUN_TOKEN", current), ("SNOWFLAKE_RUN_TOKEN", legacy)):
        monkeypatch.delenv(key, raising=False)
        if value is not None:
            monkeypatch.setenv(key, value)
    monkeypatch.setenv("SFX_COMMIT", "test-commit")
    assert RunConfig.from_env().token == expected
    assert json.loads(query_tag("ops", "ledger"))["run_token"] == expected
    tokens = []
    monkeypatch.setattr(ledger, "connect", lambda *args: nullcontext(
        SimpleNamespace(cursor=lambda: nullcontext(None))))
    monkeypatch.setattr(ledger, "read_usage", lambda cursor, token, days: (
        tokens.append(token) or ([], [], [], None)))
    monkeypatch.setattr(sys, "argv", ["ledger", "--json"] + (["--token", override] if override else []))
    ledger.main()
    assert tokens == [override or expected]
    assert json.loads(capsys.readouterr().out)["recent_tagged_queries"] == 0


@pytest.mark.parametrize("value", ["", "invalid", "sfx1119'quote"])
def test_invalid_resolved_token_is_rejected(monkeypatch, value):
    monkeypatch.delenv("RUN_TOKEN", raising=False)
    monkeypatch.delenv("SNOWFLAKE_RUN_TOKEN", raising=False)
    monkeypatch.setenv("RUN_TOKEN", value)
    with pytest.raises(ValueError, match="RUN_TOKEN"):
        RunConfig.from_env()
