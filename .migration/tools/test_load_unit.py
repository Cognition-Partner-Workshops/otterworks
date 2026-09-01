"""Unit tests for the loader's safety rails.

Run with the migration venv: `/home/ubuntu/.mongo-venv/bin/python -m pytest .migration/tools`.
These cover the parts of the loader that decide whether a load is allowed to continue --
the guards, the anomaly accounting, and the validator it installs in place of an Oracle
trigger. Parity itself is not tested here; the recon harness owns that verdict.
"""
from __future__ import annotations

import pytest

import load_unit as lu


class FakeDB:
    """Records the collMod the loader issues instead of talking to Atlas."""

    def __init__(self):
        self.commands = []

    def command(self, *args, **kwargs):
        self.commands.append((args, kwargs))


USAGE_VALIDATOR = {"$jsonSchema": {"bsonType": "object", "required": ["units", "kind_cd"],
                                   "properties": {"units": {"bsonType": "long", "minimum": 0,
                                                            "exclusiveMinimum": True},
                                                  "kind_cd": {"bsonType": "long"}}}}


def test_transforms_quarantine_rather_than_coerce():
    with pytest.raises(lu.TransformError):
        lu.parse_dd_mon_yy("  -   -  ")
    with pytest.raises(lu.TransformError):
        lu.csv_to_array("1001,,1003")
    assert lu.parse_dd_mon_yy("03-FEB-24").year == 2024
    assert lu.csv_to_array("1001, 1002") == ["1001", "1002"]


def test_anomaly_mismatch_flags_missing_excess_and_unexpected():
    spec = {"collection": "invoices",
            "quarantine": {"collection": "invoices_quarantine",
                           "expected": {"orphan_invoice_lines": 37}}}
    assert lu.anomaly_mismatches(spec, {"orphan_invoice_lines": 37}) == []
    assert lu.anomaly_mismatches(spec, {})[0].endswith("expected 37, got 0")
    assert lu.anomaly_mismatches(spec, {"orphan_invoice_lines": 38})[0].endswith(
        "expected 37, got 38")
    assert "declares no such anomaly" in lu.anomaly_mismatches(
        spec, {"orphan_invoice_lines": 37, "malformed_gl_acct_csv": 2})[0]


def test_scope_parameters_cannot_carry_sql():
    assert lu.PARAM_VALUE.match("85559852")
    assert not lu.PARAM_VALUE.match("1 OR 1=1")
    assert not lu.PARAM_VALUE.match("1) UNION SELECT * FROM CUSTOMER_MASTER --")


def test_designated_database_is_read_from_the_conventions_record():
    assert lu.designated_database() == "ow_tp_mongodb_orc1"


def test_validator_rejects_non_positive_units():
    """TRG_USAGE_EVENTS_CHECK raised ORA-20001 on units <= 0. The replacement is a
    $jsonSchema, so the same writes have to fail the schema."""
    jsonschema = pytest.importorskip("jsonschema")
    schema = {"type": "object", "required": ["units"],
              "properties": {"units": {"type": "integer", "exclusiveMinimum": 0}}}
    for units in (0, -1):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate({"units": units}, schema)
    jsonschema.validate({"units": 1}, schema)


def test_validator_enum_is_resolved_from_codes():
    db = FakeDB()
    spec = {"collection": "usage_events", "validator": USAGE_VALIDATOR,
            "validator_enum_from_codes": {"kind_cd": "USAGE_KIND"}}
    lu.install_validator(db, spec, {("USAGE_KIND", "1"): "API call",
                                    ("USAGE_KIND", "2"): "Storage",
                                    ("INV_STATUS", "9"): "Void"})
    (_, kwargs), = [(a, k) for a, k in db.commands]
    props = kwargs["validator"]["$jsonSchema"]["properties"]
    assert props["kind_cd"]["enum"] == [1, 2]
    assert props["units"]["exclusiveMinimum"] is True
    assert kwargs["validationAction"] == "error"
    # The spec the mapping generated is not mutated by having an enum resolved into it.
    assert "enum" not in USAGE_VALIDATOR["$jsonSchema"]["properties"]["kind_cd"]


def test_validator_refuses_to_widen_when_codes_are_missing():
    with pytest.raises(SystemExit):
        lu.install_validator(FakeDB(), {"collection": "usage_events",
                                        "validator": USAGE_VALIDATOR,
                                        "validator_enum_from_codes": {"kind_cd": "USAGE_KIND"}},
                             {("INV_STATUS", "9"): "Void"})
