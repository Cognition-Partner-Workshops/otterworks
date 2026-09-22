"""Unit tests for spec_loader doc building / canonicalization (no DB)."""

import datetime as dt
import decimal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "loaders"))

from bson.decimal128 import Decimal128  # noqa: E402
from spec_loader import _convert_value, _build_key, _apply_fields, _OMIT  # noqa: E402


def f(source="COL", target="col", source_type="VARCHAR2(10)", bson_type="string",
      rules=None, date_format=None):
    d = {"source": source, "target": target, "source_type": source_type,
         "bson_type": bson_type, "rules": rules or []}
    if date_format:
        d["date_format"] = date_format
    return d


def test_char_rstrip():
    v, r = _convert_value(f(source_type="CHAR(10)"), "abc       ")
    assert v == "abc" and r is None


def test_varchar_rstrip_via_rule():
    v, _ = _convert_value(f(rules=["rstrip_spaces"]), "abc   ")
    assert v == "abc"


def test_empty_string_is_null_omits():
    v, r = _convert_value(f(rules=["empty_string_is_null"]), "")
    assert v is _OMIT and r is None


def test_none_omits():
    v, _ = _convert_value(f(), None)
    assert v is _OMIT


def test_yn_flag_to_bool_when_bson_bool():
    assert _convert_value(f(bson_type="bool", rules=["yn_to_bool"]), "Y")[0] is True
    assert _convert_value(f(bson_type="bool"), "N")[0] is False
    assert _convert_value(f(bson_type="string"), "Y")[0] == "Y", "only bool fields convert"
    assert _convert_value(f(bson_type="bool"), "MAYBE")[0] == "MAYBE"


def test_decimal_scale():
    v, _ = _convert_value(f(source_type="NUMBER(10,2)", bson_type="decimal",
                          rules=["decimal_round:s2"]), "123.456")
    assert isinstance(v, Decimal128)
    assert v.to_decimal() == decimal.Decimal("123.46")


def test_number_p0_to_int():
    v, _ = _convert_value(f(source_type="NUMBER(4)", bson_type="long"), "42")
    assert v == 42 and isinstance(v, int)


def test_text_date_parses():
    v, r = _convert_value(f(source_type="VARCHAR2(9)", bson_type="date",
                            rules=["date_string_to_date:x"], ), "05-JAN-24")
    assert v == dt.datetime(2024, 1, 5) and r is None
    v2, _ = _convert_value(f(source_type="VARCHAR2(10)", bson_type="date",
                             rules=["date_string_to_date:x"], date_format="%Y%m%d"),
                           "20240105")
    assert v2 == dt.datetime(2024, 1, 5)


def test_text_date_unparseable_quarantines():
    v, r = _convert_value(f(source_type="VARCHAR2(9)", bson_type="date",
                            rules=["date_string_to_date:x"]), "31-FEB-24")
    assert v is _OMIT and "unparseable" in r


def test_csv_to_array():
    v, _ = _convert_value(f(bson_type="array", rules=["csv_to_array"]), " a, b ,, c ")
    assert v == ["a", "b", "c"]


def test_composite_key_subdocument():
    row = {"CODE_TYPE": "T", "CODE_VAL": 10}
    key = {"source": ["CODE_TYPE", "CODE_VAL"], "target": ["codeType", "codeVal"]}
    assert _build_key(row, key) == {"codeType": "T", "codeVal": 10}


def test_single_key_scalar():
    key = {"source": ["ID"], "target": "_id"}
    assert _build_key({"ID": "x"}, key) == "x"


def test_apply_fields_omits_missing_and_quarantines():
    row = {"A": None, "B": "", "C": "bad-date"}
    fields = [f("A", "a", rules=["empty_string_is_null"]),
              f("B", "b", rules=["empty_string_is_null"]),
              f("C", "c", source_type="VARCHAR2(9)", bson_type="date",
                rules=["date_string_to_date:x"])]
    doc, q = {}, []
    _apply_fields(row, fields, doc, q, {"A"})
    assert doc == {}
    assert len(q) == 1 and q[0]["field"] == "C"
