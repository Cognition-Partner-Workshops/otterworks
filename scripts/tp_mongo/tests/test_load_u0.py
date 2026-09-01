from decimal import Decimal
import sys
from pathlib import Path

import pytest
from bson import Decimal128, Int64

sys.path.insert(0, str(Path(__file__).parents[1]))
import load_u0


def test_vc_empty_string_is_none():
    assert load_u0.vc("") is None
    assert load_u0.vc("x") == "x"


def test_ch_strips_trailing_spaces_and_empty_is_none():
    assert load_u0.ch("Y ") == "Y"
    assert load_u0.ch("  ") is None


def test_dec_rounds_half_even():
    assert load_u0.dec(12.345, 2) == Decimal128("12.34")
    assert load_u0.dec("0.1234565", 6) == Decimal128("0.123456")


def test_lng_is_bson_int64():
    value = load_u0.lng(5)
    assert isinstance(value, Int64)
    assert value == 5


def test_transform_codes_uses_comparison_key_without_explicit_id():
    document = load_u0.transform_codes(
        {"CODE_TYPE": "SUB_STATUS", "CODE_VAL": 10, "CODE_DESC": "Active"}
    )
    assert document["_key"] == "SUB_STATUS:10"
    assert "_id" not in document


def test_transform_plan_uses_expected_bson_types():
    document = load_u0.transform_plans(
        {
            "ID": "PLAN-1",
            "CODE": "starter",
            "TIER_CD": 1,
            "MONTHLY_FEE": "12.345",
            "INCLUDED_UNITS": 5,
            "OVERAGE_RATE": "0.1234565",
            "ACTIVE_YN": "Y ",
        }
    )
    assert document["_id"] == "PLAN-1"
    assert isinstance(document["monthly_fee"], Decimal128)
    assert isinstance(document["included_units"], Int64)
    assert isinstance(document["overage_rate"], Decimal128)
    assert document["monthly_fee"] == Decimal128("12.34")
    assert document["overage_rate"] == Decimal128("0.123456")
    assert document["active_yn"] == "Y"


def test_target_db_guard_rejects_wrong_name():
    with pytest.raises(ValueError):
        load_u0.validate_target_db("wrong-db")
