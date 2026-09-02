import sys
from pathlib import Path

import pytest
from bson import Int64

sys.path.insert(0, str(Path(__file__).parents[1]))
import load_replay_u6
import load_u5


class _Collection:
    def __init__(self, database, name, options=None):
        self.database = database
        self.name = name
        self.options = options or {}
        self.documents = []
        self.indexes = []

    def insert_many(self, documents, ordered=True):
        self.documents.extend(documents)

    def create_index(self, keys, **options):
        self.indexes.append((keys, options))
        return "_".join(f"{key}_{direction}" for key, direction in keys)

    def count_documents(self, query):
        return sum(
            all(document.get(key) == value for key, value in query.items())
            for document in self.documents
        )

    def rename(self, new_name, dropTarget=False):
        if dropTarget:
            self.database.collections.pop(new_name, None)
        self.database.collections[new_name] = self.database.collections.pop(self.name)
        self.name = new_name


class _Database:
    def __init__(self):
        self.collections = {}

    def drop_collection(self, name):
        self.collections.pop(name, None)

    def create_collection(self, name, **options):
        self.collections[name] = _Collection(self, name, options)
        return self.collections[name]

    def list_collection_names(self):
        return list(self.collections)

    def __getitem__(self, name):
        return self.collections[name]


def test_produced_collection_names_are_prefixed():
    names = [
        load_replay_u6.collection_name(collection)
        for collection in load_replay_u6.UNIT_COLLECTIONS
    ]
    names += [
        load_replay_u6.collection_name(collection, staging=True)
        for collection in load_replay_u6.UNIT_COLLECTIONS
    ]
    names.append(load_replay_u6.collection_name("counters"))
    assert names
    assert all(name.startswith("replay_u6_") for name in names)


def test_validate_target_db_rejects_other_databases():
    with pytest.raises(ValueError):
        load_replay_u6.validate_target_db("wrong-db")


def test_load_collection_only_touches_prefixed_names():
    database = _Database()
    source = {}
    row = {
        "CODE_TYPE": "SUB_STATUS",
        "CODE_VAL": 10,
        "CODE_DESC": "Active",
    }
    report = load_replay_u6.load_collection(database, "codes", [row], source)
    assert report["inserted"] == 1
    assert all(name.startswith("replay_u6_") for name in database.list_collection_names())


def test_seed_counters_uses_int64_last_number_minus_one():
    database = _Database()
    seeds = load_replay_u6.seed_counters(
        database,
        {
            "seq_billing_audit_log": Int64(4),
            "seq_subscriptions_hist": Int64(8),
        },
    )
    assert seeds["seq_billing_audit_log"]["seq"] == Int64(3)
    assert seeds["seq_subscriptions_hist"]["seq"] == Int64(7)
    assert seeds["seq_billing_audit_log"]["source_sequence"] == "SEQ_BILLING_AUDIT_LOG"
    assert seeds["seq_subscriptions_hist"]["source_sequence"] == "SEQ_SUBSCRIPTIONS_HIST"
    assert seeds["seq_billing_audit_log"]["ns"] == load_replay_u6.NS_VALUE
    assert seeds["seq_subscriptions_hist"]["ns"] == load_replay_u6.NS_VALUE
    assert all(
        isinstance(document["seq"], Int64)
        for document in database["replay_u6_counters"].documents
    )


def test_create_index_uses_logical_collection_and_prefixed_physical_name():
    expected = {"codes": [(
        [("code_type", 1), ("code_val", 1)],
        {"unique": True},
    )]}
    expected.update(
        {
            logical: (
                [load_u5.INDEXES[logical]]
                if load_u5.INDEXES[logical][0]
                else []
            )
            for logical in load_u5.INDEXES
        }
    )
    expected["billing_invoices"].append(
        ([("status_cd", 1), ("issued_at", 1)], {})
    )

    for logical, index_specs in expected.items():
        database = _Database()
        physical = load_replay_u6.collection_name(logical, staging=True)
        database.create_collection(physical)

        index_names = load_replay_u6._create_index(database, logical, physical)

        assert database[physical].indexes == index_specs
        assert index_names == [
            "_".join(f"{key}_{direction}" for key, direction in keys)
            for keys, _ in index_specs
        ]
        assert physical.startswith("replay_u6_")


def test_seed_counters_validates_sequences_before_mutating_database():
    class OperationDatabase(_Database):
        def __init__(self):
            super().__init__()
            self.operations = []

        def drop_collection(self, name):
            self.operations.append(("drop", name))
            super().drop_collection(name)

        def create_collection(self, name, **options):
            self.operations.append(("create", name))
            return super().create_collection(name, **options)

    database = OperationDatabase()
    with pytest.raises(LookupError, match="seq_subscriptions_hist"):
        load_replay_u6.seed_counters(
            database,
            {"seq_billing_audit_log": Int64(4)},
        )
    assert database.operations == []
    assert database.collections == {}
