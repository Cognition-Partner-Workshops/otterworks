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
    v, _ = _convert_value(f(bson_type="array", rules=["csv_to_array"]), " a, b , c ")
    assert v == ["a", "b", "c"]
    v2, _ = _convert_value(f(bson_type="array", rules=["csv_to_array"]), "a,")
    assert v2 == ["a"], "trailing empty item dropped"


def test_csv_malformed_quarantines():
    for bad in ("a,,b", 'a,"b', "a,'b", "a\nb", "a;b", "a|b"):
        v, r = _convert_value(f(bson_type="array", rules=["csv_to_array"]), bad)
        assert v is _OMIT and r == "malformed csv", bad


def test_require_local_uri():
    from spec_loader import require_local_uri
    import pytest
    require_local_uri("mongodb://127.0.0.1:27017/ow_billing_offline")
    require_local_uri("mongodb://localhost/ow_billing_offline")
    with pytest.raises(ValueError):
        require_local_uri("mongodb://localhost.evil.example/x")
    with pytest.raises(ValueError):
        require_local_uri("mongodb://10.0.0.5:27017/x")


def test_datetime_with_time_format():
    v, r = _convert_value(f(source_type="VARCHAR2(20)", bson_type="date",
                            rules=["date_string_to_date:dbyHMS-30dd8b"],
                            date_format="%d-%b-%y %H:%M:%S"),
                          "15-JUN-26 12:30:45")
    assert v == dt.datetime(2026, 6, 15, 12, 30, 45) and r is None


def test_orphan_embed_rows_quarantined(tmp_path):
    """load_collections with a fake row source: child rows whose parent_key
    group no root row consumed land in quarantine with orphan_children count."""
    import json
    from spec_loader import load_collections

    spec = {"version": "1", "collections": [{
        "collection": "parents", "root_table": "PARENTS",
        "key": {"source": ["ID"], "target": "_id"},
        "fields": [],
        "embeds": [{"array_path": "kids", "child_table": "KIDS",
                    "parent_key": ["PARENT_ID"],
                    "key": {"source": ["KID_ID"], "target": "kidId"},
                    "fields": [{"source": "KNAME", "target": "kname",
                                "source_type": "VARCHAR2(10)",
                                "bson_type": "string", "rules": []}]}]}]}
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec))

    class FakeCursor:
        def __init__(self, rows):
            self._rows = rows
            self.description = None

        def execute(self, sql, params=None):
            table = "KIDS" if "KIDS" in sql else "PARENTS"
            data = {"PARENTS": [{"ID": "p1"}],
                    "KIDS": [{"PARENT_ID": "p1", "KID_ID": "k1", "KNAME": "a"},
                             {"PARENT_ID": "ghost", "KID_ID": "k2", "KNAME": "b"}]}[table]
            self._rows = data
            cols = [w.strip() for w in
                    sql.split("FROM")[0].replace("SELECT", "").split(",")]
            self.description = [(c,) for c in cols]

        def fetchall(self):
            return [tuple(r.get(c[0]) for c in self.description) for r in self._rows]

    class FakeConn:
        def cursor(self):
            return FakeCursor([])

    class FakeColl:
        def __init__(self):
            self.docs = {}

        class _Res:
            modified_count = 0

        def replace_one(self, filt, doc, upsert=False):
            self.docs[filt["_id"]] = doc
            return self._Res()

        def find(self, *a, **k):
            return [{"_id": i} for i in self.docs]

        def delete_one(self, filt):
            self.docs.pop(filt["_id"], None)

    class FakeDb:
        def __init__(self):
            self.coll = FakeColl()

        def __getitem__(self, name):
            return self.coll

    db = FakeDb()
    stats = load_collections(spec_path, ["parents"], FakeConn(), db)
    assert stats["parents"]["orphan_children"] == 1
    assert stats["parents"]["quarantined"] == 1
    assert db.coll.docs["p1"]["kids"] == [{"kidId": "k1", "kname": "a"}]


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
