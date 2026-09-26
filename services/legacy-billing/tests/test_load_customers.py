import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from bson.decimal128 import Decimal128

sys.path.insert(
    0,
    str(
        Path(__file__).resolve().parents[1] / "migration" / "mongo"
    ),
)

import load_customers


def field(**kwargs):
    spec = {"bson_type": "string", "rules": []}
    spec.update(kwargs)
    return spec


def test_none_and_empty_are_omitted():
    assert load_customers.convert_value(None, field()) == (
        load_customers.OMIT,
        None,
    )
    assert load_customers.convert_value("", field()) == (
        load_customers.OMIT,
        None,
    )
    assert load_customers.convert_value("   ", field()) == (
        load_customers.OMIT,
        None,
    )


def test_rstrip_spaces():
    f = field(rules=["rstrip_spaces"])
    assert load_customers.convert_value("A   ", f) == ("A", None)


def test_decimal_round_to_decimal128():
    f = field(bson_type="decimal", rules=["decimal_round"])
    value, reason = load_customers.convert_value(Decimal("1234.50"), f)
    assert reason is None
    assert isinstance(value, Decimal128)
    assert value.to_decimal() == Decimal("1234.50")


def test_long():
    f = field(bson_type="long")
    assert load_customers.convert_value(Decimal("42"), f) == (42, None)


def test_yn_to_bool():
    f = field(bson_type="bool", rules=["yn_to_bool"])
    assert load_customers.convert_value("Y", f) == (True, None)
    assert load_customers.convert_value("N", f) == (False, None)


def test_yn_to_bool_bad_flag_quarantined():
    f = field(bson_type="bool", rules=["yn_to_bool"])
    value, reason = load_customers.convert_value("X", f)
    assert value is load_customers.OMIT
    assert reason == "bad_flag"


@pytest.mark.parametrize("raw", ["31-FEB-24", "N/A"])
def test_bad_date_quarantined(raw):
    f = field(
        bson_type="date",
        rules=["date_string_to_date:dby-b3d57e"],
        date_format="%d-%b-%y",
    )
    value, reason = load_customers.convert_value(raw, f)
    assert value is load_customers.OMIT
    assert reason == "bad_date"


def test_date_string_to_date():
    f = field(
        bson_type="date",
        rules=["date_string_to_date:dby-b3d57e"],
        date_format="%d-%b-%y",
    )
    assert load_customers.convert_value("15-Jan-24", f) == (
        datetime(2024, 1, 15),
        None,
    )


def test_date_string_to_date_with_time():
    f = field(
        bson_type="date",
        rules=["date_string_to_date:dbyHMS-x"],
        date_format="%d-%b-%y %H:%M:%S",
    )
    assert load_customers.convert_value("15-Jan-24 08:30:00", f) == (
        datetime(2024, 1, 15, 8, 30, 0),
        None,
    )


def test_datetime_utc_truncate_ms_passthrough():
    f = field(bson_type="date", rules=["datetime_utc_truncate_ms"])
    raw = datetime(2024, 1, 15)
    assert load_customers.convert_value(raw, f) == (raw, None)


@pytest.mark.parametrize("raw", ["A;B;C", "NULL,NONE,"])
def test_malformed_csv_quarantined(raw):
    f = field(bson_type="array", rules=["csv_to_array"])
    value, reason = load_customers.convert_value(raw, f)
    assert value is load_customers.OMIT
    assert reason == "malformed_csv"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("12345,,67890,", ["12345", "67890"]), (",,", [])],
)
def test_csv_to_array(raw, expected):
    f = field(bson_type="array", rules=["csv_to_array"])
    assert load_customers.convert_value(raw, f) == (expected, None)


def test_derive_customer_defaults():
    derived = load_customers.derive_customer_defaults(
        {"custName": "acme co"}, 9001
    )
    assert derived["custSeqNo"] == 9001
    assert derived["custNameUpper"] == "ACME CO"
    assert derived["rowVersionNo"] == 1


def test_derive_customer_defaults_keeps_existing():
    derived = load_customers.derive_customer_defaults(
        {"custSeqNo": 5, "custName": "Acme", "rowVersionNo": 3}, 9001
    )
    assert derived["custSeqNo"] == 5
    assert derived["custNameUpper"] == "ACME"
    assert derived["rowVersionNo"] == 3
