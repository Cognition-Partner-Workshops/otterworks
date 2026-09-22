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
    for bad in ("a,,b", "a, ,b", "a,  ,b", 'a,"b', "a,'b", "a\nb", "a;b", "a|b"):
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
    import spec_loader
    from spec_loader import load_collections
    spec_loader.QUARANTINE_DIR = tmp_path / "quarantine"

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


def test_char_whitespace_only_omits():
    v, r = _convert_value(f(source_type="CHAR(4)", rules=["empty_string_is_null"]), "    ")
    assert v is _OMIT and r is None


def test_require_local_oracle_dsn():
    from spec_loader import require_local_oracle_dsn
    import pytest
    require_local_oracle_dsn("127.0.0.1:1521/FREEPDB1")
    require_local_oracle_dsn("localhost/FREEPDB1")
    with pytest.raises(ValueError):
        require_local_oracle_dsn("db.prod.internal:1521/FREEPDB1")
    with pytest.raises(ValueError):
        require_local_oracle_dsn("(DESCRIPTION=(ADDRESS=...) (CONNECT_DATA=...))")


def test_embed_order_by_and_predicates(tmp_path):
    import json
    import pytest
    from spec_loader import load_collections

    base = {"version": "1", "collections": [{
        "collection": "parents", "root_table": "PARENTS",
        "key": {"source": ["ID"], "target": "_id"}, "fields": [],
        "embeds": [{"array_path": "kids", "child_table": "KIDS",
                    "parent_key": ["PARENT_ID"],
                    "key": {"source": ["KID_ID"], "target": "kidId"},
                    "fields": []}]}]}
    sp = tmp_path / "s.json"
    sp.write_text(json.dumps(base))

    sqls = []

    class FakeCursor:
        description = None

        def execute(self, sql, params=None):
            sqls.append(sql)
            self._rows = []
            if "KIDS" in sql:
                self._rows = [{"PARENT_ID": "p1", "KID_ID": "k1"}]
                self.description = [("PARENT_ID",), ("KID_ID",)]
            else:
                self._rows = [{"ID": "p1"}]
                self.description = [("ID",)]

        def fetchall(self):
            return [tuple(r[c[0]] for c in self.description) for r in self._rows]

    class FakeConn:
        def cursor(self):
            return FakeCursor()

    class FakeColl:
        class _Res:
            modified_count = 0

        def replace_one(self, f, d, upsert=False):
            return self._Res()

        def find(self, *a, **k):
            return []

        def delete_one(self, f):
            pass

    class FakeDb:
        def __getitem__(self, n):
            return FakeColl()

    load_collections(sp, ["parents"], FakeConn(), FakeDb())
    kids_sql = next(s for s in sqls if "KIDS" in s)
    assert kids_sql.rstrip().endswith("ORDER BY PARENT_ID, KID_ID")

    # keyless embed: ORDER BY falls back to parent_key + all selected cols
    spec_nokey = json.loads(json.dumps(base))
    spec_nokey["collections"][0]["embeds"] = [{
        "array_path": "kids", "child_table": "KIDS",
        "parent_key": ["PARENT_ID"],
        "fields": [{"source": "KNAME", "target": "kname",
                    "source_type": "VARCHAR2(50)", "bson_type": "string",
                    "rules": []}]}]
    sp.write_text(json.dumps(spec_nokey))
    load_collections(sp, ["parents"], FakeConn(), FakeDb())
    nokey_sql = [s for s in sqls if "KIDS" in s][-1]
    assert nokey_sql.rstrip().endswith("ORDER BY PARENT_ID, KNAME")

    for bad in ("ID = 1; DROP TABLE x", "x = 1 UNION SELECT 2"):
        spec_bad = json.loads(json.dumps(base))
        spec_bad["collections"][0]["root_where"] = bad
        sp.write_text(json.dumps(spec_bad))
        with pytest.raises(ValueError):
            load_collections(sp, ["parents"], FakeConn(), FakeDb())

    full = json.loads((Path(__file__).resolve().parents[3]
                       / ".migration" / "03_mapping_spec.json").read_text())
    fp = tmp_path / "full.json"
    fp.write_text(json.dumps(full))
    names = [c["collection"] for c in full["collections"]]
    stats = load_collections(fp, names, FakeConn(), FakeDb())
    assert sorted(stats) == sorted(names)


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


def test_collections_not_in_spec_refused(tmp_path):
    import json
    import pytest
    from spec_loader import load_collections
    spec = {"version": "1", "collections": [
        {"collection": "codes", "root_table": "CODES",
         "key": {"source": ["ID"], "target": "_id"}, "fields": []}]}
    sp = tmp_path / "s.json"
    sp.write_text(json.dumps(spec))
    with pytest.raises(ValueError, match="collections not in spec"):
        load_collections(sp, ["nope"], None, None)


def test_embed_quarantine_uses_child_key_and_dedupes(tmp_path):
    """Malformed child value quarantines once (fields+child_fields overlap
    deduped) and is keyed by the embed's own key cols, not the root key."""
    import json
    import spec_loader
    from spec_loader import load_collections
    spec_loader.QUARANTINE_DIR = tmp_path / "quarantine"

    csv_field = {"source": "GL", "target": "gl",
                 "source_type": "VARCHAR2(100)", "bson_type": "array",
                 "rules": ["csv_to_array"]}
    st_field = {"source": "STATUS", "target": "status",
                "source_type": "CHAR(1)", "bson_type": "string",
                "rules": ["empty_string_is_null"]}
    st_field2 = {"source": "STATUS", "target": "legacyStatus",
                 "source_type": "CHAR(1)", "bson_type": "string",
                 "rules": ["empty_string_is_null"]}
    spec = {"version": "1", "collections": [{
        "collection": "parents", "root_table": "PARENTS",
        "key": {"source": ["ID"], "target": "_id"},
        "fields": [],
        "embeds": [{"array_path": "kids", "child_table": "KIDS",
                    "parent_key": ["PARENT_ID"],
                    "key": {"source": ["KID_ID"], "target": "kidId"},
                    "fields": [csv_field, st_field],
                    "child_fields": [csv_field, st_field2]}]}]}
    sp = tmp_path / "spec.json"
    sp.write_text(json.dumps(spec))

    class FakeCursor:
        def execute(self, sql, params=None):
            if "KIDS" in sql:
                self._rows = [{"PARENT_ID": "p1", "KID_ID": "k1",
                               "GL": "a,,b", "STATUS": "A"}]
            else:
                self._rows = [{"ID": "p1"}]
            cols = [w.strip() for w in
                    sql.split("FROM")[0].replace("SELECT", "").split(",")]
            self.description = [(c,) for c in cols]

        def fetchall(self):
            return [tuple(r.get(c[0]) for c in self.description) for r in self._rows]

    class FakeConn:
        def cursor(self):
            return FakeCursor()

    class FakeColl:
        class _Res:
            modified_count = 0

        def replace_one(self, f, d, upsert=False):
            return self._Res()

        def find(self, *a, **k):
            return []

        def delete_one(self, f):
            pass

    class FakeDb:
        def __getitem__(self, n):
            return FakeColl()

    docs = {}

    class RecColl(FakeColl):
        def replace_one(self, f, d, upsert=False):
            docs[f["_id"]] = d
            return self._Res()

    class RecDb:
        def __getitem__(self, n):
            return RecColl()

    stats = load_collections(sp, ["parents"], FakeConn(), RecDb())
    assert stats["parents"]["quarantined"] == 1
    qf = (tmp_path / "quarantine" / "parents.jsonl").read_text().strip()
    entry = json.loads(qf)
    assert entry["source_key"] == {"KID_ID": "k1"}
    assert "malformed" in entry["reason"]
    kid = docs["p1"]["kids"][0]
    assert kid["status"] == "A" and kid["legacyStatus"] == "A"


def _eav_fakes(rows_by_table, seed_docs):
    class FakeCursor:
        def execute(self, sql, params=None):
            table = [t for t in rows_by_table if t in sql][0]
            self._rows = rows_by_table[table]
            cols = [w.strip() for w in
                    sql.split("FROM")[0].replace("SELECT", "").split(",")]
            self.description = [(c,) for c in cols]

        def fetchall(self):
            return [tuple(r.get(c[0]) for c in self.description) for r in self._rows]

    class FakeConn:
        def cursor(self):
            return FakeCursor()

    class FakeColl:
        def __init__(self):
            self.docs = dict(seed_docs)

        class _Res:
            modified_count = 0

        def replace_one(self, f, d, upsert=False):
            self.docs[f["_id"]] = d
            return self._Res()

        def find(self, f=None, proj=None):
            def ok(d):
                for k, v in (f or {}).items():
                    if isinstance(v, dict) and "$ne" in v:
                        if d.get(k) == v["$ne"]:
                            return False
                    elif d.get(k) != v:
                        return False
                return True
            return [{"_id": i} for i, d in self.docs.items() if ok(d)]

        def delete_one(self, f):
            self.docs.pop(f["_id"], None)

    class FakeDb:
        def __init__(self):
            self.coll = FakeColl()

        def __getitem__(self, n):
            return self.coll

    return FakeConn(), FakeDb()


def _scoped_entry(root, target="eav", tw={"entityType": {"$ne": "CUSTOMER"}}):
    return {
        "collection": target, "root_table": root,
        "root_where": "ETYPE != 'CUSTOMER'",
        "target_where": json_dumps(tw),
        "key": {"source": ["ID"], "target": "_id"},
        "fields": [{"source": "ETYPE", "target": "entityType",
                    "source_type": "VARCHAR2(30)", "bson_type": "string",
                    "rules": ["empty_string_is_null"]}]}


import json as _json
def json_dumps(x):
    return _json.dumps(x)

def test_scoped_convergence_default_keeps_out_of_scope(tmp_path):
    """Default: the convergence delete is scoped to target_where, so an
    out-of-scope doc survives."""
    import json
    import spec_loader
    from spec_loader import load_collections
    spec_loader.QUARANTINE_DIR = tmp_path / "quarantine"
    spec = {"version": "1", "collections": [_scoped_entry("EAV")]}
    sp = tmp_path / "s.json"
    sp.write_text(json.dumps(spec))
    conn, db = _eav_fakes({"EAV": [{"ID": "e1", "ETYPE": "PLAN"}]},
                          {"z1": {"_id": "z1", "entityType": "CUSTOMER"}})
    load_collections(sp, ["eav"], conn, db)
    assert "z1" in db.coll.docs
    assert "e1" in db.coll.docs


def test_scoped_convergence_full_converge_deletes_out_of_scope(tmp_path):
    """full_converge names a collection the caller asserts it solely owns:
    the whole target converges, removing out-of-scope leftovers."""
    import json
    import spec_loader
    from spec_loader import load_collections
    spec_loader.QUARANTINE_DIR = tmp_path / "quarantine"
    spec = {"version": "1", "collections": [_scoped_entry("EAV")]}
    sp = tmp_path / "s.json"
    sp.write_text(json.dumps(spec))
    conn, db = _eav_fakes({"EAV": [{"ID": "e1", "ETYPE": "PLAN"}]},
                          {"z1": {"_id": "z1", "entityType": "CUSTOMER"}})
    load_collections(sp, ["eav"], conn, db, full_converge={"eav"})
    assert "z1" not in db.coll.docs
    assert "e1" in db.coll.docs
