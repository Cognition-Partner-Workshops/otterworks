import datetime as dt
from decimal import Decimal

import pytest

from runner import expr as X


def ev(text, row=None, types=None, params=None):
    return X.compile_expr(text, X.CompileContext(port_types=types or {}, params=params or {}))(row or {})


ROW = {"A": None, "B": "x", "N": 5, "D": dt.datetime(2024, 1, 31)}
TYPES = {"A": "string", "B": "string", "N": "integer", "D": "date/time"}


@pytest.mark.parametrize("text,expected", [
    ("IIF(A = 'x', 'Y', 'N')", "N"),           # null condition takes the false branch
    ("IIF(A = 'x', 'Y')", ""),                 # two-argument IIF defaults to empty string for strings
    ("IIF(N > 9, N)", 0),                      # ... and to zero for numbers
    ("IIF(ISNULL(A), 'missing', A)", "missing"),
    ("NVL(A, B)", "x"),
    ("ISNULL(A)", 1),
    ("A || B", "x"),                           # null concatenates as empty
    ("LTRIM('  ab ')", "ab "),
    ("RTRIM('  ab  ')", "  ab"),
    ("LTRIM(A)", None),
    ("DECODE(B, 'x', 1, 'y', 2, 0)", 1),
    ("DECODE(A, NULL, 'null-match', 'other')", "null-match"),
    ("DECODE(TRUE, N > 9, 'a', N > 3, 'b', 'c')", "b"),
    ("A = 1 OR 1 = 1", 1),
    ("A = 1 AND 1 = 0", 0),
    ("NOT A = 1", None),
    ("N + A", None),
])
def test_null_semantics(text, expected):
    assert ev(text, ROW, TYPES) == expected


def test_dates():
    assert ev("TO_DATE('2026-11-09 10:11:12', 'YYYY-MM-DD HH24:MI:SS')") == dt.datetime(2026, 11, 9, 10, 11, 12)
    assert ev("TO_DATE(A, 'YYYY-MM-DD')", ROW, TYPES) is None
    assert ev("ADD_TO_DATE(D, 'MM', 1)", ROW, TYPES) == dt.datetime(2024, 2, 29)
    assert ev("ADD_TO_DATE(D, 'DD', -31)", ROW, TYPES) == dt.datetime(2023, 12, 31)
    assert ev("ADD_TO_DATE(A, 'DD', 1)", {"A": None}, {"A": "date/time"}) is None
    assert ev("TO_CHAR(D, 'YYYYMMDD')", ROW, TYPES) == "20240131"
    assert ev("TRUNC(TO_DATE('2026-11-09 10:11:12', 'YYYY-MM-DD HH24:MI:SS'), 'DD')") == dt.datetime(2026, 11, 9)


def test_numbers_and_params():
    assert ev("ROUND(N * 2.555, 2)", ROW, TYPES) == Decimal("12.78")
    assert ev("ROUND(TOTAL * $$RATE / (1 + $$RATE), 2)", {"TOTAL": Decimal("108.25")}, {"TOTAL": "decimal"},
              {"$$RATE": Decimal("0.0825")}) == Decimal("8.25")
    assert ev("TO_DECIMAL('12.345', 2)") == Decimal("12.35") or ev("TO_DECIMAL('12.345', 2)") == Decimal("12.34")


def test_update_strategy_constants():
    assert (ev("DD_INSERT"), ev("DD_UPDATE"), ev("DD_DELETE"), ev("DD_REJECT")) == (0, 1, 2, 3)
    assert ev("IIF(ISNULL(A), DD_INSERT, DD_UPDATE)", ROW, TYPES) == X.DD_INSERT


def test_unknown_parameter_is_an_error():
    with pytest.raises(X.ExpressionError):
        ev("$$NOT_DEFINED + 1")
