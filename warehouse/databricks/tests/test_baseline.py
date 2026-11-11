from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from warehouse.databricks.baseline import delta_type, load, macro_result, main


def test_precision_timestamp_and_unbounded_view_numeric():
    assert delta_type("timestamp(0) without time zone") == "TIMESTAMP"
    assert delta_type("numeric") == "DECIMAL(38,18)"


def source_fixture(objects=(("base",), ("v_report",)), macros=(("m_totals",),)):
    source = MagicMock()
    def execute(statement, params=None):
        cursor = MagicMock()
        if isinstance(statement, str) and "FROM pg_tables" in statement:
            cursor.fetchall.return_value = list(objects)
        elif isinstance(statement, str) and "FROM sfx_td.routines" in statement:
            cursor.fetchall.return_value = list(macros)
        elif isinstance(statement, str) and "FROM pg_attribute" in statement:
            cursor.fetchall.return_value = [("id", "bigint")]
        else:
            cursor.fetchmany.side_effect = [[(1,)], []]
        return cursor
    source.execute.side_effect = execute
    return source


def target_fixture(count=1):
    target = MagicMock()
    target.execute.return_value = {"rows": [[count]], "statement_id": "published"}
    return target


def test_tables_views_and_macro_publish():
    from collections import deque
    target = target_fixture()
    with patch("warehouse.databricks.baseline.macro_result",
               return_value=([("id", "bigint")], deque([(1,)]))) as macro:
        receipts = load(source_fixture(), target, "billing")
    macro.assert_called_once()
    assert [r["source"] for r in receipts] == ["sfx_billing.base", "sfx_billing.v_report", "sfx_billing.m_totals"]
    assert all(r["rows"] == 1 and r["statement_id"] == "published" for r in receipts)
    statements = [c.args[0] for c in target.execute.call_args_list]
    assert sum(s.startswith("CREATE OR REPLACE TABLE") for s in statements) == 3
    assert all("run_token=dbx-d1111 expires=2026-11-24" in s for s in statements if s.startswith("CREATE"))


def test_empty_result_publishes_and_missing_objects_fails():
    source = source_fixture(objects=(("v_empty",),), macros=())
    original = source.execute.side_effect
    def execute(statement, params=None):
        cursor = original(statement, params)
        if not isinstance(statement, str):
            cursor.fetchmany.side_effect = [[]]
        return cursor
    source.execute.side_effect = execute
    assert load(source, target_fixture(0), "users")[0]["rows"] == 0
    with pytest.raises(RuntimeError, match="no baseline tables"):
        load(source_fixture(objects=(), macros=()), target_fixture(), "users")


def test_count_failure_cleans_stage_without_publish():
    target = target_fixture(9)
    with pytest.raises(RuntimeError, match="count mismatch"):
        load(source_fixture(macros=()), target, "billing")
    statements = [c.args[0] for c in target.execute.call_args_list]
    assert statements[-1].startswith("DROP TABLE IF EXISTS")
    assert not any(s.startswith("CREATE OR REPLACE") for s in statements)


@pytest.mark.parametrize("kwargs", [{"catalog": "other"}, {"schema": "dbx_d1111_after"}, {"batch": 0}])
def test_guardrails(kwargs):
    with pytest.raises(ValueError):
        load(MagicMock(), MagicMock(), "billing", **kwargs)


@pytest.mark.parametrize("empty", [False, True])
def test_macro_exec_metadata_and_values(empty):
    source = MagicMock()
    source.execute.return_value.fetchone.return_value = ("numeric",)
    description = [SimpleNamespace(name="amount", type_code=1700)]
    def execute(statement):
        source.execute.return_value.description = description
        runner.conn.execute("SELECT amount")
        runner.headers = ["amount"]
        runner.rows = [] if empty else [(Decimal("12.30"),)]
    with patch("warehouse.teradata.bteq.runner.Runner") as cls:
        runner = cls.return_value
        runner.errorcode = 0
        cls.side_effect = lambda **kw: (setattr(runner, "conn", kw["connection"]) or runner)
        runner.execute.side_effect = execute
        columns, rows = macro_result(source, "documents", "m_storage_totals")
    runner.execute.assert_called_once_with("EXEC SFX_documents.m_storage_totals(DATE '2026-11-01', DATE '2026-12-01')")
    assert columns == [("amount", "numeric(38,18)" if empty else "numeric(38,2)")]
    assert list(rows) == ([] if empty else [(Decimal("12.30"),)])


def test_macro_failure_is_not_published():
    with patch("warehouse.teradata.bteq.runner.Runner") as cls:
        cls.return_value.errorcode = 3700
        with pytest.raises(RuntimeError, match="baseline macro"):
            macro_result(MagicMock(), "billing", "m_currency_totals")


def test_repeatable_subject_cli(monkeypatch):
    monkeypatch.setenv("TD_DSN", "local-test")
    monkeypatch.setattr("sys.argv", ["baseline", "--subject", "billing", "--subject", "users"])
    with patch("psycopg.connect"), patch("warehouse.databricks.baseline.Warehouse") as warehouse, patch("warehouse.databricks.baseline.load", return_value=[]) as loader:
        main()
    assert [c.args[2] for c in loader.call_args_list] == ["billing", "users"]
    warehouse.assert_called_once_with(act="prove", consumer="billing")
