"""Compare two in-memory result sets using manifest column names."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pandas as pd

DUPLICATE_KEY = "<duplicate key>"
MISSING_IN_SNOWFLAKE = "<missing in snowflake>"
MISSING_IN_SQLSERVER = "<missing in sqlserver>"


@dataclass
class UnitResult:
    status: str
    source_rows: int
    target_rows: int
    differing_key_count: int
    differences: list[dict[str, Any]]


def _as_scalar(value: Any) -> Any:
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        try:
            return value.item()
        except (TypeError, ValueError):
            pass
    return value


def _is_null(value: Any) -> bool:
    value = _as_scalar(value)
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _datetime_equal(source: Any, target: Any) -> bool:
    source_aware = source.utcoffset() is not None
    target_aware = target.utcoffset() is not None
    if source_aware != target_aware:
        return False
    if source_aware:
        source = source.astimezone(UTC).replace(tzinfo=None)
        target = target.astimezone(UTC).replace(tzinfo=None)
    return source == target


def _equal(source: Any, target: Any) -> bool:
    source = _as_scalar(source)
    target = _as_scalar(target)
    if _is_null(source) or _is_null(target):
        return _is_null(source) and _is_null(target)
    if isinstance(source, (datetime, pd.Timestamp)) and isinstance(
        target, (datetime, pd.Timestamp)
    ):
        return _datetime_equal(source, target)
    if isinstance(source, Decimal) or isinstance(target, Decimal):
        try:
            return bool(source == target)
        except (TypeError, ValueError):
            return False
    try:
        return bool(source == target)
    except (TypeError, ValueError):
        return False


def _display(value: Any) -> str | None:
    value = _as_scalar(value)
    if _is_null(value):
        return "NULL"
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _sort_component(value: Any) -> tuple[int, Any]:
    value = _as_scalar(value)
    if _is_null(value):
        return (0, "")
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        try:
            return (1, Decimal(str(value)))
        except Exception:
            return (1, str(value))
    if isinstance(value, (datetime, date)):
        return (2, value.isoformat())
    return (3, str(value))


def _key_token(values: tuple[Any, ...]) -> tuple[Any, ...]:
    return tuple((1, None) if _is_null(value) else (0, value) for value in values)


def _column_map(frame: pd.DataFrame, requested: list[str], side: str) -> dict[str, Any]:
    available = {str(column).lower(): column for column in frame.columns}
    missing = [column for column in requested if column.lower() not in available]
    if missing:
        raise ValueError(f"{side} is missing manifest column {missing[0]!r}")
    return {column.lower(): available[column.lower()] for column in requested}


def _index_frame(
    frame: pd.DataFrame,
    keys: list[str],
    columns: list[str],
    names: dict[str, Any],
) -> tuple[
    dict[tuple[Any, ...], dict[str, Any]],
    Counter[tuple[Any, ...]],
    dict[tuple[Any, ...], tuple[Any, ...]],
]:
    requested = [*keys, *columns]
    actual_names = [names[column.lower()] for column in requested]
    index: dict[tuple[Any, ...], dict[str, Any]] = {}
    counts: Counter[tuple[Any, ...]] = Counter()
    raw_keys: dict[tuple[Any, ...], tuple[Any, ...]] = {}
    for values in frame[actual_names].itertuples(index=False, name=None):
        raw_key = tuple(_as_scalar(value) for value in values[: len(keys)])
        token = _key_token(raw_key)
        counts[token] += 1
        raw_keys.setdefault(token, raw_key)
        index.setdefault(
            token,
            {column.lower(): value for column, value in zip(requested, values, strict=True)},
        )
    return index, counts, raw_keys


def compare_frames(
    source: pd.DataFrame,
    target: pd.DataFrame,
    keys: list[str],
    columns: list[str],
) -> UnitResult:
    """Compare rows by keys, retaining the first manifest-ordered difference per key."""
    source_names = _column_map(source, [*keys, *columns], "SQL Server")
    target_names = _column_map(target, [*keys, *columns], "Snowflake")
    source_index, source_counts, source_keys = _index_frame(source, keys, columns, source_names)
    target_index, target_counts, target_keys = _index_frame(target, keys, columns, target_names)

    all_tokens = set(source_index) | set(target_index)
    differing: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    for token in all_tokens:
        raw_key = source_keys[token] if token in source_keys else target_keys[token]
        key_values = {name: _display(value) for name, value in zip(keys, raw_key, strict=True)}
        if source_counts[token] > 1 or target_counts[token] > 1:
            detail = {
                "key": key_values,
                "column": DUPLICATE_KEY,
                "sqlserver": f"{source_counts[token]} rows",
                "snowflake": f"{target_counts[token]} rows",
            }
            differing.append((raw_key, detail))
            continue
        if token not in target_index:
            differing.append(
                (
                    raw_key,
                    {
                        "key": key_values,
                        "column": MISSING_IN_SNOWFLAKE,
                        "sqlserver": "row present",
                        "snowflake": "row missing",
                    },
                )
            )
            continue
        if token not in source_index:
            differing.append(
                (
                    raw_key,
                    {
                        "key": key_values,
                        "column": MISSING_IN_SQLSERVER,
                        "sqlserver": "row missing",
                        "snowflake": "row present",
                    },
                )
            )
            continue
        for column in columns:
            source_value = source_index[token][column.lower()]
            target_value = target_index[token][column.lower()]
            if not _equal(source_value, target_value):
                differing.append(
                    (
                        raw_key,
                        {
                            "key": key_values,
                            "column": column,
                            "sqlserver": _display(source_value),
                            "snowflake": _display(target_value),
                        },
                    )
                )
                break

    differing.sort(key=lambda item: tuple(_sort_component(value) for value in item[0]))
    return UnitResult(
        status="DIVERGE" if differing else "PASS",
        source_rows=len(source),
        target_rows=len(target),
        differing_key_count=len(differing),
        differences=[detail for _, detail in differing[:10]],
    )
