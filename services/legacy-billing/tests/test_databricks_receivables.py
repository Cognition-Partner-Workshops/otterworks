from datetime import date
from decimal import Decimal

import pytest

import databricks_receivables as native
from finance_warehouse import COLUMNS


@pytest.mark.parametrize("a,b,expected", [
    ("5647.87", "6320.53", "0.89357538054561880095"),
    ("1.00", "3.00", "0.33333333333333333333"),
    ("3.00", "2.00", "1.5000000000000000"),
    ("0.01", "10000.00", "0.000001000000000000000000"),
    ("1.00", "0.00", None),
    ("1.00", None, None),
])
def test_source_ratio_preserves_bridge_precision(a, b, expected):
    result = native.source_ratio(Decimal(a), Decimal(b) if b else None)
    assert (str(result) if result is not None else None) == expected
    if expected is not None:
        assert result.as_tuple() == Decimal(expected).as_tuple()


def test_native_mapping_uses_exact_aggregates_and_bound_date(monkeypatch):
    calls = []

    def execute(sql, parameters, **kwargs):
        calls.append((sql, parameters, kwargs))
        return {"columns": list(COLUMNS[:-1]) + ["AMOUNT_DUE"], "statement_id": "test-id",
                "rows": [["ACC-1 ", "Generic", "USD ", date(2026, 12, 9),
                          Decimal("1.00"), Decimal("1.00"), 0, 0, 0, 0, Decimal("3.00")]]}

    monkeypatch.setattr(native, "execute", execute)
    warehouse = native.DatabricksReceivablesWarehouse("2026-11-09")
    row, = warehouse.ar_aging()
    assert list(row) == list(COLUMNS)
    assert row["OPEN_RATIO"] == "0.33333333333333333333"
    assert row["ACCOUNT_NO"] == "ACC-1"
    assert row["CURRENCY_CD"] == "USD"
    assert row["OLDEST_DUE_DATE"] == "2026-12-09"
    assert calls[0][1] == ["2026-11-09"] * 5


def test_native_import_and_init_do_not_open_connection(monkeypatch):
    monkeypatch.setattr(native, "execute", lambda *a, **kw: pytest.fail("unexpected warehouse connection"))
    native.DatabricksReceivablesWarehouse("2026-11-09")
    with pytest.raises(ValueError):
        native.DatabricksReceivablesWarehouse("2026-11-09' OR 1=1")
