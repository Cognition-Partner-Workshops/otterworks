"""Unit tests for migration/billing/recon/recon.py (run: pytest migration/billing/recon/tests -q)."""
from __future__ import annotations

import datetime as dt
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from bson import Decimal128, Int64

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import recon  # noqa: E402

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 10, 2, 0, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def inputs() -> recon.Inputs:
    return recon.build_inputs(fixture_path=None)


@pytest.fixture(scope="module")
def inputs_with_fixture() -> recon.Inputs:
    return recon.build_inputs()


def money(fm_money=True) -> recon.FieldMap:
    return recon.FieldMap("amount", "T", "AMOUNT", "decimal", False, False, fm_money)


def tol() -> recon.Tolerance:
    return recon.Tolerance(Decimal("0"), Decimal("0"), 0, False, False)


# ---- mapping spec is parsed structurally, not hard-coded -------------------------------------

def test_spec_parses_every_collection(inputs):
    names = {c.name for c in inputs.collections}
    assert len(inputs.collections) == 16
    codes = next(c for c in inputs.collections if c.name == "codes")
    assert codes.id_fields == ["codeType", "codeVal"] and codes.id_columns == ["CODE_TYPE", "CODE_VAL"]
    feed = next(c for c in inputs.collections if c.name == "invoice_feed")
    (lines,) = feed.embedded
    assert (lines.table, lines.parent_fk, lines.identity_field, lines.identity_column) == ("INVOICE_LINE", "INVOICE_ID", "lineId", "LINE_ID")
    assert lines.order_fields == ["lineNo", "lineId"]
    assert lines.quarantine_collection == "invoice_feed_quarantine"
    q = next(c for c in inputs.collections if c.name == "invoice_feed_quarantine")
    assert q.quarantine_of is lines and q.id_columns == ["LINE_ID"]
    cust = next(c for c in inputs.collections if c.name == "customers")
    (attrs,) = cust.embedded
    assert attrs.parent_fk == "ENTITY_ID" and attrs.fixed_filter == {"ENTITY_TYPE": "CUSTOMER"}
    rp = next(c for c in inputs.collections if c.name == "rating_periods")
    assert rp.embedded[0].shape == "subdoc" and rp.embedded[0].parent_fk == "PERIOD_ID"
    assert "invoices" in names and "billing_audit_log" in names


def test_money_columns_come_from_tolerances_only(inputs):
    cust = next(c for c in inputs.collections if c.name == "customers")
    fm = next(f for f in cust.fields if f.field == "curBalAmt")
    assert fm.money and fm.bson == "decimal"
    assert tol().money_abs == 0 and recon.Tolerance.from_tolerances(inputs.tolerances).money_abs == 0


# ---- value comparison --------------------------------------------------------------------------

def test_decimal_vs_decimal128_exact():
    fm = money()
    exp = recon.canon_source(Decimal("1234.50"), "decimal")
    act = recon.canon_target({"amount": Decimal128("1234.50")}, "amount", "decimal")
    assert recon.values_equal(exp, act, fm, tol())
    act2 = recon.canon_target({"amount": Decimal128("1234.51")}, "amount", "decimal")
    assert not recon.values_equal(exp, act2, fm, tol())


def test_binary_float_is_a_type_violation_not_a_rounding_question():
    with pytest.raises(recon.TypeViolation):
        recon.canon_target({"amount": 1234.5}, "amount", "decimal")
    with pytest.raises(recon.TypeViolation):
        recon.canon_source(1234.5, "decimal")
    with pytest.raises(recon.TypeViolation):
        recon.canon_target({"amount": 1234}, "amount", "decimal")  # int32 where Decimal128 is required


def test_float_rounded_decimal128_is_caught_by_value():
    exp = recon.canon_source(Decimal("0.10") + Decimal("0.20"), "decimal")
    act = recon.canon_target({"amount": Decimal128(Decimal(repr(0.1 + 0.2)))}, "amount", "decimal")
    assert not recon.values_equal(exp, act, money(), tol())


def test_null_maps_to_absent_and_explicit_null_is_a_violation():
    assert recon.canon_source(None, "string") is recon.MISSING
    assert recon.canon_target({}, "x", "string") is recon.MISSING
    with pytest.raises(recon.TypeViolation):
        recon.canon_target({"x": None}, "x", "string")


def test_dates_compare_in_utc_with_zero_tolerance():
    fm = recon.FieldMap("d", "T", "D", "date", False, False)
    exp = recon.canon_source(dt.datetime(2026, 1, 1, 12, 0), "date")  # naive Oracle value == UTC
    act = recon.canon_target({"d": dt.datetime(2026, 1, 1, 12, 0, tzinfo=UTC)}, "d", "date")
    assert recon.values_equal(exp, act, fm, tol())
    act2 = recon.canon_target({"d": dt.datetime(2026, 1, 1, 12, 0, 1, tzinfo=UTC)}, "d", "date")
    assert not recon.values_equal(exp, act2, fm, tol())


def test_ints_and_longs():
    assert recon.canon_source(Decimal("20"), "int") == 20
    assert recon.canon_target({"n": Int64(7)}, "n", "long") == 7
    with pytest.raises(recon.TypeViolation):
        recon.canon_target({"n": True}, "n", "int")
    with pytest.raises(recon.TypeViolation):
        recon.canon_source(Decimal("20.5"), "int")


# ---- derived rules -------------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("01-JAN-24", dt.date(2024, 1, 1)), ("31-DEC-99", dt.date(1999, 12, 31)), ("15-JUN-49", dt.date(2049, 6, 15)),
    ("31-FEB-24", None), ("29-FEB-23", None), ("N/A", None), ("1/1/1900", None), ("00-XXX-00", None), ("  -   -  ", None),
    ("99-999-99", None), ("12-13-201", None), (None, None),
])
def test_parse_ddmonyy_rr_rule(text, expected):
    assert recon.parse_ddmonyy(text) == expected


@pytest.mark.parametrize("text,clean", [("12345,67890", True), ("12345", True), (" , 99 ,", False), (",,", False),
                                        ("A;B;C", False), ("NULL,NONE,", False), ("12345,,67890,", False), (None, False)])
def test_csv_clean_form(text, clean):
    assert recon.csv_is_clean(text) is clean


# ---- end-to-end on a small synthetic estate ---------------------------------------------------------

SUBSET = ["codes", "customers", "invoice_feed", "invoice_feed_quarantine", "rating_periods", "plans"]


def small_estate(inputs: recon.Inputs) -> tuple[dict, dict]:
    tables = recon.build_faithful_copy(_shrink(inputs), seed=7)
    docs = recon.load_documents(inputs, tables, NOW)
    return tables, docs


def _shrink(inputs: recon.Inputs) -> recon.Inputs:
    """A copy of the real inputs with a tiny fixture manifest: 40 customers, 12 headers, 60 lines, 3 orphans."""
    fx = {
        "namespace": "unit", "tables": {t: {"fixture_rows": n, "census_rows": n, "delta": 0} for t, n in {
            "CODES": 8, "TENANTS": 3, "PLANS": 2, "SUBSCRIPTIONS": 3, "SUBSCRIPTIONS_HIST": 0, "USAGE_EVENTS": 5,
            "RATING_PERIODS": 2, "RATING_RESULTS": 2, "INVOICES": 2, "INVOICE_LINES": 4, "CREDIT_NOTES": 1,
            "DUNNING_ATTEMPTS": 1, "NOTIFICATIONS": 1, "BILLING_AUDIT_LOG": 0, "CUSTOMER_MASTER": 40,
            "CUSTOMER_MASTER_HIST": 0, "ENTITY_ATTR_VALUE": 6, "INVOICE_HEADER": 12, "INVOICE_LINE": 60}.items()},
        "census_delta": {"static_upgrade_rows": {"CUSTOMER_MASTER": ["40000000-0000-0000-0000-00000000a001"]}},
        "anomalies": [
            {"kind": "orphaned_rows", "line_ids": ["o-1", "o-2", "o-3"], "target": "oracle.OW_BILLING.INVOICE_LINE"},
            {"kind": "dirty_dates", "cust_ids": ["c-dirty-1", "c-dirty-2"], "target": "oracle.OW_BILLING.CUSTOMER_MASTER.SIGNUP_DT",
             "values": {"31-FEB-24": {"count": 1}, "N/A": {"count": 1}}},
            {"kind": "malformed_csv_lists", "cust_ids": ["c-csv-1"], "target": "oracle.OW_BILLING.CUSTOMER_MASTER.RELATED_ACCT_IDS",
             "definition": r"RELATED_ACCT_IDS not matching ^\d{5}(,\d{5}){0,3}$ (NULL/empty is clean)", "values": {"A;B;C": 1}},
            {"kind": "eav_boolean_spellings", "target": "oracle.OW_BILLING.ENTITY_ATTR_VALUE",
             "attr_value_matrix": {"FAX_OPTOUT": {"Y": 2, "TRUE": 1, "blue": 1}}, "static_baseline_rows": [
                 {"eav_id": "99000000000001", "attr_name": "TAX_REGION_OVERRIDE", "attr_value": "US-IL"},
                 {"eav_id": "99000000000002", "attr_name": "tax_region_override", "attr_value": "us-il"}]},
        ],
    }
    fx["tables"]["CUSTOMER_MASTER"]["census_rows"] = 39
    fx["tables"]["CUSTOMER_MASTER"]["delta"] = 1
    return recon.Inputs(inputs.spec, inputs.tolerances, fx, inputs.spec_sha, inputs.tolerances_sha, "unit",
                        inputs.collections, inputs.money_columns)


def run_small(inputs, tables, docs, mutate=None, collections=None):
    if mutate:
        mutate(docs)
    run = recon.ReconRun(_shrink(inputs), recon.DictSource(tables), recon.DictTarget(docs), "fixture", now=NOW,
                         collections=collections)
    idem = recon.execute(run)
    report = recon.build_report(run, "unit", idem)
    assert recon.validate_report(report) == [], recon.validate_report(report)
    return run, report


def failed(run) -> set[str]:
    return {c.id for c in run.checks if c.result == "fail"}


def test_faithful_copy_passes_and_report_validates(inputs):
    tables, docs = small_estate(inputs)
    run, report = run_small(inputs, tables, docs)
    assert failed(run) == set(), failed(run)
    assert report["run_mode"] == "fixture" and report["merge_evidence"] is False
    assert report["idempotency_rerun"]["result"] == "pass"
    assert report["planted_anomaly_detections"]["missing"] == [] and report["planted_anomaly_detections"]["unexpected"] == []
    assert any(x.startswith("orphaned_rows:o-1") for x in report["planted_anomaly_detections"]["expected_set"])
    assert {c["id"] for c in report["checks"]} >= {"census_delta.CUSTOMER_MASTER", "anomalies.eav_boolean_spellings.target",
                                                   "invoice_feed_quarantine.row_count", "codes.keyed_values"}


def test_census_delta_row_is_not_a_defect(inputs):
    tables, docs = small_estate(inputs)
    assert any(r["CUST_ID"] == "40000000-0000-0000-0000-00000000a001" for r in tables["CUSTOMER_MASTER"])
    run, _ = run_small(inputs, tables, docs)
    delta = next(c for c in run.checks if c.id == "census_delta.CUSTOMER_MASTER")
    assert delta.result == "pass" and delta.actual["fixture_only_in_target"] == ["40000000-0000-0000-0000-00000000a001"]
    # drop the fixture-only row from the target -> accounted-for check fails, and so does keyed presence
    def drop(d):
        d["customers"] = [x for x in d["customers"] if x["_id"] != "40000000-0000-0000-0000-00000000a001"]
    run2, _ = run_small(inputs, tables, docs, drop)
    assert {"census_delta.CUSTOMER_MASTER", "customers.keyed_presence", "customers.row_count"} <= failed(run2)


def test_dropped_row_is_caught(inputs):
    tables, docs = small_estate(inputs)
    run, _ = run_small(inputs, tables, docs, lambda d: d["invoice_feed"].pop(3))
    assert {"invoice_feed.row_count", "invoice_feed.keyed_presence"} <= failed(run)


def test_changed_amount_is_caught(inputs):
    tables, docs = small_estate(inputs)
    def bump(d):
        doc = next(x for x in d["customers"] if "curBalAmt" in x)
        doc["curBalAmt"] = Decimal128(doc["curBalAmt"].to_decimal() + Decimal("0.01"))
    run, report = run_small(inputs, tables, docs, bump)
    assert failed(run) == {"customers.keyed_values"}
    check = next(c for c in report["checks"] if c["id"] == "customers.keyed_values")
    assert check["samples"][0]["field"] == "curBalAmt" and check["samples"][0]["reason"] == "value differs"


def test_float_rounded_amount_is_caught(inputs):
    tables, docs = small_estate(inputs)
    def to_float(d):
        line = next(ln for x in d["invoice_feed"] for ln in x.get("lines", []) if "amount" in ln)
        line["amount"] = round(float(line["amount"].to_decimal()), 2)
    run, _ = run_small(inputs, tables, docs, to_float)
    assert {"invoice_feed.lines.money_decimal128", "invoice_feed.lines.keyed_values"} == failed(run)


def test_quarantine_must_match_exactly(inputs):
    tables, docs = small_estate(inputs)
    assert len(docs["invoice_feed_quarantine"]) == 3
    run, _ = run_small(inputs, tables, docs, lambda d: d["invoice_feed_quarantine"].pop())
    assert {"invoice_feed_quarantine.row_count", "invoice_feed_quarantine.keyed_presence", "invoice_feed.lines.row_count",
            "anomalies.orphaned_rows.target"} <= failed(run)


def test_dirty_date_must_stay_verbatim_without_derived_date(inputs):
    tables, docs = small_estate(inputs)
    def heal(d):
        doc = next(x for x in d["customers"] if x["_id"] == "c-dirty-1")
        doc["signupDate"] = dt.datetime(2024, 2, 29, tzinfo=UTC)   # loader "fixed" 31-FEB-24
    run, _ = run_small(inputs, tables, docs, heal)
    assert {"derived_fields.rules", "anomalies.dirty_dates.target"} == failed(run)


def test_eav_spelling_matrix_is_compared_cell_by_cell(inputs):
    tables, docs = small_estate(inputs)
    def normalise(d):
        for doc in d["customers"]:
            for a in doc.get("attributes", []):
                if a["value"] == "TRUE":
                    a["value"] = "Y"
    run, _ = run_small(inputs, tables, docs, normalise)
    assert {"anomalies.eav_boolean_spellings.target", "customers.attributes.keyed_values"} == failed(run)


ANOMALY_CHECKS = {f"anomalies.{kind}.{side}" for kind in ("orphaned_rows", "dirty_dates", "malformed_csv_lists", "eav_boolean_spellings")
                  for side in ("source", "target")}


def anomaly_checks(run) -> set[str]:
    return {c.id for c in run.checks if c.id.startswith("anomalies.")}


def test_subset_run_skips_out_of_scope_anomaly_kinds_as_unverified(inputs):
    tables, docs = small_estate(inputs)
    u1 = ["codes", "tenants", "plans", "subscriptions", "subscriptions_hist"]
    run, report = run_small(inputs, tables, docs, collections=u1)
    assert anomaly_checks(run) == set()
    assert {x for x in run.unverified if x.startswith("anomalies.")} == {
        "anomalies.orphaned_rows: INVOICE_LINE outside this run's collections; not evaluated",
        "anomalies.dirty_dates: CUSTOMER_MASTER outside this run's collections; not evaluated",
        "anomalies.malformed_csv_lists: CUSTOMER_MASTER outside this run's collections; not evaluated",
        "anomalies.eav_boolean_spellings: ENTITY_ATTR_VALUE outside this run's collections; not evaluated",
    }
    assert set(report["unverified_paths"]) >= {x for x in run.unverified if x.startswith("anomalies.")}
    assert run.verdict() == "pass" and failed(run) == set()
    assert report["planted_anomaly_detections"] == {"expected_set": [], "actual_set": [], "missing": [], "unexpected": []}
    assert {c["id"] for c in report["checks"]} >= {f"{c}.keyed_values" for c in u1}


def test_subset_run_including_the_anomaly_table_still_evaluates_it(inputs):
    tables, docs = small_estate(inputs)
    run, _ = run_small(inputs, tables, docs, collections=["customers"])
    assert anomaly_checks(run) == {"anomalies.dirty_dates.source", "anomalies.dirty_dates.target",
                                   "anomalies.malformed_csv_lists.source", "anomalies.malformed_csv_lists.target",
                                   "anomalies.eav_boolean_spellings.source", "anomalies.eav_boolean_spellings.target"}
    assert [x for x in run.unverified if x.startswith("anomalies.")] == [
        "anomalies.orphaned_rows: INVOICE_LINE outside this run's collections; not evaluated"]
    assert failed(run) == set()

    tables, docs = small_estate(inputs)
    def heal(d):
        doc = next(x for x in d["customers"] if x["_id"] == "c-dirty-1")
        doc["signupDate"] = dt.datetime(2024, 2, 29, tzinfo=UTC)
    run, _ = run_small(inputs, tables, docs, heal, collections=["customers"])
    assert {"derived_fields.rules", "anomalies.dirty_dates.target"} == failed(run)


def test_full_run_evaluates_every_anomaly_kind(inputs):
    tables, docs = small_estate(inputs)
    run, report = run_small(inputs, tables, docs)
    assert anomaly_checks(run) == ANOMALY_CHECKS
    assert not any("outside this run's collections" in x for x in report["unverified_paths"])
    assert len(report["planted_anomaly_detections"]["expected_set"]) > 0


def test_compound_id_key_order_and_embedded_order(inputs):
    tables, docs = small_estate(inputs)
    def swap(d):
        doc = d["codes"][0]
        doc["_id"] = {"codeVal": doc["_id"]["codeVal"], "codeType": doc["_id"]["codeType"]}
        feed = next(x for x in d["invoice_feed"] if len(x.get("lines", [])) > 1)
        feed["lines"].reverse()
    run, _ = run_small(inputs, tables, docs, swap)
    assert {"codes.key_shape", "codes.keyed_presence", "invoice_feed.lines.shape_and_order"} <= failed(run)


def test_map_source_row_applies_mapping(inputs):
    cust = next(c for c in inputs.collections if c.name == "customers")
    row = {"CUST_ID": "c1", "CUR_BAL_AMT": Decimal("10.50"), "SIGNUP_DT": "01-JAN-24", "RELATED_ACCT_IDS": "12345,67890",
           "STATUS_CD": Decimal("10"), "CUST_NAME": None}
    doc = recon.map_source_row(cust, row, NOW)
    assert doc["_id"] == "c1" and doc["curBalAmt"] == Decimal128("10.50") and doc["statusCd"] == 10
    assert doc["signupDate"] == dt.datetime(2024, 1, 1, tzinfo=UTC) and doc["relatedAcctIdsList"] == ["12345", "67890"]
    assert "custName" not in doc
    dirty = recon.map_source_row(cust, {"CUST_ID": "c2", "SIGNUP_DT": "31-FEB-24", "RELATED_ACCT_IDS": "A;B;C"}, NOW)
    assert dirty["signupDt"] == "31-FEB-24" and "signupDate" not in dirty and "relatedAcctIdsList" not in dirty


def test_live_mode_requires_named_secrets(monkeypatch, tmp_path):
    monkeypatch.delenv("OW_TP_ORACLE_RO_DSN", raising=False)
    with pytest.raises(SystemExit, match="OW_TP_ORACLE_RO_DSN is not set"):
        recon.main(["run", "--mode", "live", "--out", str(tmp_path / "r.json")])
    with pytest.raises(SystemExit, match="requires the configured secrets"):
        recon.main(["run", "--mode", "live", "--out", str(tmp_path / "r.json"), "--oracle-dsn-env", "SOMETHING_ELSE"])


def test_oracle_dsn_forms():
    assert recon._oracle_kwargs('{"user":"u","password":"p","dsn":"h:1521/svc"}') == {"user": "u", "password": "p", "dsn": "h:1521/svc"}
    assert recon._oracle_kwargs("u/p@h:1521/svc")["dsn"] == "h:1521/svc"
    assert recon._dsn_host("h:1521/svc") == "h" and recon._dsn_host("(DESCRIPTION=(ADDRESS=(HOST=db.example)(PORT=1)))") == "db.example"
