import ast
from decimal import Decimal
from unittest.mock import MagicMock

import nbformat
import pytest

from finance_nb.queries import NOTEBOOK, extract_queries
from finance_nb.warehouse import QUERY_TAG, WarehouseUnavailable, connect, run_query

TERADATA_ONLY = ("SEL ", "TOP ", "ZEROIFNULL", "NULLIFZERO", "FORMAT '", "1200101", "SFX_BILLING.", "CURRENT_DATE -")
SNOWFLAKE_ENV = {
    "SNOWFLAKE_ACCOUNT": "fake-account",
    "SNOWFLAKE_USER": "fake-user",
    "SNOWFLAKE_ROLE": "fake-role",
    "SNOWFLAKE_WAREHOUSE": "fake-wh",
    "SNOWFLAKE_PRIVATE_KEY": "fake-key",
}


def test_notebook_valid_clear_and_every_query_is_extractable():
    notebook = nbformat.read(NOTEBOOK, as_version=4)
    nbformat.validate(notebook)
    tagged = [c for c in notebook.cells if "warehouse-query" in c.metadata.get("tags", [])]
    assert set(extract_queries()) == {"revenue", "dso", "collections", "overdue"}
    assert len(tagged) == len(extract_queries())
    for cell in notebook.cells:
        if cell.cell_type == "code":
            assert cell.outputs == [] and cell.execution_count is None
            ast.parse(cell.source)
    for cell in tagged:
        tree = ast.parse(cell.source)
        variable = next(n.targets[0].id for n in tree.body if isinstance(n, ast.Assign))
        assert any(
            isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == "run_query" and isinstance(n.args[1], ast.Name)
            and n.args[1].id == variable
            for n in ast.walk(tree)
        )
    for sql in extract_queries().values():
        assert sql.lstrip().startswith(("SELECT ", "WITH "))
        assert not any(token in sql for token in TERADATA_ONLY)
        assert "SFX_D1110_AFTER.COMPAT." in sql


def test_notebook_has_no_teradata_logon():
    text = NOTEBOOK.read_text()
    assert "nb_dsci_pkhan" not in text and "tdprod" not in text and "password" not in text


def test_connection_uses_fake_without_driver_import():
    connector = MagicMock()
    config = {"account": "fake-account", "user": "fake-user", "private_key": b"fake-der"}
    assert connect(config, connector=connector) is connector.return_value
    connector.assert_called_once_with(**config, session_parameters={"QUERY_TAG": QUERY_TAG})


def test_default_connection_config_and_disabled_flag(monkeypatch):
    for name, value in SNOWFLAKE_ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr("finance_nb.warehouse._der_private_key", lambda key: b"der:" + key.encode())
    connector = MagicMock()
    connect(connector=connector)
    assert connector.call_args.kwargs == {
        "account": "fake-account", "user": "fake-user", "role": "fake-role",
        "warehouse": "fake-wh", "private_key": b"der:fake-key",
        "database": "SFX_D1110_AFTER", "schema": "COMPAT", "authenticator": "SNOWFLAKE_JWT",
        "session_parameters": {"QUERY_TAG": QUERY_TAG, "TIMEZONE": "UTC"},
    }
    assert QUERY_TAG == '{"run":"sfx-d1110","act":"consumers","consumer":"finance-notebook"}'
    connector.reset_mock()
    monkeypatch.setenv("FINANCE_WAREHOUSE_ENABLED", "false")
    with pytest.raises(RuntimeError, match="disabled"):
        connect(connector=connector)
    connector.assert_not_called()


@pytest.mark.parametrize("rows", [[("2026-10", Decimal("45000.50"))], []])
def test_query_dataframe_and_cursor_cleanup(rows):
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.description = [("MONTH_LABEL",), ("REVENUE",)]
    cursor.fetchall.return_value = rows
    result = run_query(connection, "SELECT fake")
    cursor.execute.assert_called_once_with("SELECT fake")
    assert list(result.columns) == ["MONTH_LABEL", "REVENUE"]
    assert list(result.itertuples(index=False, name=None)) == rows
    connection.cursor.return_value.__exit__.assert_called_once()
    connection.close.assert_not_called()


def test_missing_snowflake_settings_fail_before_connecting(monkeypatch):
    for name in SNOWFLAKE_ENV:
        monkeypatch.delenv(name, raising=False)
    connector = MagicMock()
    with pytest.raises(WarehouseUnavailable, match="^finance warehouse not configured$"):
        connect(connector=connector)
    connector.assert_not_called()


def test_errors_are_sanitized_and_cursor_closed(monkeypatch):
    for name, value in SNOWFLAKE_ENV.items():
        monkeypatch.setenv(name, value)
    with pytest.raises(WarehouseUnavailable, match="^finance warehouse unavailable$"):
        connect(connector=MagicMock())
    connector = MagicMock(side_effect=RuntimeError("private DSN"))
    with pytest.raises(WarehouseUnavailable, match="^finance warehouse unavailable$"):
        connect({"account": "fake", "private_key": b"der"}, connector=connector)
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value.execute.side_effect = RuntimeError("private SQL")
    with pytest.raises(WarehouseUnavailable, match="^finance query failed$"):
        run_query(connection, "SELECT fake")
    connection.cursor.return_value.__exit__.assert_called_once()


@pytest.mark.parametrize("source", ["x = 1", 'x_sql = ""', 'x_sql = build_sql()'])
def test_malformed_query_cell_rejected(tmp_path, source):
    notebook = nbformat.v4.new_notebook(cells=[
        nbformat.v4.new_code_cell(source, metadata={"tags": ["warehouse-query"]})
    ])
    path = tmp_path / "bad.ipynb"
    nbformat.write(notebook, path)
    with pytest.raises((ValueError, TypeError)):
        extract_queries(path)


def test_no_query_cells_rejected(tmp_path):
    path = tmp_path / "empty.ipynb"
    nbformat.write(nbformat.v4.new_notebook(), path)
    with pytest.raises(ValueError, match="no warehouse-query"):
        extract_queries(path)
