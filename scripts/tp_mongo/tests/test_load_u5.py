# ruff: noqa: DTZ001
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from bson import Decimal128, Int64

sys.path.insert(0, str(Path(__file__).parents[1]))
import load_u5


def test_ts_floors_microseconds_and_passes_none():
    value = datetime(2026, 1, 2, 3, 4, 5, 123456, tzinfo=timezone.utc)
    assert load_u5.ts(value) == datetime(2026, 1, 2, 3, 4, 5, 123000)
    assert load_u5.ts(None) is None


def test_dec_rounds_half_even_to_requested_scale():
    assert load_u5.dec("12.345", 2) == Decimal128("12.34")
    assert load_u5.dec("12.355", 2) == Decimal128("12.36")
    assert load_u5.dec(Decimal("1.2"), 2) == Decimal128("1.20")


def test_transformers_use_expected_bson_types_and_namespace():
    when = datetime(2026, 1, 2, 3, 4, 5, 123456)
    subscription = load_u5.transform_subscriptions(
        {
            "ID": "sub-1",
            "TENANT_ID": "tenant-1",
            "PLAN_ID": "plan-1",
            "STARTS_ON": when,
            "ENDS_ON": None,
            "STATUS_CD": 1,
            "SUSPENDED_ON": None,
        }
    )
    assert subscription["_id"] == subscription["id"] == "sub-1"
    assert subscription["starts_on"] == when.replace(microsecond=123000)
    assert isinstance(subscription["status_cd"], int)
    assert subscription["ns"] == load_u5.NS_VALUE

    history = load_u5.transform_subscriptions_history(
        {
            "HIST_ID": 4,
            "HIST_DT": "01-JAN-26 00:00:00",
            "HIST_OP": "UPD",
            "ID": "sub-1",
            "TENANT_ID": "tenant-1",
            "PLAN_ID": "plan-1",
            "STARTS_ON": when,
            "ENDS_ON": None,
            "STATUS_CD": 1,
            "SUSPENDED_ON": None,
        }
    )
    assert isinstance(history["_id"], Int64)
    assert isinstance(history["hist_id"], Int64)

    usage = load_u5.transform_usage_events(
        {
            "ID": "event-1",
            "TENANT_ID": "tenant-1",
            "OCCURRED_AT": when,
            "UNITS": 7,
            "KIND_CD": 2,
        }
    )
    assert isinstance(usage["units"], Int64)
    assert isinstance(usage["kind_cd"], int)
    assert usage["ns"] == load_u5.NS_VALUE

    result = load_u5.transform_rating_result(
        {
            "ID": "result-1",
            "PERIOD_ID": "period-1",
            "SUBSCRIPTION_ID": "sub-1",
            "USED_UNITS": 1,
            "QUOTA_UNITS": 2,
            "ROLLOVER_UNITS": 3,
            "BILLABLE_UNITS": 4,
            "OVERAGE_AMOUNT": "1.235",
            "CREATED_AT": when,
        }
    )
    assert all(isinstance(result[name], Int64) for name in
               ("used_units", "quota_units", "rollover_units", "billable_units"))
    assert result["overage_amount"] == Decimal128("1.24")

    invoice_line = load_u5.transform_invoice_line(
        {
            "ID": "line-1",
            "INVOICE_ID": "invoice-1",
            "LINE_NO": 1,
            "LINE_TYPE": "BASE",
            "DESCRIPTION": "Base",
            "AMOUNT": "2.345",
        }
    )
    assert isinstance(invoice_line["line_no"], int)
    assert invoice_line["amount"] == Decimal128("2.34")

    assert isinstance(load_u5.transform_dunning_attempts(
        {"ID": "d", "TENANT_ID": "t", "INVOICE_ID": "i", "ATTEMPT_NO": 1,
         "SCHEDULED_FOR": when, "STATUS_CD": 2}
    )["attempt_no"], int)
    assert isinstance(load_u5.transform_billing_audit_log(
        {"LOG_ID": 2, "LOGGED_AT": when, "MODULE": "m", "MESSAGE": "x"}
    )["log_id"], Int64)


def test_embeds_group_in_order_and_parents_without_children_get_empty_arrays():
    periods = [
        {"ID": "p1", "TENANT_ID": "t", "PERIOD_START": datetime(2026, 1, 1),
         "PERIOD_END": datetime(2026, 1, 31)},
        {"ID": "p2", "TENANT_ID": "t", "PERIOD_START": datetime(2026, 2, 1),
         "PERIOD_END": datetime(2026, 2, 28)},
    ]
    results = [
        {"ID": "r2", "PERIOD_ID": "p1", "SUBSCRIPTION_ID": "s", "USED_UNITS": 2,
         "QUOTA_UNITS": 2, "ROLLOVER_UNITS": 0, "BILLABLE_UNITS": 2,
         "OVERAGE_AMOUNT": "0", "CREATED_AT": datetime(2026, 1, 2)},
        {"ID": "r1", "PERIOD_ID": "p1", "SUBSCRIPTION_ID": "s", "USED_UNITS": 1,
         "QUOTA_UNITS": 2, "ROLLOVER_UNITS": 0, "BILLABLE_UNITS": 1,
         "OVERAGE_AMOUNT": "0", "CREATED_AT": datetime(2026, 1, 1)},
    ]
    built = load_u5.build_rating_periods(periods, results)
    assert [result["id"] for result in built[0]["results"]] == ["r1", "r2"]
    assert built[1]["results"] == []

    invoices = [
        {"ID": "i1", "TENANT_ID": "t", "PERIOD_ID": "p", "ISSUED_AT": datetime(2026, 1, 1),
         "SUBTOTAL": "1", "TAX": "0", "TOTAL": "1", "STATUS_CD": 1},
    ]
    lines = [
        {"ID": "l2", "INVOICE_ID": "i1", "LINE_NO": 2, "LINE_TYPE": "TAX",
         "DESCRIPTION": "tax", "AMOUNT": "0"},
        {"ID": "l1", "INVOICE_ID": "i1", "LINE_NO": 1, "LINE_TYPE": "BASE",
         "DESCRIPTION": "base", "AMOUNT": "1"},
    ]
    assert [line["line_no"] for line in load_u5.build_billing_invoices(invoices, lines)[0]["lines"]] == [1, 2]


def test_orphan_embedded_rows_raise_runtime_error():
    with pytest.raises(RuntimeError):
        load_u5.build_rating_periods(
            [{"ID": "p1", "TENANT_ID": "t", "PERIOD_START": None, "PERIOD_END": None}],
            [{"ID": "r1", "PERIOD_ID": "missing"}],
        )
    with pytest.raises(RuntimeError):
        load_u5.build_billing_invoices(
            [{"ID": "i1", "TENANT_ID": "t", "PERIOD_ID": "p", "ISSUED_AT": None,
              "SUBTOTAL": 0, "TAX": 0, "TOTAL": 0, "STATUS_CD": 1}],
            [{"ID": "l1", "INVOICE_ID": "missing"}],
        )


def test_validator_and_unit_scope_contracts():
    properties = load_u5.USAGE_EVENTS_VALIDATOR["$jsonSchema"]["properties"]
    assert properties["units"]["minimum"] == 1
    assert properties["units"]["bsonType"] == "long"
    assert set(load_u5.UNIT_COLLECTIONS).isdisjoint(
        {"invoices", "customers", "counters", "codes", "tenants", "plans"}
    )
    assert load_u5.TTL_SECONDS == 7776000


def test_target_db_guard_rejects_other_databases():
    with pytest.raises(ValueError):
        load_u5.validate_target_db("wrong-db")


class _FakeCollection:
    def __init__(self, database, name, documents=None, options=None):
        self.database = database
        self.name = name
        self.documents = list(documents or [])
        self.options = options or {}
        self.indexes = []

    def insert_many(self, documents, ordered=True):
        if self.database.fail_inserts:
            raise RuntimeError("insert failed")
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


class _FakeDatabase:
    def __init__(self):
        self.collections = {}
        self.fail_inserts = False

    def drop_collection(self, name):
        self.collections.pop(name, None)

    def create_collection(self, name, **options):
        self.collections[name] = _FakeCollection(self, name, options=options)
        return self.collections[name]

    def list_collection_names(self):
        return list(self.collections)

    def __getitem__(self, name):
        return self.collections[name]


def test_load_collection_stages_before_swap_and_carries_validator_options():
    database = _FakeDatabase()
    previous = [{"_id": "old", "ns": load_u5.NS_VALUE}]
    database.collections["usage_events"] = _FakeCollection(
        database, "usage_events", previous
    )
    database.fail_inserts = True
    row = {
        "ID": "event-1",
        "TENANT_ID": "tenant-1",
        "OCCURRED_AT": datetime(2026, 1, 2),
        "UNITS": 1,
        "KIND_CD": 2,
    }

    with pytest.raises(RuntimeError, match="insert failed"):
        load_u5.load_collection(database, "usage_events", [row])
    assert database["usage_events"].documents == previous
    assert "usage_events__staging" not in database.list_collection_names()

    database.fail_inserts = False
    report = load_u5.load_collection(database, "usage_events", [row])
    assert report["inserted"] == 1
    assert database["usage_events"].documents[0]["id"] == "event-1"
    assert database["usage_events"].options == {
        "validator": load_u5.USAGE_EVENTS_VALIDATOR,
        "validationLevel": "strict",
        "validationAction": "error",
    }
    assert "usage_events__staging" not in database.list_collection_names()
