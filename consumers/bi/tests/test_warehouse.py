from unittest.mock import MagicMock

import pytest

from contract.warehouse import EmulatorWarehouse, SnowflakeWarehouse


@pytest.mark.parametrize("user", [None, "svc_bi_semantic", "other"])
@pytest.mark.parametrize("target", ["teradata-emulator", "snowflake-semantics"])
def test_emulators_require_parity_identity(monkeypatch, user, target):
    monkeypatch.setenv("WAREHOUSE_CONTRACT_TARGET", target)
    if user is None:
        monkeypatch.delenv("TD_USER", raising=False)
    else:
        monkeypatch.setenv("TD_USER", user)
    with pytest.raises(ValueError):
        EmulatorWarehouse({})


def test_replay_needs_no_identity(monkeypatch):
    monkeypatch.setenv("WAREHOUSE_CONTRACT_TARGET", "replay")
    monkeypatch.delenv("TD_USER", raising=False)
    assert EmulatorWarehouse({}).names == {}


def test_parity_identity_accepted(monkeypatch):
    monkeypatch.setenv("WAREHOUSE_CONTRACT_TARGET", "teradata-emulator")
    monkeypatch.setenv("TD_USER", "svc_exit_parity")
    assert EmulatorWarehouse({}).names == {}


def client():
    warehouse = SnowflakeWarehouse()
    warehouse.credentials = dict.fromkeys(warehouse.credentials, "configured")
    warehouse.connection = MagicMock()
    return warehouse


@pytest.mark.parametrize("rows", [[], [(1,)]])
def test_snowflake_results_and_query_ids(rows, capsys):
    warehouse = client()
    cursor = warehouse.connection.cursor.return_value.__enter__.return_value
    cursor.sfqid = "query-id"
    cursor.description = [("VALUE",)]
    cursor.fetchall.return_value = rows
    assert warehouse.query("SELECT 1 AS VALUE", "sample") == [
        {"VALUE": row[0]} for row in rows
    ]
    assert warehouse.columns == ["VALUE"]
    assert warehouse.query_ids == [("sample", "query-id")]
    assert capsys.readouterr().out == "snowflake query_id sample query-id\n"


def test_query_error_records_id():
    warehouse = client()
    cursor = warehouse.connection.cursor.return_value.__enter__.return_value
    cursor.sfqid = "failed-id"
    cursor.execute.side_effect = RuntimeError("query failed")
    with pytest.raises(RuntimeError, match="query failed"):
        warehouse.query("SELECT 1", "failed")
    assert warehouse.query_ids == [("failed", "failed-id")]


@pytest.mark.parametrize("sql", ["DELETE FROM source", "SELECT 1; DROP TABLE source"])
def test_snowflake_rejects_writes(sql):
    warehouse = client()
    with pytest.raises(ValueError, match="read-only"):
        warehouse.query(sql)
    warehouse.connection.cursor.assert_not_called()


def test_snowflake_requires_credentials():
    warehouse = client()
    warehouse.credentials["ACCOUNT"] = None
    with pytest.raises(ValueError, match="not configured"):
        warehouse.query("SELECT 1")
