from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pandas as pd
import pytest
from migration.snowflake.gate.compare import UnitResult, compare_frames


def compare(source: list[dict[str, object]], target: list[dict[str, object]]) -> UnitResult:
    return compare_frames(
        pd.DataFrame(source, columns=["id", "value"]),
        pd.DataFrame(target, columns=["id", "value"]),
        ["id"],
        ["value"],
    )


def test_identical_frames_pass() -> None:
    result = compare([{"id": 1, "value": "same"}], [{"id": 1, "value": "same"}])
    assert result.status == "PASS"
    assert result.differing_key_count == 0


def test_value_difference_reports_key_and_column() -> None:
    result = compare([{"id": 3, "value": "left"}], [{"id": 3, "value": "right"}])
    assert result.status == "DIVERGE"
    assert result.differences[0]["key"] == {"id": "3"}
    assert result.differences[0]["column"] == "value"


def test_missing_row_in_snowflake() -> None:
    result = compare([{"id": 1, "value": "a"}], [])
    assert result.differences[0]["column"] == "<missing in snowflake>"


def test_missing_row_in_sqlserver() -> None:
    result = compare([], [{"id": 1, "value": "a"}])
    assert result.differences[0]["column"] == "<missing in sqlserver>"


def test_duplicate_keys_diverge() -> None:
    result = compare(
        [{"id": 1, "value": "a"}, {"id": 1, "value": "b"}],
        [{"id": 1, "value": "a"}],
    )
    assert result.status == "DIVERGE"
    assert result.differences[0]["column"] == "<duplicate key>"


def test_duplicate_target_keys_diverge() -> None:
    result = compare(
        [{"id": 1, "value": "a"}],
        [{"id": 1, "value": "a"}, {"id": 1, "value": "a"}],
    )
    assert result.status == "DIVERGE"
    assert result.differences[0]["column"] == "<duplicate key>"


def test_null_matches_null_but_not_a_value() -> None:
    assert compare([{"id": 1, "value": None}], [{"id": 1, "value": float("nan")}]).status == "PASS"
    assert compare([{"id": 1, "value": None}], [{"id": 1, "value": "value"}]).status == "DIVERGE"


def test_decimal_scale_is_ignored() -> None:
    assert (
        compare(
            [{"id": 1, "value": Decimal("1.50")}],
            [{"id": 1, "value": Decimal("1.5")}],
        ).status
        == "PASS"
    )


def test_integer_matches_decimal() -> None:
    assert compare([{"id": 1, "value": 7}], [{"id": 1, "value": Decimal("7.0")}]).status == "PASS"


def test_floats_are_compared_exactly() -> None:
    result = compare([{"id": 1, "value": 0.3}], [{"id": 1, "value": 0.1 + 0.2}])
    assert result.status == "DIVERGE"


def test_column_names_match_without_case_sensitivity() -> None:
    result = compare_frames(
        pd.DataFrame([{"ID": 1, "Value": "same"}]),
        pd.DataFrame([{"id": 1, "value": "same"}]),
        ["id"],
        ["value"],
    )
    assert result.status == "PASS"


def test_difference_count_exceeds_ten_but_details_are_capped() -> None:
    source = [{"id": index, "value": "left"} for index in range(15)]
    target = [{"id": index, "value": "right"} for index in range(15)]
    result = compare(source, target)
    assert result.differing_key_count == 15
    assert len(result.differences) == 10


def test_string_trailing_space_is_significant() -> None:
    assert compare([{"id": 1, "value": "text"}], [{"id": 1, "value": "text "}]).status == "DIVERGE"


def test_aware_datetimes_compare_as_utc() -> None:
    source = datetime(2026, 9, 15, 9, tzinfo=UTC)
    target = datetime.fromisoformat("2026-09-15T05:00:00-04:00")
    assert compare([{"id": 1, "value": source}], [{"id": 1, "value": target}]).status == "PASS"


def test_missing_manifest_column_is_an_error() -> None:
    with pytest.raises(ValueError, match="manifest column"):
        compare_frames(pd.DataFrame([{"id": 1}]), pd.DataFrame([{"id": 1}]), ["id"], ["value"])
