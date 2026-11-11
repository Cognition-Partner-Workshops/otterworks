import ast
from decimal import Decimal
from unittest.mock import MagicMock

import nbformat
import pytest

from finance_nb.queries import NOTEBOOK, extract_queries
from finance_nb.warehouse import WarehouseUnavailable, connect, run_query


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
    assert all(sql.lstrip().startswith(("SEL ", "WITH ")) for sql in extract_queries().values())


def test_connection_uses_fake_without_driver_import():
    connector = MagicMock()
    config = {"host": "fake-host", "user": "fake-user", "password": "not-a-real-password"} # gitleaks:allow
    assert connect(config, connector=connector) is connector.return_value
    connector.assert_called_once_with(**config)


def test_default_connection_config_and_disabled_flag(monkeypatch):
    connector = MagicMock()
    connect(connector=connector)
    assert connector.call_args.kwargs["user"] == "nb_dsci_pkhan"
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
    result = run_query(connection, "SEL fake")
    cursor.execute.assert_called_once_with("SEL fake")
    assert list(result.columns) == ["MONTH_LABEL", "REVENUE"]
    assert list(result.itertuples(index=False, name=None)) == rows
    connection.cursor.return_value.__exit__.assert_called_once()
    connection.close.assert_not_called()


def test_errors_are_sanitized_and_cursor_closed():
    connector = MagicMock(side_effect=RuntimeError("private DSN"))
    with pytest.raises(WarehouseUnavailable, match="^finance warehouse unavailable$"):
        connect(connector=connector)
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value.execute.side_effect = RuntimeError("private SQL")
    with pytest.raises(WarehouseUnavailable, match="^finance query failed$"):
        run_query(connection, "SEL fake")
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
