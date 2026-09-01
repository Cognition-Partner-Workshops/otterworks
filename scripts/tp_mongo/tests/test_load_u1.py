# ruff: noqa: DTZ001
import sys
from datetime import datetime
from pathlib import Path

from bson import Decimal128, Int64

sys.path.insert(0, str(Path(__file__).parents[1]))
import load_u1

MAPPING = load_u1.load_mapping()


def test_mapping_carries_all_source_columns():
    assert len(MAPPING["customers"]["fields"]) == 155
    assert len(MAPPING["customers_history"]["fields"]) == 158
    assert MAPPING["customers"]["embeds"][0]["key"]["target"] == "eav_id"


def test_parse_dd_mon_yy_strict():
    assert load_u1.parse_dd_mon_yy("22-DEC-22") == datetime(2022, 12, 22)
    for dirty in ["31-FEB-24", "00-XXX-00", "99-999-99", "1/1/1900", "N/A",
                  "29-FEB-23", "  -   -  ", "12-13-201"]:
        assert load_u1.parse_dd_mon_yy(dirty) is None
    assert load_u1.parse_dd_mon_yy(None) is None


def test_split_csv_well_formed_and_malformed():
    assert load_u1.split_csv("27907,56235,10789") == (["27907", "56235", "10789"], None)
    assert load_u1.split_csv("SPRING24,LEGACY") == (["SPRING24", "LEGACY"], None)
    assert load_u1.split_csv(None) == ([], None)
    for bad in [",,", "12345,,67890,", " , 99 ,", "NULL,NONE,", "0000000000000000000000,"]:
        assert load_u1.split_csv(bad) == (None, "empty_token")
    assert load_u1.split_csv("A;B;C") == (None, "invalid_token")


def test_convert_types_follow_mapping():
    fields = {f["source"]: f for f in MAPPING["customers"]["fields"]}
    assert load_u1.convert(fields["CUST_SEQ_NO"], 100056) == Int64(100056)
    assert isinstance(load_u1.convert(fields["CUST_SEQ_NO"], 1), Int64)
    assert load_u1.convert(fields["STATUS_CD"], 1) == 1
    assert load_u1.convert(fields["CUR_BAL_AMT"], 12.345) == Decimal128("12.34")
    assert load_u1.convert(fields["TAX_EXEMPT_YN"], "Y ") == "Y"
    assert load_u1.convert(fields["ADDR_LINE_2"], "") is None
    assert load_u1.convert(fields["CREATED_DT"], datetime(2022, 4, 12)) == datetime(2022, 4, 12)


def _row(**overrides):
    row = {f["source"]: None for f in MAPPING["customers"]["fields"]}
    row.update({"CUST_ID": "c1", "CUST_NAME": "Ann Lee", "PHONE1": "555-1", "PHONE1_TYPE_CD": 1,
                "SIGNUP_DT": "22-DEC-22", "RELATED_ACCT_IDS": "1,2", "PROMO_CODES_CSV": None})
    row.update(overrides)
    return row


def test_build_customer_embeds_sorted_attributes_and_tags_ns():
    attrs = [
        {"EAV_ID": 5, "ENTITY_TYPE": "CUSTOMER", "ENTITY_ID": "c1", "ATTR_NAME": "A",
         "ATTR_VALUE": "1", "ATTR_TYPE": "STR", "CREATED_DT": "01-JAN-20"},
        {"EAV_ID": 2, "ENTITY_TYPE": "CUSTOMER", "ENTITY_ID": "c1", "ATTR_NAME": "B",
         "ATTR_VALUE": "", "ATTR_TYPE": "STR", "CREATED_DT": "01-JAN-21"},
    ]
    doc, quarantine = load_u1.build_customer(MAPPING["customers"], _row(), attrs)
    assert doc["_id"] == "c1" and doc["ns"] == "mongo_205236"
    assert [a["eav_id"] for a in doc["attributes"]] == [Int64(2), Int64(5)]
    assert doc["attributes"][0]["attr_value"] is None
    assert doc["signup_dt"] == "22-DEC-22" and doc["signup_date"] == datetime(2022, 12, 22)
    assert doc["related_accounts"] == ["1", "2"] and doc["promo_codes"] == []
    assert doc["phones"] == [{"number": "555-1", "type_cd": 1}]
    assert "addr_line_1" in doc and doc["addr_line_1"] is None
    assert quarantine == []


def test_build_customer_quarantines_dirty_date_and_bad_csv_keeping_verbatim():
    doc, quarantine = load_u1.build_customer(
        MAPPING["customers"], _row(SIGNUP_DT="31-FEB-24", RELATED_ACCT_IDS="A;B;C"), []
    )
    assert doc["signup_dt"] == "31-FEB-24" and doc["signup_date"] is None
    assert doc["related_acct_ids"] == "A;B;C" and doc["related_accounts"] is None
    assert sorted(q["class"] for q in quarantine) == ["bad_csv_list", "dirty_signup_dt"]
    assert all(q["ns"] == "mongo_205236" and q["cust_id"] == "c1" for q in quarantine)


def test_build_counter_seeds_last_number_as_int64():
    doc = load_u1.build_counter("SEQ_CUSTOMER_MASTER", 125000)
    assert doc == {"_id": "seq_customer_master", "seq": Int64(125000),
                   "source_sequence": "SEQ_CUSTOMER_MASTER", "ns": "mongo_205236"}
    assert isinstance(doc["seq"], Int64)


def test_validate_target_db_rejects_other_databases():
    try:
        load_u1.validate_target_db("ow_tp_mongodb_other")
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_build_customer_quarantine_carries_runtime_batch():
    _, quarantine = load_u1.build_customer(
        MAPPING["customers"], _row(SIGNUP_DT="N/A", CONVERSION_BATCH_NO=12345678), [], 12345678
    )
    assert [q["batch_no"] for q in quarantine] == [12345678]


class _Cursor:
    def __init__(self, tables):
        self.tables = tables
        self.arraysize = 0
        self.description = []
        self.rows = []

    def execute(self, sql, params):
        if "USER_SEQUENCES" in sql:
            rows = self.tables["sequences"]
        elif "CUSTOMER_MASTER_HIST" in sql:
            assert "WHERE" not in sql and params == {}, sql
            rows = self.tables["history"]
        elif "ENTITY_ATTR_VALUE" in sql:
            assert "ENTITY_ID IN (SELECT CUST_ID FROM CUSTOMER_MASTER" in sql
            parents = {r["CUST_ID"] for r in self.tables["customers"]
                       if r["CONVERSION_BATCH_NO"] == 111}
            rows = [r for r in self.tables["attributes"] if r["ENTITY_ID"] in parents]
        else:
            assert params == {"batch_no": 111}, sql
            rows = [r for r in self.tables["customers"] if r["CONVERSION_BATCH_NO"] == 111]
        self.description = [(k,) for k in (rows[0] if rows else {})]
        self.rows = [tuple(r.values()) for r in rows]

    def fetchall(self):
        return self.rows


class _Connection:
    def __init__(self, tables):
        self.tables = tables

    def cursor(self):
        return _Cursor(self.tables)


def _tables():
    hist_cols = {f["source"]: None for f in MAPPING["customers_history"]["fields"]}
    return {
        "customers": [_row(CUST_ID="c1", CONVERSION_BATCH_NO=111),
                      _row(CUST_ID="c2", CONVERSION_BATCH_NO=222)],
        "attributes": [
            {"EAV_ID": 1, "ENTITY_TYPE": "CUSTOMER", "ENTITY_ID": "c1", "ATTR_NAME": "A",
             "ATTR_VALUE": "1", "ATTR_TYPE": "STR", "CREATED_DT": "01-JAN-20"},
            {"EAV_ID": 2, "ENTITY_TYPE": "CUSTOMER", "ENTITY_ID": "c2", "ATTR_NAME": "A",
             "ATTR_VALUE": "1", "ATTR_TYPE": "STR", "CREATED_DT": "01-JAN-20"},
        ],
        "history": [dict(hist_cols, HIST_ID=1, CUST_ID="c2", CONVERSION_BATCH_NO=222)],
        "sequences": [{"SEQUENCE_NAME": n, "LAST_NUMBER": 5} for n in load_u1.SEQUENCES],
    }


def test_extract_scopes_attributes_to_the_batch_and_history_per_mapping():
    assert MAPPING["customers_history"].get("root_where") is None
    source = load_u1.extract(_Connection(_tables()), MAPPING, 111)
    assert [r["CUST_ID"] for r in source["customers"]] == ["c1"]
    assert [r["EAV_ID"] for r in source["attributes"]] == [1]
    assert [r["HIST_ID"] for r in source["history"]] == [1]
    built = load_u1.build_documents(MAPPING, source, 111)
    assert [d["_id"] for d in built["customers"]] == ["c1"]
    assert built["embedded_attributes"] == 1
    assert [d["_id"] for d in built["customers_history"]] == [1]


def test_where_clause_binds_batch_or_is_empty():
    assert load_u1.where_clause(None) == ""
    assert load_u1.where_clause("conversion_batch_no = ${batch_no}") == \
        " WHERE conversion_batch_no = :batch_no"


def test_build_documents_rejects_empty_customer_batch():
    tables = _tables()
    source = {"customers": [], "attributes": [], "history": [], "sequences": tables["sequences"]}
    try:
        load_u1.build_documents(MAPPING, source, 999)
    except RuntimeError as exc:
        assert "999" in str(exc)
        return
    raise AssertionError("expected RuntimeError")


class _FakeCollection:
    def __init__(self, db, name):
        self.db, self.name, self.docs, self.indexes = db, name, [], []

    def insert_many(self, docs, ordered=True):
        if any(d.get("boom") for d in docs):
            raise RuntimeError("insert failed")
        self.docs.extend(docs)

    def create_index(self, keys, unique=False):
        self.indexes.append(keys)
        return "_".join(f"{k}_{v}" for k, v in keys)

    def count_documents(self, query):
        return sum(all(d.get(k) == v for k, v in query.items()) for d in self.docs)

    def rename(self, new_name, dropTarget=False):
        self.db.collections.pop(new_name, None)
        self.db.collections[new_name] = self.db.collections.pop(self.name)
        self.name = new_name


class _FakeDatabase:
    def __init__(self):
        self.collections = {}

    def drop_collection(self, name):
        self.collections.pop(name, None)

    def create_collection(self, name):
        self.collections[name] = _FakeCollection(self, name)

    def __getitem__(self, name):
        return self.collections[name]


def test_replace_collection_swaps_via_staging_and_keeps_old_copy_on_failure():
    db = _FakeDatabase()
    good = [{"_id": 1, "ns": load_u1.NS_VALUE}]
    report = load_u1.replace_collection(db, "customers", good, [[("a", 1)]], unique_first=True)
    assert report["inserted"] == 1 and list(db.collections) == ["customers"]
    try:
        load_u1.replace_collection(db, "customers", [{"_id": 2, "ns": load_u1.NS_VALUE, "boom": True}])
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected RuntimeError")
    assert list(db.collections) == ["customers"]
    assert db["customers"].docs == good
