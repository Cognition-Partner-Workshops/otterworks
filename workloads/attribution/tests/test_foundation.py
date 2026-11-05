import importlib.util
import json
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import sf_attribution as sf
import yaml
from schemachange.config.ChangeHistoryTable import ChangeHistoryTable

PATH = Path(__file__).resolve().parents[2] / "foundation" / "apply.py"
SPEC = importlib.util.spec_from_file_location("foundation_apply", PATH)
foundation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(foundation)


def test_connection_and_resets_preserve_attribution(monkeypatch):
    for key, value in {
        "SNOWFLAKE_EXT_ACCOUNT": "account", "SNOWFLAKE_EXT_USER": "DEVIN_EXT_SVC",
        "SNOWFLAKE_EXT_PRIVATE_KEY_FILE": "/private/key.p8", "SNOWFLAKE_EXT_WAREHOUSE": "EXECUTION_WH",
    }.items():
        monkeypatch.setenv(key, value)
    params = foundation.connection_parameters("doc_usage_dashboard")
    tag = params["session_parameters"]["QUERY_TAG"]
    assert sf.parse_query_tag(tag)["csid"] == "cs_doc_usage_dashboard_account_usage"
    assert json.dumps(json.loads(tag), separators=(",", ":")) == tag
    assert params["authenticator"] == "SNOWFLAKE_JWT"
    assert params["role"] == "DEVIN_EXT_ROLE"
    assert params["user"] == "DEVIN_EXT_SVC"
    assert params["application"] == "Devin_Demo"
    assert params["private_key_file"] == "/private/key.p8"
    con = MagicMock()
    for name in ("account", "user", "role", "warehouse"):
        setattr(con, name, params[name])
    con.database = con.schema = None
    with patch.object(foundation.snowflake.connector, "connect", return_value=con) as connect:
        session = foundation.new_session(params, ChangeHistoryTable())
    assert connect.call_args.kwargs["session_parameters"] == {"QUERY_TAG": tag}
    assert connect.call_args.kwargs["application"] == sf.APPLICATION
    assert connect.call_args.kwargs["authenticator"] == "SNOWFLAKE_JWT"
    before = con.mock_calls[:]
    session.reset_query_tag(foundation.LOGGER, extra_tag="V1.0.0__test.sql")
    session.reset_query_tag(foundation.LOGGER)
    assert session.session_parameters == {"QUERY_TAG": tag}
    assert con.mock_calls == before
    assert foundation.connection_parameters("doc_usage_dashboard", admin=True)["role"] == "ACCOUNTADMIN"
    assert foundation.connection_parameters(
        "doc_usage_dashboard", admin=True, admin_role="DEVIN_EXT_ROLE"
    )["role"] == "DEVIN_EXT_ROLE"
    monkeypatch.delenv("SNOWFLAKE_EXT_WAREHOUSE")
    assert foundation.connection_parameters("doc_usage_dashboard")["warehouse"] == "WH_DOC_USAGE_DASHBOARD"


def test_bootstrap_without_execution_warehouse():
    params = {"session_parameters": {"QUERY_TAG": "exact"}, "application": sf.APPLICATION,
              "authenticator": "SNOWFLAKE_JWT", "warehouse": "WH_DOC_USAGE_DASHBOARD"}
    con = MagicMock()
    with patch.object(foundation.snowflake.connector, "connect", return_value=con) as connect:
        foundation.bootstrap(params)
    assert connect.call_args.kwargs == {**params, "warehouse": None}
    con.execute_string.assert_called_once_with(foundation.bootstrap_sql())
    con.close.assert_called_once()
    migration = next(foundation.render(
        foundation.ROOT / "doc_usage_dashboard" / "migrations", foundation.template_vars("doc_usage_dashboard")
    ))[1]
    statement = re.search(r"CREATE WAREHOUSE.*?;", migration, re.S)[0]
    assert " ".join(statement.split()) in " ".join(foundation.bootstrap_sql().split())


def test_bootstrap_closes_on_error():
    con = MagicMock()
    con.execute_string.side_effect = RuntimeError("denied")
    with patch.object(foundation.snowflake.connector, "connect", return_value=con):
        with pytest.raises(RuntimeError, match="denied"):
            foundation.bootstrap({})
    con.close.assert_called_once()


def test_constructor_failure_restores_connector():
    params = {"session_parameters": {"QUERY_TAG": "tag"}, "account": "account"}
    with patch.object(foundation.snowflake.connector, "connect", side_effect=RuntimeError("offline")) as connect:
        with pytest.raises(RuntimeError, match="offline"):
            foundation.new_session(params, ChangeHistoryTable())
        assert foundation.snowflake.connector.connect is connect


def test_migration_contracts():
    for workload, folder, _ in foundation.migration_jobs(False):
        rendered = list(foundation.render(folder, foundation.template_vars(workload)))
        assert rendered
        sql = "\n".join(content for _, content in rendered)
        for name, _ in rendered:
            assert re.fullmatch(r"V\d+\.\d+\.\d+__\w+\.sql", name)
        for statement in sql.split(";"):
            if re.match(r"\s*CREATE (DATABASE|WAREHOUSE|ROLE|MASKING POLICY)\b", statement):
                assert "COMMENT =" in statement
                assert sf.RUN_TOKEN in statement and sf.EXPIRES in statement
        value = sf.sql_string(sf.devin_csid_value(sf.workload_csids(workload)))
        for kind, name in (("DATABASE", sf.database_name(workload)), ("WAREHOUSE", sf.warehouse_name(workload))):
            assert f"ALTER {kind} {name} SET TAG {sf.TAG_FQN} = {value};" in sql
        spec = yaml.safe_load((foundation.ROOT / workload / "spec.yaml").read_text())
        for source in spec["inputs"]:
            match = re.search(rf"CREATE TABLE IF NOT EXISTS {re.escape(source['landing'])} \((.*?)\);", sql, re.S)
            assert match, source["landing"]
            columns = [column.strip().split()[0].lower() for column in re.split(r",(?!\d)", match[1])]
            columns += [column.lower() for column in re.findall(
                rf"ALTER TABLE {re.escape(source['landing'])} ADD COLUMN IF NOT EXISTS (\w+)", sql
            )]
            assert columns == source["columns"]
        assert "CREATE RESOURCE MONITOR" not in sql
        assert "ON FUTURE TABLES" not in sql
        assert f"GRANT SELECT ON ALL TABLES IN SCHEMA {sf.database_name(workload)}.APP" in sql
    dashboard = "\n".join(sql for _, sql in foundation.render(
        foundation.ROOT / "doc_usage_dashboard" / "migrations", foundation.template_vars("doc_usage_dashboard")
    ))
    assert f"IS_ROLE_IN_SESSION('{sf.RUN_TOKEN}_ANALYST')" in dashboard
    assert "ELSE '***MASKED***'" in dashboard
    assert "MODIFY COLUMN EMAIL\n    SET MASKING POLICY" in dashboard
    assert "'@example.com'" in dashboard
    assert "WHERE NOT EXISTS" in dashboard
    assert "TARGET.ID =" in dashboard
    assert sf.RUN_TOKEN in foundation.bootstrap_sql() and sf.EXPIRES in foundation.bootstrap_sql()


def test_admin_history_and_monitor_statements():
    workload, folder, table = foundation.migration_jobs(True)[0]
    assert table == "ADMIN_MONITORS"
    sql = "\n".join(sql for _, sql in foundation.render(folder, foundation.template_vars(workload)))
    for name, _, _ in foundation.migration_jobs(False):
        assert f"ALTER WAREHOUSE {sf.warehouse_name(name)} SET RESOURCE_MONITOR = {sf.resource_monitor_name(name)}" in sql


def test_audit_proof_migrations_surround_runtime_grant_fix():
    rendered = dict(foundation.render(
        foundation.ROOT / "doc_usage_dashboard" / "migrations",
        foundation.template_vars("doc_usage_dashboard"),
    ))
    names = list(rendered)
    proof = "V1.0.4__grant_audit_proof_roles.sql"
    fix = "V1.0.5__narrow_runtime_grants.sql"
    cleanup = "V1.0.6__revoke_audit_proof_roles.sql"
    assert names.index(proof) < names.index(fix) < names.index(cleanup)
    for role in ("READER", "ANALYST"):
        assert f"GRANT ROLE {sf.RUN_TOKEN}_{role} TO USER DEVIN_EXT_SVC" in rendered[proof]
        assert f"REVOKE ROLE {sf.RUN_TOKEN}_{role} FROM USER DEVIN_EXT_SVC" in rendered[cleanup]
    app_role = f"{sf.RUN_TOKEN}_DOC_USAGE_DASHBOARD_APP"
    assert f"REVOKE ROLE {sf.RUN_TOKEN}_READER FROM ROLE {app_role};" in rendered[fix]
    selects = re.findall(r"GRANT SELECT ON TABLE ([\w.]+) TO ROLE (\w+);", rendered[fix])
    assert selects == [(f"{sf.database_name('doc_usage_dashboard')}.APP.ACCOUNT_STORAGE_USAGE", app_role)]
    for user in ("DOC_USAGE_DASHBOARD_ACCOUNT_USAGE", "DOC_SEARCH_API_TOP_ITEMS", "CHURN_MODEL_ACCOUNT_SCORE"):
        assert f"ALTER USER IF EXISTS SVC_CS_{user} SET DEFAULT_SECONDARY_ROLES = ()" in rendered[fix]
    assert "DEVIN_EXT_ROLE" not in rendered[fix]


def test_raw_email_migrations_are_guarded_and_follow_dashboard_policy_creation():
    jobs = foundation.migration_jobs(False)
    workloads = [workload for workload, _, _ in jobs]
    for workload, version in (("doc_search_api", "V1.0.3"), ("churn_model", "V1.0.5")):
        assert workloads.index("doc_usage_dashboard") < workloads.index(workload)
        rendered = dict(foundation.render(
            foundation.ROOT / workload / "migrations", foundation.template_vars(workload),
        ))
        sql = rendered[f"{version}__mask_raw_email.sql"]
        assert "IF (column_count > 0) THEN" in sql
        assert "IF (policy_count = 0) THEN" in sql
        assert "POLICY_REFERENCES(" in sql
        assert "REF_COLUMN_NAME = 'EMAIL' AND POLICY_KIND = 'MASKING_POLICY'" in sql
        assert f"ALTER TABLE {sf.database_name(workload)}.RAW.ADMIN_ADMIN_USERS MODIFY COLUMN EMAIL" in sql
        assert f"SET MASKING POLICY {sf.database_name('doc_usage_dashboard')}.APP.EMAIL_MASK;" in sql
        assert " FORCE" not in sql and "DEVIN_EXT_ROLE" not in sql


def test_migrations_leave_no_proof_roles_granted_to_build_user():
    grants = set()
    seen_roles = set()
    for workload, folder, _ in foundation.migration_jobs(False):
        for _, sql in foundation.render(folder, foundation.template_vars(workload)):
            for action, role in re.findall(
                r"(GRANT|REVOKE) ROLE (\w+) (?:TO|FROM) USER DEVIN_EXT_SVC", sql
            ):
                seen_roles.add(role)
                if action == "GRANT":
                    grants.add(role)
                else:
                    grants.discard(role)
    assert seen_roles == {f"{sf.RUN_TOKEN}_READER", f"{sf.RUN_TOKEN}_ANALYST"}
    assert not grants


def test_dry_run_never_connects(capsys):
    with patch.object(foundation.snowflake.connector, "connect", side_effect=AssertionError("network")):
        assert foundation.main(["--dry-run"]) == 0
        assert foundation.main(["--dry-run", "--admin"]) == 0
    output = capsys.readouterr().out
    assert "CREATE DATABASE IF NOT EXISTS DB_SCHEMACHANGE_" in output
    assert "ADMIN_MONITORS" in output


def test_empty_folder_and_version_error(tmp_path, monkeypatch):
    assert list(foundation.render(tmp_path, {})) == []
    monkeypatch.setattr(foundation, "version", lambda _: "0.0.0")
    with pytest.raises(RuntimeError, match="4.4.0"):
        foundation.main(["--dry-run"])
