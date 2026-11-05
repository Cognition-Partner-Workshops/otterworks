import hashlib
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from test_cd import cd


def support():
    return cd.module(cd.REPO, "workloads/doc_usage_dashboard/responder/provision_support.py", "test_support_setup")


@pytest.mark.parametrize("exists,key", [(False, "public-key"), (True, None), (True, "different-key")])
def test_provision_non_destructive(exists, key):
    module = support()
    statements = module.provision_sql(key, user_exists=exists)
    sql = "\n".join(statements)
    assert "ALTER USER" not in sql and "OR REPLACE" not in sql
    assert all(s.startswith(("CREATE ROLE IF NOT EXISTS", "CREATE USER IF NOT EXISTS", "GRANT ")) for s in statements)
    assert [s for s in statements if s.startswith("GRANT")] == [
        f"GRANT USAGE ON DATABASE {module.EP.database} TO ROLE {module.ROLE}",
        f"GRANT USAGE ON WAREHOUSE {module.EP.warehouse} TO ROLE {module.ROLE}",
        f"GRANT ROLE {module.ROLE} TO USER {module.EP.service_user}",
    ]
    assert ('RSA_PUBLIC_KEY' in sql) == (not exists)
    if not exists:
        assert "DEFAULT_SECONDARY_ROLES = ()" in sql
        assert f"DEFAULT_ROLE = {module.ROLE}" in sql
        assert all(value in sql for value in ("SFEXT_20261105A", "2026-11-19", module.EP.csid))


def test_missing_key_fails_before_any_write():
    with pytest.raises(ValueError, match="SNOWFLAKE_EXT_SUPPORT_PUBLIC_KEY required"):
        support().provision_sql()


def test_existing_user_lookup_is_exact(monkeypatch):
    monkeypatch.delenv("SNOWFLAKE_EXT_SUPPORT_PUBLIC_KEY", raising=False)
    module = support()
    with patch.object(cd, "execute", side_effect=[[(None, module.EP.service_user)], [], [], [], []]) as execute:
        cd.provision_support(cd.REPO, MagicMock(), MagicMock())
    assert not any("CREATE USER" in call.args[1] for call in execute.call_args_list)
    with patch.object(cd, "execute", return_value=[(None, "UNRELATED")]) as execute:
        with pytest.raises(ValueError, match="PUBLIC_KEY"):
            cd.provision_support(cd.REPO, MagicMock(), MagicMock())
    assert execute.call_count == 1


def test_model_bootstrap_shares_installer_ddl(tmp_path):
    runtime = cd.module(cd.REPO, "workloads/pipeline/runtime.py", "test_bootstrap_runtime")
    target = tmp_path / "bootstrap"
    target.mkdir()
    node = {"config": {"column_ddl": "account_id VARCHAR(36), snapshot_date DATE"}}
    (target / "manifest.json").write_text(json.dumps({"nodes": {"model.otterworks_pipeline.account_storage_usage": node}}))
    expected = runtime.model_table_sql("doc_usage_dashboard", node)
    with patch.object(runtime, "dbtRunner") as runner, patch.object(cd, "execute") as execute:
        runner.return_value.invoke.return_value.success = True
        cd.bootstrap_models(runtime, "doc_usage_dashboard", MagicMock(), MagicMock(), tmp_path)
    assert [call.args[1] for call in execute.call_args_list] == expected
    assert all(sql.startswith("CREATE TABLE IF NOT EXISTS") for sql in expected)
    assert f"({node['config']['column_ddl']})" in expected[0]
    assert "EXECUTION_ROLE VARCHAR, REFRESHED_AT TIMESTAMP_LTZ, REPORT_QUERY_ID VARCHAR" in expected[1]
    with patch.object(runtime, "dbtRunner") as runner, patch.object(cd, "execute") as execute:
        runner.return_value.invoke.return_value.success = False
        with pytest.raises(cd.GateFailure, match="bootstrap_parse"):
            cd.bootstrap_models(runtime, "doc_usage_dashboard", MagicMock(), MagicMock(), tmp_path)
        execute.assert_not_called()


@pytest.mark.parametrize("ci", [False, True])
def test_deploy_setup_order(tmp_path, monkeypatch, ci):
    monkeypatch.setenv("GITHUB_ACTIONS", "true" if ci else "false")
    monkeypatch.setenv("SNOWFLAKE_EXT_ACCOUNT", "test-account")
    monkeypatch.setenv("SNOWFLAKE_EXT_USER", "TEST_SETUP_USER")
    monkeypatch.setenv("SNOWFLAKE_EXT_PRIVATE_KEY", "test-key")
    monkeypatch.delenv("SNOWFLAKE_EXT_SUPPORT_PUBLIC_KEY", raising=False)
    if ci:
        monkeypatch.delenv("DEVIN_SESSION_URL", raising=False)
    else:
        monkeypatch.setenv("DEVIN_SESSION_URL", "https://app.devin.ai/sessions/" + "a" * 32)
    args = SimpleNamespace(mode="deploy", dry_run=False, write_provenance=False, log_dir=str(tmp_path))
    runtime = SimpleNamespace(APP="DB.APP.STREAMLIT", MODELS={"doc_usage_dashboard": "account_storage_usage"},
                              procedure_name=lambda w: "DB.APP.P")
    events = []
    def event(name, value=None):
        def record(*args):
            events.append(name)
            return value
        return record
    with patch.object(cd, "module", return_value=runtime), patch.object(cd, "parameters", wraps=cd.parameters) as params, \
            patch.object(cd.serialization, "load_pem_private_key"), patch.object(cd, "der", return_value=b"test-key"), \
            patch.object(cd.snowflake.connector, "connect", return_value=MagicMock()) as connect, \
            patch.object(cd, "execute", return_value=[]), \
            patch.object(cd, "provision_support", side_effect=event("provision")), \
            patch.object(cd, "bootstrap_models", side_effect=event("bootstrap")), \
            patch.object(cd, "migrate", side_effect=event("migrate", [])), \
            patch.object(cd, "install", side_effect=event("install")), \
            patch.object(cd, "dbt", return_value=1), patch.object(cd, "streamlit"), patch.object(cd, "provenance"):
        assert cd.run_workload(cd.REPO, "doc_usage_dashboard", args, "a" * 40, "a" * 40)
    assert events == ["provision", "bootstrap", "migrate", "install"]
    phase = "runtime" if ci else "dev"
    assert params.call_args.args[-1] == phase
    assert params.call_args_list[0].args[2] != params.call_args_list[1].args[2]
    setup = connect.call_args_list[1].kwargs
    tag = json.loads(setup["session_parameters"]["QUERY_TAG"])
    assert tag["phase"] == phase
    assert cd.sf.parse_run_id(tag["run_id"])["phase"] == phase
    assert ("session_url" in tag) == (not ci)
    assert setup["user"] == "TEST_SETUP_USER"
    assert setup["role"] == "DEVIN_EXT_ROLE"


def test_applied_migrations_unchanged():
    hashes = [
        "1a86390d90e00d65ed4932799e022422d9047899582629d23d6c69f44274c6ff",
        "bc41d74d9a5105b165401b2c7505076b4a9761a0a11b1c0c1000501e0560230f",
        "77609c289a53016d6b149371fd9fa6cf42dbed3ecfe97acd929bfbf57ec8e6e0",
        "014b5cb7be779220c2145cd609fd31d996970cf9fd38c65b55a4fac8d1a89d2a",
    ]
    files = sorted((cd.REPO / "workloads/doc_usage_dashboard/migrations").glob("V1.0.[0-3]__*.sql"))
    assert [hashlib.sha256(path.read_bytes()).hexdigest() for path in files] == hashes
