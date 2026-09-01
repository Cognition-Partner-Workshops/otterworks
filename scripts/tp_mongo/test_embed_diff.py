"""Tests for the embedded-child verification's comparison logic (no database needed)."""

from __future__ import annotations

import datetime as dt
import decimal
import sys
from pathlib import Path

from bson.decimal128 import Decimal128

sys.path.insert(0, str(Path(__file__).resolve().parent))

from embed_diff import comparable, diff_children, flatten

LINES = {"INV-1": [{"line_id": "L-1", "amount": Decimal128("10.00")},
                   {"line_id": "L-2", "amount": Decimal128("20.00")}]}


def diff(actual):
    return diff_children(LINES, actual, "invoices.lines", "line_id")


def test_identical_children_produce_no_findings():
    assert diff({"INV-1": [dict(line) for line in LINES["INV-1"]]}) == []


def test_a_changed_child_field_is_reported_with_its_path():
    findings = diff({"INV-1": [LINES["INV-1"][0],
                               {"line_id": "L-2", "amount": Decimal128("20.01")}]})
    assert [f["kind"] for f in findings] == ["child_field_diff"]
    assert findings[0]["array_path"] == "invoices.lines.amount"
    assert findings[0]["child"] == "L-2"


def test_a_dropped_child_is_reported_as_a_count_difference():
    findings = diff({"INV-1": LINES["INV-1"][:1]})
    assert [(f["kind"], f["expected"], f["actual"]) for f in findings] == [("child_count", 2, 1)]


def test_a_child_attached_to_the_wrong_parent_is_reported_on_both_parents():
    findings = diff({"INV-1": LINES["INV-1"][:1], "INV-2": LINES["INV-1"][1:]})
    assert [(f["parent"], f["kind"]) for f in findings] == [
        ("INV-1", "child_count"), ("INV-2", "child_count")]


def test_reordered_children_are_reported_rather_than_treated_as_a_set():
    findings = diff({"INV-1": list(reversed(LINES["INV-1"]))})
    assert {f["kind"] for f in findings} == {"child_order_or_identity"}


def test_a_field_missing_on_one_side_only_is_still_compared():
    findings = diff({"INV-1": [{"line_id": "L-1"}, LINES["INV-1"][1]]})
    assert findings[0]["array_path"] == "invoices.lines.amount"
    assert findings[0]["actual"] == "None"


def test_decimal128_compares_by_value_not_by_its_stored_scale():
    assert comparable(Decimal128("10.00")) == comparable(Decimal128(decimal.Decimal("10.00")))
    assert comparable(Decimal128("10.0")) == comparable(Decimal128("10.00"))
    assert comparable(Decimal128("10.01")) != comparable(Decimal128("10.00"))


def test_a_naive_datetime_is_read_as_utc():
    naive = dt.datetime(2024, 3, 1, 12, 0)
    assert comparable(naive) == comparable(naive.replace(tzinfo=dt.timezone.utc))


def test_a_zero_is_not_equal_to_an_empty_string_or_none():
    assert comparable(0) != comparable("")
    assert comparable(0) != comparable(None)
    assert comparable(False) != comparable(0)


def test_nested_child_values_are_flattened_to_dotted_paths():
    assert flatten({"line_no": 1, "legacy": {"invoice_dt": "01-JAN-24"}}) == {
        "line_no": 1, "legacy.invoice_dt": "01-JAN-24"}
