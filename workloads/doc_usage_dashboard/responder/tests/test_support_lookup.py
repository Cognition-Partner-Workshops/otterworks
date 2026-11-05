import importlib.util
import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jinja2 import Template

PATH = Path(__file__).resolve().parents[1] / "support_lookup.py"
SPEC = importlib.util.spec_from_file_location("support_lookup", PATH)
f = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(f)
COMMIT = "a" * 40
ACCOUNT = "00000000-0000-4000-8000-000000000101"


def provenance(tmp_path, records=None, revision=COMMIT):
    path = tmp_path / "provenance.yaml"
    path.write_text(yaml.safe_dump({
        "endpoints": [{"csid": f.EP.csid, "runtime_source": {"path": f.SOURCE, "revision": revision}}],
        "deployment": {"installed": records if records is not None else [
            {"type": "runtime_source", "name": f.SOURCE, "revision": COMMIT, "status": "installed"}]},
    }))
    return path


def test_runtime_identity_key_and_tag(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_SHA", "b" * 40)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    env = dict(SNOWFLAKE_EXT_ACCOUNT="account", SNOWFLAKE_EXT_SUPPORT_USER=f.EP.service_user,
               SNOWFLAKE_EXT_SUPPORT_PRIVATE_KEY=pem)
    path = provenance(tmp_path)
    params = f.connection_parameters(path, env)
    tag = json.loads(params["session_parameters"]["QUERY_TAG"])
    assert list(tag) == ["csid", "workload", "phase", "commit", "run_id"]
    assert tag["csid"] == f.EP.csid and tag["phase"] == "runtime" and tag["commit"] == COMMIT
    assert tag["run_id"] != json.loads(f.connection_parameters(path, env)["session_parameters"]["QUERY_TAG"])["run_id"]
    assert params["application"] == "Devin_Demo" and params["role"] == f.ROLE
    assert params["schema"] == "OPS" and params["user"] == f.EP.service_user
    assert params["session_parameters"]["DEFAULT_SECONDARY_ROLES"] == "NONE"
    assert "private_key_file" not in params and isinstance(params["private_key"], bytes)
    with pytest.raises(f.LookupError, match="Support service identity"):
        f.connection_parameters(path, {**env, "SNOWFLAKE_EXT_SUPPORT_USER": "WRONG"})


def test_revision_requires_latest_successful_matching_record(tmp_path):
    with pytest.raises(f.LookupError, match="installed lookup"):
        f.deployed_revision(provenance(tmp_path, []))
    with pytest.raises(f.LookupError, match="match the installed"):
        f.deployed_revision(provenance(tmp_path, revision="b" * 40))
    records = [{"type": "runtime_source", "name": f.SOURCE, "revision": r, "status": s}
               for r, s in [("b"*40, "installed"), (COMMIT, "installed"), ("c"*40, "failed")]]
    assert f.deployed_revision(provenance(tmp_path, records)) == COMMIT


@pytest.mark.parametrize("start,end,expected", [
    (None, None, (ACCOUNT,)),
    ("2026-11-02", None, (ACCOUNT, date(2026, 11, 2))),
    (None, date(2026, 11, 5), (ACCOUNT, date(2026, 11, 5))),
    ("2026-11-02", "2026-11-05", (ACCOUNT, date(2026, 11, 2), date(2026, 11, 5))),
])
def test_sql_is_account_scoped_bound_and_ordered(start, end, expected):
    sql, binds = f.lookup_sql(ACCOUNT, start, end)
    assert f"FROM {f.VIEW} WHERE account_id = %s" in sql
    assert sql.endswith("ORDER BY snapshot_date")
    assert ACCOUNT not in sql and binds == expected and sql.count("%s") == len(binds)


@pytest.mark.parametrize("account,start,end", [
    ("' OR 1=1 --", None, None), (None, None, None), ("", None, None),
    (ACCOUNT, "yesterday", None), (ACCOUNT, "2026-11-05", "2026-11-02"),
    (ACCOUNT, 123, None),
])
def test_invalid_input_precedes_queries(account, start, end):
    client = f.Lookup(None)
    client.query = MagicMock()
    with pytest.raises(ValueError):
        client.lookup(account, start, end)
    client.query.assert_not_called()


@pytest.mark.parametrize("secondary,valid", [
    ('{"roles":"","value":""}', True), ('{"roles":[],"value":[]}', True),
    ('{"roles":"OTHER","value":"ALL"}', False), ('{}', False),
])
def test_secondary_roles_must_be_disabled(secondary, valid):
    client = f.Lookup(None)
    client.query = MagicMock(side_effect=[[], [{"user_name": f.EP.service_user, "role_name": f.ROLE,
                                               "secondary_roles": secondary}]])
    if valid:
        client.identify()
    else:
        with pytest.raises(f.LookupError, match="secondary roles"):
            client.identify()
    assert client.query.call_args_list[0].args == ("USE SECONDARY ROLES NONE",)


@pytest.mark.parametrize("rows", [[], [{"account_id": ACCOUNT}]])
def test_lookup_normal_and_empty(rows):
    client = f.Lookup(None)
    client.identify = MagicMock()
    client.query = MagicMock(return_value=rows)
    assert client.lookup(ACCOUNT) == rows
    client.identify.assert_called_once()
    client.query.assert_called_once_with(*f.lookup_sql(ACCOUNT))


def test_query_error_propagates_and_other_accounts_fail_closed():
    client = f.Lookup(None)
    client.identify = MagicMock()
    client.query = MagicMock(side_effect=RuntimeError("denied"))
    with pytest.raises(RuntimeError, match="denied"):
        client.lookup(ACCOUNT)
    client.query = MagicMock(return_value=[{"account_id": "another-account"}])
    with pytest.raises(f.LookupError, match="another account"):
        client.lookup(ACCOUNT)


def test_migration_only_exposes_masked_source_view_and_two_grants():
    from workloads.foundation.apply import template_vars

    path = PATH.parents[1] / "migrations/V1.0.3__support_lookup.sql"
    sql = Template(path.read_text()).render(**template_vars(f.EP.workload)).upper()
    assert sql.count(";") == 3
    assert f"FROM {f.EP.database}.APP.ACCOUNT_STORAGE_USAGE" in sql
    assert "ACCOUNT_EMAIL" in sql and "MASKING" not in sql
    assert '"RUN_TOKEN":"SFEXT_20261105A"' in sql and '"EXPIRES":"2026-11-19"' in sql
    assert "GRANT SELECT ON VIEW" in sql and "GRANT USAGE ON SCHEMA" in sql
    assert not any(word in sql for word in ["ALTER ", "CALL ", "TASK ", ".RAW.", "STREAMLIT", "USER "])
