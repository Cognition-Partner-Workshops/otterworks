import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jinja2 import Template

PATH = Path(__file__).resolve().parents[1] / "freshness.py"
SPEC = importlib.util.spec_from_file_location("freshness", PATH)
f = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(f)
COMMIT = "a" * 40


def provenance(tmp_path, records=None):
    path = tmp_path / "provenance.yaml"
    path.write_text(yaml.safe_dump({
        "endpoints": [{"csid": f.EP.csid, "runtime_source": {"path": f.SOURCE, "revision": COMMIT}}],
        "deployment": {"installed": records if records is not None else [
            {"type": "runtime_source", "name": f.SOURCE, "revision": COMMIT, "status": "installed"}]},
    }))
    return path


def test_runtime_tag_uses_installed_revision_not_git_or_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_SHA", "b" * 40)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    env = dict(SNOWFLAKE_EXT_ACCOUNT="account", SNOWFLAKE_EXT_SRE_USER=f.EP.service_user,
               SNOWFLAKE_EXT_SRE_PRIVATE_KEY=pem)
    one = f.connection_parameters(provenance(tmp_path), env)
    two = f.connection_parameters(provenance(tmp_path), env)
    tag = json.loads(one["session_parameters"]["QUERY_TAG"])
    assert list(tag) == ["csid", "workload", "phase", "commit", "run_id"]
    assert tag["phase"] == "runtime" and tag["commit"] == COMMIT and tag["csid"] == f.EP.csid
    assert tag["run_id"] != json.loads(two["session_parameters"]["QUERY_TAG"])["run_id"]
    assert one["application"] == "Devin_Demo" and one["role"] == f.ROLE
    assert one["session_parameters"]["DEFAULT_SECONDARY_ROLES"] == "NONE"
    assert "private_key_file" not in one and isinstance(one["private_key"], bytes)


def test_missing_or_mismatched_installed_revision_aborts(tmp_path):
    with pytest.raises(f.ResponderError, match="installed responder"):
        f.deployed_revision(provenance(tmp_path, []))
    with pytest.raises(f.ResponderError, match="match the installed"):
        f.deployed_revision(provenance(tmp_path, [
            {"type": "runtime_source", "name": f.SOURCE, "revision": "b" * 40, "status": "installed"}]))


@pytest.mark.parametrize("secondary,valid", [
    ('{"roles":"","value":""}', True), ('{"roles":[],"value":[]}', True),
    ('{"roles":"OTHER","value":"ALL"}', False), ('{}', False),
])
def test_secondary_role_assertion(secondary, valid):
    r = f.Responder(None)
    r.query = MagicMock(side_effect=[[], [{"user_name": f.EP.service_user, "role_name": f.ROLE,
                                          "secondary_roles": secondary}]])
    if valid:
        r.identify()
    else:
        with pytest.raises(f.ResponderError, match="secondary roles"):
            r.identify()
    assert r.query.call_args_list[0].args == ("USE SECONDARY ROLES NONE",)


@pytest.mark.parametrize("credits", ["8.50", "10.00"])
def test_credit_stop_precedes_reads_and_recovery(credits):
    r = f.Responder(None)
    r.query = MagicMock(return_value=[{"name": f.MONITOR, "used_credits": credits}])
    with pytest.raises(f.ResponderError, match="8.5-credit"):
        r.check()
    r.query.assert_called_once_with("SHOW RESOURCE MONITORS")
    r.query.reset_mock()
    with pytest.raises(f.ResponderError, match="8.5-credit"):
        r.recover()
    r.query.assert_called_once_with("SHOW RESOURCE MONITORS")


@pytest.mark.parametrize("rows", [[], [{"name": f.MONITOR, "used_credits": None}]])
def test_missing_credit_readback_fails_closed(rows):
    r = f.Responder(None)
    r.query = MagicMock(return_value=rows)
    with pytest.raises(f.ResponderError, match="unavailable"):
        r.credit_guard()


def fresh_rows(stale=False):
    return [{"table_name": name, "stale": stale} for name in sorted(f.TABLES)]


@pytest.mark.parametrize("fresh,history,state,healthy,problem", [
    (fresh_rows(), [{"state": "SUCCEEDED"}], "started", True, None),
    (fresh_rows(True), [{"state": "SUCCEEDED"}], "started", False, "stale"),
    ([], [], "started", False, "missing_freshness_rows"),
    (fresh_rows(), [{"state": "FAILED"}], "started", False, "latest_task_run_not_succeeded"),
    (fresh_rows(), [{"state": "SUCCEEDED"}], "suspended", False, "task_suspended_or_missing"),
])
def test_check_normal_empty_stale_failed_and_suspended(fresh, history, state, healthy, problem):
    r = f.Responder(None)
    r.query = MagicMock(side_effect=[[{"name": f.MONITOR, "used_credits": "2.31"}], fresh, history, [],
                                    [{"name": "REFRESH_DOC_USAGE_DASHBOARD", "schema_name": "APP", "state": state}]])
    assert r.check() is healthy
    if problem:
        assert problem in r.output["problems"]
    assert "SCHEDULED_TIME_RANGE_END=>CURRENT_TIMESTAMP()" in r.query.call_args_list[2].args[0]


@pytest.mark.parametrize("faults", [[], [dict(target_task="OTHER.APP.TASK", mode="user_task_timeout_ms", cleared_at=None)]])
def test_recovery_refuses_missing_or_non_dashboard_targets(faults):
    r = f.Responder(None)
    r.query = MagicMock(side_effect=[[{"name": f.MONITOR, "used_credits": "2"}], faults])
    with pytest.raises(f.ResponderError, match="exactly one active dashboard"):
        r.recover()
    assert not any("CALL" in c.args[0] for c in r.query.call_args_list)


def test_recovery_polls_new_run_then_rechecks():
    r = f.Responder(None)
    now = datetime.now(timezone.utc)
    r.credit_guard = MagicMock()
    r.check = MagicMock(return_value=True)
    r.query = MagicMock(side_effect=[
        [{"target_task": f.TASK, "mode": "user_task_timeout_ms", "cleared_at": None}],
        [{"result": {"target_task": f.TASK, "recovery_started_at": now.isoformat()}}],
        [{"scheduled_time": now, "state": "SUCCEEDED"}],
    ])
    assert r.recover(interval=0)
    r.check.assert_called_once()


def test_query_error_still_records_id():
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.sfqid = "failed-query-id"
    cursor.execute.side_effect = RuntimeError("denied")
    r = f.Responder(conn)
    with pytest.raises(RuntimeError, match="denied"):
        r.query("SELECT 1")
    assert r.output["query_ids"] == ["failed-query-id"]


def test_migration_is_narrow_and_uses_data_timestamps():
    migration = PATH.parents[1] / "migrations/V1.0.2__freshness_responder.sql"
    sql = Template(migration.read_text()).render(
        database=f.EP.database, warehouse=f.EP.warehouse, comment=f.sf.sql_string(f.sf.external_comment()),
        tag=f.sf.TAG_FQN, tag_value=f.sf.sql_string(f.sf.devin_csid_value(f.sf.workload_csids(f.EP.workload))))
    grants = [line for line in sql.splitlines() if line.startswith("GRANT ")]
    assert len(grants) == 5
    assert all(line.endswith(f"TO ROLE {f.ROLE};") for line in grants)
    assert not any("READER" in line or "GRANT ROLE" in line or ".RAW" in line for line in grants)
    assert not any("ARM_DASHBOARD_FAULT" in line for line in grants)
    assert "EXECUTE AS OWNER" in sql and "invalid_count <> 0" in sql
    assert "TARGET_TASK <> '" + f.TASK + "'" in sql
    assert "SET USER_TASK_TIMEOUT_MS = 1000" in sql
    assert "UNSET USER_TASK_TIMEOUT_MS" in sql
    assert "STATEMENT_TIMEOUT_IN_SECONDS" not in sql
    assert "CREATE OR REPLACE TASK" not in sql and "CREATE OR REPLACE PROCEDURE" not in sql
    assert "CHURN" not in sql and "SEARCH" not in sql
    assert "LAST_ALTERED" not in sql and "MAX(REFRESHED_AT)" in sql
    assert "MAX(SNAPSHOT_DATE)" in sql and "transaction-audit proxy" in sql
    assert "COMMENT = '{\"run_token\":\"SFEXT_20261105A\",\"expires\":\"2026-11-19\"}'" in sql
