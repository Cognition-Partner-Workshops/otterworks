"""Unit tests for the loader's safety rails.

Run with the migration venv: `/home/ubuntu/.mongo-venv/bin/python -m pytest .migration/tools`.
These cover the parts of the loader that decide whether a load is allowed to continue --
the guards, the anomaly accounting, and the validator it installs in place of an Oracle
trigger. Parity itself is not tested here; the recon harness owns that verdict.
"""
from __future__ import annotations

import subprocess
import sys
import textwrap

import load_unit as lu
import pytest
import recon_report as rr


class FakeDB:
    """Records the collMod the loader issues instead of talking to Atlas."""

    def __init__(self):
        self.commands = []

    def command(self, *args, **kwargs):
        self.commands.append((args, kwargs))


class FakeResult:
    def __init__(self, deleted_count):
        self.deleted_count = deleted_count


class FakeCollection:
    """Enough of a collection to observe what a load does to documents already there."""

    def __init__(self):
        self.docs = {}
        self.indexes = []

    def bulk_write(self, ops, ordered=True):
        for op in ops:
            self.docs[op._filter["_id"]] = op._doc

    def delete_many(self, flt):
        keep = set(flt["_id"]["$nin"])
        scope = flt.get("collection")
        gone = [k for k, d in self.docs.items()
                if k not in keep and (scope is None or d.get("collection") == scope)]
        for k in gone:
            del self.docs[k]
        return FakeResult(len(gone))

    def create_index(self, keys, **kwargs):
        self.indexes.append((keys, kwargs))


class FakeMongo(FakeDB):
    def __init__(self):
        super().__init__()
        self.colls: dict[str, FakeCollection] = {}

    def __getitem__(self, name):
        return self.colls.setdefault(name, FakeCollection())

    def list_collection_names(self):
        return list(self.colls)

    def create_collection(self, name):
        self.colls.setdefault(name, FakeCollection())


class FakeCursor:
    """Serves rows per table; the loader's SELECTs are `SELECT cols FROM <table> [WHERE]`."""

    def __init__(self, tables):
        self.tables = tables
        self.rows: list = []
        self.description: list = []

    def execute(self, sql):
        cols = sql.split("SELECT ", 1)[1].split(" FROM ")[0].replace('"', "").split(", ")
        table = sql.split(" FROM ")[1].split(" WHERE ")[0].strip()
        self.description = [(c,) for c in cols]
        self.rows = [tuple(r[c] for c in cols) for r in self.tables[table]]

    def __iter__(self):
        return iter(self.rows)


TENANT_SPEC = {
    "collection": "tenants", "root_table": "TENANTS",
    "key": {"source": ["ID"], "target": "_id"},
    "fields": [{"source": "ID", "target": "_id", "bson_type": "long", "rules": []},
               {"source": "NAME", "target": "name", "bson_type": "string", "rules": []}],
    "quarantine": {"collection": "tenants_quarantine", "expected": {}},
    "indexes": [],
}


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


# --------------------------------------------------------------- rerun convergence
def test_rerun_removes_documents_whose_source_row_is_gone():
    """Upsert alone converges on changes and additions. A deleted source row would survive
    as a target document the source no longer has, so the load prunes what it did not just
    extract."""
    db = FakeMongo()
    tables = {"TENANTS": [{"ID": 1, "NAME": "acme"}, {"ID": 2, "NAME": "globex"}]}
    lu.load_collection(FakeCursor(tables), db, TENANT_SPEC, {}, {}, dry_run=False)
    assert set(db["tenants"].docs) == {1, 2}

    tables["TENANTS"] = [{"ID": 1, "NAME": "acme"}]
    summary, _ = lu.load_collection(FakeCursor(tables), db, TENANT_SPEC, {}, {}, dry_run=False)
    assert set(db["tenants"].docs) == {1}
    assert summary["pruned"] == 1


def test_unchanged_rerun_prunes_nothing():
    db = FakeMongo()
    tables = {"TENANTS": [{"ID": 1, "NAME": "acme"}]}
    lu.load_collection(FakeCursor(tables), db, TENANT_SPEC, {}, {}, dry_run=False)
    summary, _ = lu.load_collection(FakeCursor(tables), db, TENANT_SPEC, {}, {}, dry_run=False)
    assert summary["pruned"] == 0
    assert set(db["tenants"].docs) == {1}


def test_rerun_removes_a_quarantine_record_for_a_repaired_row():
    """A row whose bad value has been fixed at source is no longer an anomaly; leaving its
    quarantine record behind would keep grading the unit against data that no longer exists.
    Quarantine records belonging to other collections are not in reach."""
    db = FakeMongo()
    spec = {**TENANT_SPEC,
            "derived_fields": [{"source": "SIGNUP", "target": "signup_at",
                                "transform": "parse_dd_mon_yy", "on_error": "quarantine",
                                "quarantine_category": "unparseable_signup"}],
            "quarantine": {"collection": "tenants_quarantine",
                           "expected": {"unparseable_signup": 1}}}
    db["tenants_quarantine"].docs["other:1:X"] = {"collection": "customers"}
    tables = {"TENANTS": [{"ID": 1, "NAME": "acme", "SIGNUP": "  -   -  "}]}
    lu.load_collection(FakeCursor(tables), db, spec, {}, {}, dry_run=False)
    assert [k for k, d in db["tenants_quarantine"].docs.items()
            if d.get("collection") == "tenants"]

    tables["TENANTS"] = [{"ID": 1, "NAME": "acme", "SIGNUP": "03-FEB-24"}]
    summary, _ = lu.load_collection(FakeCursor(tables), db, spec, {}, {}, dry_run=False)
    assert summary["pruned"] == 1
    assert list(db["tenants_quarantine"].docs) == ["other:1:X"]


# --------------------------------------------------------------- extract lease
def test_extract_lease_excludes_a_second_loader(tmp_path):
    """The source-load cap of 1 has to hold across processes: a wave runs three units wide."""
    lock = tmp_path / "extract.lock"
    prog = textwrap.dedent(f"""
        import sys
        sys.path.insert(0, {str(lu.__file__).rsplit("/", 1)[0]!r})
        import pathlib, load_unit
        with load_unit.extract_lease(pathlib.Path({str(lock)!r})):
            print("acquired")
    """)
    with lu.extract_lease(lock):
        second = subprocess.Popen([sys.executable, "-c", prog], stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True)
        with pytest.raises(subprocess.TimeoutExpired):
            second.communicate(timeout=3)  # it waits rather than reading the source
        assert second.poll() is None
    out, _ = second.communicate(timeout=10)
    assert "acquired" in out  # and it proceeds the moment the lease is released


def test_extract_lease_is_released_when_the_load_raises(tmp_path):
    lock = tmp_path / "extract.lock"
    with pytest.raises(RuntimeError), lu.extract_lease(lock):
        raise RuntimeError("load failed mid-extract")
    with lu.extract_lease(lock):
        pass


# --------------------------------------------------------------- idempotency evidence
def load_report(**over):
    base = {"unit": "reference", "dry_run": False, "completed_at": "2026-09-01T04:00:00+00:00",
            "collections": [{"collection": "tenants", "documents": 69, "embedded": {},
                             "quarantined": 0, "anomalies": {}, "pruned": 0}]}
    return {**base, **over}


def test_idempotency_is_derived_from_two_loads():
    first = load_report()
    rerun = load_report(completed_at="2026-09-01T05:00:00+00:00")
    verdict, evidence = rr.idempotency("reference", first, rerun)
    assert verdict == "pass"
    assert "tenants=69" in evidence


@pytest.mark.parametrize("bad_collection", [
    {"collection": "tenants", "documents": 70, "embedded": {}, "quarantined": 0,
     "anomalies": {}, "pruned": 0},
    {"collection": "tenants", "documents": 69, "embedded": {}, "quarantined": 0,
     "anomalies": {}, "pruned": 2},
])
def test_a_rerun_that_changed_the_target_fails_idempotency(bad_collection):
    rerun = load_report(completed_at="2026-09-01T05:00:00+00:00",
                        collections=[bad_collection])
    verdict, evidence = rr.idempotency("reference", load_report(), rerun)
    assert verdict == "fail"
    assert "diverged" in evidence


def test_idempotency_needs_a_later_rerun_and_a_real_load():
    with pytest.raises(SystemExit):
        rr.idempotency("reference", load_report(), load_report())
    with pytest.raises(SystemExit):
        rr.idempotency("reference", load_report(dry_run=True), load_report())
