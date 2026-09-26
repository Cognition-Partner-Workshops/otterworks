import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from bson.int64 import Int64

sys.path.insert(
    0,
    str(
        Path(__file__).resolve().parents[1]
        / "migration"
        / "mongo"
    ),
)

import load_usage_audit as loader

VALID_KINDS = {1, 2, 3}


def _row(**overrides):
    row = [
        "e-1",
        "tenant-1",
        datetime(2026, 2, 10, 10, 0, 0, 123456),
        Decimal("5"),
        Decimal("1"),
    ]
    keys = ["id", "tenant_id", "occurred_at", "units", "kind_cd"]
    for key, value in overrides.items():
        row[keys.index(key)] = value
    return tuple(row)


def test_canonicalize_happy_path():
    doc, reason = loader.canonicalize_usage_event(_row(), VALID_KINDS)
    assert reason is None
    assert doc["_id"] == "e-1"
    assert doc["tenantId"] == "tenant-1"
    assert doc["occurredAt"] == datetime(2026, 2, 10, 10, 0, 0, 123000)
    assert isinstance(doc["units"], Int64)
    assert int(doc["units"]) == 5
    assert isinstance(doc["kindCd"], Int64)


def test_null_key():
    doc, reason = loader.canonicalize_usage_event(_row(id=None), VALID_KINDS)
    assert doc is None and reason == "null_key:ID"


def test_empty_tenant():
    for value in (None, "", "   "):
        doc, reason = loader.canonicalize_usage_event(
            _row(tenant_id=value), VALID_KINDS
        )
        assert doc is None and reason == "empty_string_is_null:TENANT_ID"


def test_null_occurred_at():
    doc, reason = loader.canonicalize_usage_event(
        _row(occurred_at=None), VALID_KINDS
    )
    assert doc is None and reason == "null:OCCURRED_AT"


@pytest.mark.parametrize("units", [None, Decimal("0"), Decimal("-3")])
def test_units_not_positive(units):
    doc, reason = loader.canonicalize_usage_event(_row(units=units), VALID_KINDS)
    assert doc is None and reason == "units_not_positive"


@pytest.mark.parametrize("kind_cd", [None, Decimal("9")])
def test_unknown_usage_kind(kind_cd):
    doc, reason = loader.canonicalize_usage_event(
        _row(kind_cd=kind_cd), VALID_KINDS
    )
    assert doc is None and reason == "unknown_usage_kind"


def test_audit_row_happy_and_null_absent():
    doc, reason = loader.canonicalize_audit_row(
        (7, datetime(2026, 2, 1, 3, 30, 0, 999999), None, "purged")
    )
    assert reason is None
    assert doc["_id"] == 7
    assert doc["loggedAt"] == datetime(2026, 2, 1, 3, 30, 0, 999000)
    assert "module" not in doc
    assert doc["message"] == "purged"


def test_audit_row_quarantine():
    assert loader.canonicalize_audit_row(
        (None, datetime(2026, 1, 1), "m", "x")
    )[1] == "null_key:LOG_ID"
    assert loader.canonicalize_audit_row(
        (1, None, "m", "x")
    )[1] == "null:LOGGED_AT"
