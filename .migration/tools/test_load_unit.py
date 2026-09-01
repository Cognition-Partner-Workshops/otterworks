"""Unit tests for the loader's safety rails.

Run with the migration venv: `/home/ubuntu/.mongo-venv/bin/python -m pytest .migration/tools`.
These cover the parts of the loader that decide whether a load is allowed to continue --
the guards, the anomaly accounting, and the validator it installs in place of an Oracle
trigger. Parity itself is not tested here; the recon harness owns that verdict.
"""
from __future__ import annotations

import decimal
import subprocess
import sys
import textwrap

import load_unit as lu
import pytest
import recon_report as rr
from bson.int64 import Int64


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
        scope = {k: v for k, v in flt.items() if k != "_id"}
        gone = [k for k, d in self.docs.items()
                if k not in keep and all(dotted(d, p) == v for p, v in scope.items())]
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


def dotted(doc, path):
    for part in path.split("."):
        doc = (doc or {}).get(part)
    return doc


class FakeCursor:
    """Serves rows per table; the loader's SELECTs are `SELECT cols FROM <table> [WHERE]`.

    A `COL = value` WHERE clause is honoured, so a scoped extract really does come back with
    only its own batch -- without that the batch-isolation tests would pass for the wrong
    reason.
    """

    def __init__(self, tables):
        self.tables = tables
        self.rows: list = []
        self.description: list = []

    def execute(self, sql):
        cols = sql.split("SELECT ", 1)[1].split(" FROM ")[0].replace('"', "").split(", ")
        table = sql.split(" FROM ")[1].split(" WHERE ")[0].strip()
        rows = self.tables[table]
        if " WHERE " in sql:
            predicate = sql.split(" WHERE ")[1]
            operator = ">=" if ">=" in predicate else "="
            column, value = (part.strip() for part in predicate.split(operator, 1))
            rows = [r for r in rows
                    if (str(r[column]) == value if operator == "="
                        else r[column] >= type(r[column])(value))]
        self.description = [(c,) for c in cols]
        self.rows = [tuple(r[c] for c in cols) for r in rows]

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


def test_the_two_digit_year_reads_as_oracle_reads_it():
    """`TO_DATE(str, 'DD-MON-YY')` takes the century from SYSDATE; the estate's far-future
    sentinel `31-DEC-99` is 2099, not 1999. A pivoting reading would move it a century."""
    assert lu.parse_dd_mon_yy("31-DEC-99").year == 2099
    assert lu.parse_dd_mon_yy("01-JAN-00").year == 2000


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

    # The row is repaired at source and the census refreshed, so the mapping now declares no
    # anomaly for it -- the load has to agree, and the old record has to go.
    tables["TENANTS"] = [{"ID": 1, "NAME": "acme", "SIGNUP": "03-FEB-24"}]
    spec = {**spec, "quarantine": {"collection": "tenants_quarantine", "expected": {}}}
    summary, _ = lu.load_collection(FakeCursor(tables), db, spec, {}, {}, dry_run=False)
    assert summary["pruned"] == 1
    assert list(db["tenants_quarantine"].docs) == ["other:1:X"]


# --------------------------------------------------------------- batch scoping
BATCH_SPEC = {
    "collection": "invoices", "root_table": "INVOICE_HEADER",
    "root_where": "BATCH_NO = ${batch_no}",
    "scope": {"source_column": "BATCH_NO", "target_field": "batch_no", "param": "batch_no"},
    "key": {"source": ["INVOICE_ID"], "target": "_id"},
    "fields": [{"source": "INVOICE_ID", "target": "_id", "bson_type": "long", "rules": []},
               {"source": "BATCH_NO", "target": "batch_no", "bson_type": "long",
                "rules": []},
               {"source": "REF", "target": "ref", "bson_type": "string", "rules": []}],
    "quarantine": {"collection": "invoices_quarantine", "expected": {}},
    "indexes": [],
}

HEADERS = [{"INVOICE_ID": 1, "BATCH_NO": 10, "REF": "a"},
           {"INVOICE_ID": 2, "BATCH_NO": 10, "REF": "b"},
           {"INVOICE_ID": 3, "BATCH_NO": 20, "REF": "c"}]


def load_batch(db, tables, batch, spec=BATCH_SPEC):
    return lu.load_collection(FakeCursor(tables), db, spec, {"batch_no": str(batch)}, {},
                              dry_run=False)[0]


def test_reloading_one_batch_leaves_the_other_batches_alone():
    """The extract is scoped to a batch, so everything outside it is not stale -- it is
    another batch's live data, which a rerun must not touch."""
    db = FakeMongo()
    tables = {"INVOICE_HEADER": HEADERS}
    load_batch(db, tables, 10)
    load_batch(db, tables, 20)
    assert set(db["invoices"].docs) == {1, 2, 3}

    assert load_batch(db, tables, 10)["pruned"] == 0
    assert set(db["invoices"].docs) == {1, 2, 3}
    assert load_batch(db, tables, 20)["pruned"] == 0
    assert set(db["invoices"].docs) == {1, 2, 3}


def test_a_scoped_rerun_still_prunes_its_own_deleted_rows():
    db = FakeMongo()
    tables = {"INVOICE_HEADER": HEADERS}
    load_batch(db, tables, 10)
    load_batch(db, tables, 20)

    tables["INVOICE_HEADER"] = [r for r in HEADERS if r["INVOICE_ID"] != 2]
    assert load_batch(db, tables, 10)["pruned"] == 1
    assert set(db["invoices"].docs) == {1, 3}


def test_quarantine_evidence_from_another_batch_survives_a_reload():
    spec = {**BATCH_SPEC,
            "derived_fields": [{"source": "SIGNED", "target": "signed_at",
                                "transform": "parse_dd_mon_yy", "on_error": "quarantine",
                                "quarantine_category": "unparseable_signed"}],
            "quarantine": {"collection": "invoices_quarantine",
                           "expected": {"unparseable_signed": 1}}}
    db = FakeMongo()
    tables = {"INVOICE_HEADER": [{"INVOICE_ID": 1, "BATCH_NO": 10, "REF": "a",
                                  "SIGNED": "  -   -  "},
                                 {"INVOICE_ID": 3, "BATCH_NO": 20, "REF": "c",
                                  "SIGNED": "  -   -  "}]}
    load_batch(db, tables, 10, spec)
    load_batch(db, tables, 20, spec)
    assert len(db["invoices_quarantine"].docs) == 2

    assert load_batch(db, tables, 10, spec)["pruned"] == 0
    assert len(db["invoices_quarantine"].docs) == 2, "a reload erased another batch's evidence"


def test_a_scoped_collection_must_declare_what_its_scope_is():
    """Without a declared scope the loader cannot tell another batch's documents from stale
    ones, so it stops instead of guessing."""
    spec = {k: v for k, v in BATCH_SPEC.items() if k != "scope"}
    with pytest.raises(SystemExit):
        load_batch(FakeMongo(), {"INVOICE_HEADER": HEADERS}, 10, spec)


def test_an_extract_that_leaves_the_declared_scope_is_rejected():
    """The scope filter is only safe if the extract really is confined to it. Here the
    predicate takes in later batches too, so the filter would delete the rows it just read
    -- the load stops instead."""
    spec = {**BATCH_SPEC, "root_where": "BATCH_NO >= ${batch_no}"}
    with pytest.raises(SystemExit):
        load_batch(FakeMongo(), {"INVOICE_HEADER": HEADERS}, 10, spec)


# ------------------------------------------------- scoped extracts and their children
EMBED_SPEC = {**BATCH_SPEC, "expected_documents": 3,
              "embeds": [{"array_path": "lines", "child_table": "INVOICE_LINE",
                          "parent_key": ["INVOICE_ID"],
                          "key": {"source": ["LINE_ID"], "target": "line_id"},
                          "fields": [{"source": "LINE_ID", "target": "line_id",
                                      "bson_type": "long", "rules": []}]}]}

LINES = [{"INVOICE_ID": 1, "LINE_ID": 11}, {"INVOICE_ID": 3, "LINE_ID": 33}]


def test_a_child_of_another_batch_is_not_an_orphan():
    """INVOICE_LINE rows hanging off batch 20 are not parentless just because batch 10 is
    the slice being loaded; treating them as orphans would quarantine another batch's live
    data (and here, with no orphan_category declared, would halt the load outright)."""
    db = FakeMongo()
    summary = load_batch(db, {"INVOICE_HEADER": HEADERS, "INVOICE_LINE": LINES}, 10,
                         EMBED_SPEC)
    assert summary["embedded"]["lines"] == 1
    assert [d["line_id"] for d in db["invoices"].docs[1]["lines"]] == [11]
    assert summary["quarantined"] == 0


def test_a_child_with_no_parent_anywhere_still_halts_when_the_anomaly_is_unnamed():
    """The out-of-scope exemption must not swallow the real anomaly: line 99 belongs to no
    invoice in any batch, and the mapping has not named that anomaly."""
    tables = {"INVOICE_HEADER": HEADERS,
              "INVOICE_LINE": LINES + [{"INVOICE_ID": 99, "LINE_ID": 991}]}
    with pytest.raises(SystemExit):
        load_batch(FakeMongo(), tables, 10, EMBED_SPEC)


def test_a_scoped_extract_is_counted_against_its_own_scope():
    """`expected_documents` is the census of the whole table. A batch load extracts one
    slice of it, so gating the slice on the estate-wide total would reject every valid
    partial batch."""
    db = FakeMongo()
    summary = load_batch(db, {"INVOICE_HEADER": HEADERS}, 10, {**BATCH_SPEC,
                                                               "expected_documents": 3})
    assert summary["documents"] == 2
    assert summary["expected_documents"] == 2
    assert summary["matches_census"] is True


def test_a_short_scoped_extract_is_still_rejected():
    """Scope-aware counting must not become no counting: the root key list is read back
    independently, so an extract that returns fewer rows than its own scope holds still
    stops before the write path."""
    class TruncatingCursor(FakeCursor):
        """Returns one row short on the scoped extract, and the whole table on the key read
        -- an extract that died part-way through its fetch."""

        def execute(self, sql):
            super().execute(sql)
            if " WHERE " in sql:
                self.rows = self.rows[:-1]

    db = FakeMongo()
    spec = {**BATCH_SPEC, "expected_documents": 3}
    with pytest.raises(SystemExit):
        lu.load_collection(TruncatingCursor({"INVOICE_HEADER": HEADERS}), db, spec,
                           {"batch_no": "10"}, {}, dry_run=False)
    assert db["invoices"].docs == {}


def test_a_stale_census_stops_a_scoped_load():
    """If the table no longer holds the number of rows the approved mapping was built from,
    the mapping is stale and the scope counts derived from it cannot be trusted either."""
    with pytest.raises(SystemExit):
        load_batch(FakeMongo(), {"INVOICE_HEADER": HEADERS}, 10,
                   {**BATCH_SPEC, "expected_documents": 4})


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
            "mapping_version": "m1", "target_db": "ow_tp_mongodb_orc1",
            "params": {"batch_no": "85559852"},
            "collections": [{"collection": "tenants", "documents": 69, "embedded": {},
                             "quarantined": 0, "anomalies": {}, "pruned": 0,
                             "digest": "cafe"}]}
    return {**base, **over}


def test_idempotency_is_derived_from_two_loads():
    first = load_report()
    rerun = load_report(completed_at="2026-09-01T05:00:00+00:00")
    verdict, evidence = rr.idempotency("reference", first, rerun)
    assert verdict == "pass"
    assert "tenants=69" in evidence


@pytest.mark.parametrize("difference", [{"documents": 70}, {"pruned": 2}])
def test_a_rerun_that_changed_the_target_fails_idempotency(difference):
    rerun = load_report(completed_at="2026-09-01T05:00:00+00:00",
                        collections=[{**load_report()["collections"][0], **difference}])
    verdict, evidence = rr.idempotency("reference", load_report(), rerun)
    assert verdict == "fail"
    assert "diverged" in evidence


def test_idempotency_needs_a_later_rerun_and_a_real_load():
    with pytest.raises(SystemExit):
        rr.idempotency("reference", load_report(), load_report())
    with pytest.raises(SystemExit):
        rr.idempotency("reference", load_report(dry_run=True), load_report())


# --------------------------------------------------------------- bson types
def test_a_long_field_is_encoded_as_a_bson_long():
    """tolerance v1 maps integer-safe NUMBER(p,0) to BSON long. A plain Python int is
    encoded as int32 when it is small, which is a different BSON type from the one the
    mapping declares and the one the target's validator requires."""
    assert isinstance(lu.to_bson(decimal.Decimal(420), "long"), Int64)
    assert lu.to_bson(decimal.Decimal(420), "long") == 420


def test_a_numeric_key_is_encoded_as_a_bson_long():
    assert isinstance(lu.key_to_bson(decimal.Decimal(7302), "CUSTOMER_MASTER.CUST_ID"),
                      Int64)
    assert lu.key_to_bson("a-uuid", "USAGE_EVENTS.EVENT_ID") == "a-uuid"


# --------------------------------------------------------------- gates before writes
def test_a_short_extract_is_rejected_before_anything_is_written():
    """The count and anomaly gates have to run before the target is touched: an extract that
    came back short would otherwise upsert what it has and then delete every valid document
    it did not see."""
    db = FakeMongo()
    tables = {"TENANTS": [{"ID": 1, "NAME": "acme"}, {"ID": 2, "NAME": "globex"}]}
    spec = {**TENANT_SPEC, "expected_documents": 2}
    lu.load_collection(FakeCursor(tables), db, spec, {}, {}, dry_run=False)

    tables["TENANTS"] = [{"ID": 1, "NAME": "acme"}]
    with pytest.raises(SystemExit):
        lu.load_collection(FakeCursor(tables), db, spec, {}, {}, dry_run=False)
    assert set(db["tenants"].docs) == {1, 2}, "a failed extract erased valid documents"


def test_an_anomaly_count_mismatch_is_rejected_before_anything_is_written():
    db = FakeMongo()
    spec = {**TENANT_SPEC, "expected_documents": 1,
            "derived_fields": [{"source": "SIGNUP", "target": "signup_at",
                                "transform": "parse_dd_mon_yy", "on_error": "quarantine",
                                "quarantine_category": "unparseable_signup"}],
            "quarantine": {"collection": "tenants_quarantine",
                           "expected": {"unparseable_signup": 1}}}
    tables = {"TENANTS": [{"ID": 1, "NAME": "acme", "SIGNUP": "03-FEB-24"}]}
    with pytest.raises(SystemExit):
        lu.load_collection(FakeCursor(tables), db, spec, {}, {}, dry_run=False)
    assert db["tenants"].docs == {}


# --------------------------------------------------------------- content evidence
def test_the_load_report_carries_a_content_digest():
    """Equal document counts do not prove equal documents, so the rerun comparison needs the
    content itself: same rows in, same digest out; a changed value changes it."""
    db = FakeMongo()
    spec = {**TENANT_SPEC, "expected_documents": 1}
    tables = {"TENANTS": [{"ID": 1, "NAME": "acme"}]}
    first, _ = lu.load_collection(FakeCursor(tables), db, spec, {}, {}, dry_run=False)
    same, _ = lu.load_collection(FakeCursor(tables), db, spec, {}, {}, dry_run=False)
    tables["TENANTS"] = [{"ID": 1, "NAME": "acme renamed"}]
    changed, _ = lu.load_collection(FakeCursor(tables), db, spec, {}, {}, dry_run=False)
    assert first["digest"] == same["digest"]
    assert changed["digest"] != first["digest"]


def test_a_rerun_with_changed_values_fails_idempotency():
    rerun = load_report(completed_at="2026-09-01T05:00:00+00:00",
                        collections=[{**load_report()["collections"][0], "digest": "beef"}])
    verdict, _ = rr.idempotency("reference", load_report(), rerun)
    assert verdict == "fail"


@pytest.mark.parametrize("differing", [{"mapping_version": "m2"},
                                       {"target_db": "somewhere_else"},
                                       {"params": {"batch_no": "1"}}])
def test_the_two_loads_must_describe_the_same_migration(differing):
    """Two loads of different mappings, databases, or scopes are not a load and its rerun,
    however well their counts agree."""
    with pytest.raises(SystemExit):
        rr.idempotency("reference", load_report(),
                       load_report(completed_at="2026-09-01T05:00:00+00:00", **differing))
