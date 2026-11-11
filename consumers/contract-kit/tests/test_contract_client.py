import json
import subprocess

import pytest

from contract_client import bind, execute


@pytest.mark.parametrize("value,literal", [(None, "NULL"), ("O'Brien", "'O''Brien'"), ("", "''")])
def test_bind(value, literal):
    assert bind("SEL ? AS VALUE", [value]) == f"SEL {literal} AS VALUE"


@pytest.mark.parametrize("sql,parameters", [("SEL ?", []), ("SEL 1", ["extra"])])
def test_parameter_count_is_checked(sql, parameters):
    with pytest.raises(ValueError, match="parameter count"):
        bind(sql, parameters)


def test_live_record_and_replay_without_a_bridge(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTRACT_RECORD", "true")
    monkeypatch.setenv("WAREHOUSE_CONTRACT_TARGET", "teradata-emulator")
    result = execute("SEL ? AS VALUE", tmp_path, "sample", ["O'Brien"])
    assert result == {"query": "sample", "columns": ["VALUE"], "rows": [["O'Brien"]]}
    recorded = tmp_path / "recorded" / "teradata" / "sample.json"
    assert json.loads(recorded.read_text()) == result
    monkeypatch.setenv("WAREHOUSE_CONTRACT_TARGET", "replay")
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: pytest.fail("replay invoked bridge"))
    assert execute("SEL ? AS VALUE", tmp_path, "sample", ["O'Brien"]) == result


def test_empty_result_and_query_error(tmp_path, monkeypatch):
    monkeypatch.setenv("WAREHOUSE_CONTRACT_TARGET", "teradata-emulator")
    result = execute("SEL CUSTOMER_ID FROM SFX_BILLING.CUSTOMER_ACCOUNT WHERE CUSTOMER_ID = -1",
                     tmp_path, "empty")
    assert result["rows"] == []
    with pytest.raises(RuntimeError, match="warehouse query failed"):
        execute("SEL missing_column FROM SFX_BILLING.CUSTOMER_ACCOUNT", tmp_path, "bad")


def test_unknown_target_and_missing_replay(tmp_path, monkeypatch):
    monkeypatch.setenv("WAREHOUSE_CONTRACT_TARGET", "unsupported")
    with pytest.raises(ValueError, match="unsupported bridge target"):
        execute("SEL 1", tmp_path, "bad")
    monkeypatch.setenv("WAREHOUSE_CONTRACT_TARGET", "replay")
    with pytest.raises(FileNotFoundError):
        execute("SEL 1", tmp_path, "absent")
