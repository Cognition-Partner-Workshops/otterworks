from contextlib import nullcontext
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ledger
from sfx_conn import query_tag
from warehouse.run_config import RunConfig


@pytest.mark.parametrize('label', [None, '', 'sfx1119'])
def test_optional_query_tag_label(monkeypatch, label):
    if label is None:
        monkeypatch.delenv('SFX_QUERY_TAG_LABEL', raising=False)
    else:
        monkeypatch.setenv('SFX_QUERY_TAG_LABEL', label)
    value = json.loads(query_tag('ops', 'close'))
    assert value.get('tag') == (label or None)


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


@pytest.mark.parametrize('token', ['sfx1119', 'sfx2220', 'sfx-d1110-alice'])
def test_workload_names_and_spark_attribution_use_the_same_run(token):
    root = Path(__file__).resolve().parents[3]
    result = subprocess.run([sys.executable, '-c',
        'import json; from warehouse.snowflake.sfx_conn import WORKLOADS, query_tag; '
        'print(json.dumps([WORKLOADS, json.loads(query_tag("snowpark", "spark-job", job="example"))]))'],
        cwd=root, env={**os.environ, 'RUN_TOKEN': token}, capture_output=True, text=True, check=True)
    workloads, tag = json.loads(result.stdout)
    config = RunConfig(token)
    assert workloads == {name: f'{config.database}_{name.upper()}_WH'
                         for name in ('load', 'transform', 'parity', 'snowpark', 'ops')}
    assert tag['run'] == tag['run_token'] == token
    assert tag['workload'] == 'snowpark' and tag['phase'] == 'spark-job'
    assert tag['commit'] and tag['run_id']
