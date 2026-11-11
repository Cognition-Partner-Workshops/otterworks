from copy import deepcopy
import json
from shutil import copyfile
import subprocess
import sys

import pytest

from warehouse.databricks_operate.drift import ROOT, SchemaDrift, read_rows, seed, validate


FIXTURE = ROOT / "landing/invoices.jsonl"
SCHEMA = json.loads((ROOT / "schema.json").read_text())
PRE_DRIFT_SCHEMA = {k: v for k, v in SCHEMA.items() if k != "tax_region"}
DRIFTED = ('{"invoice_id":7,"customer_id":10,"amount":"120.00","currency":"USD",'
           '"tax_region":"domestic"}\n')


def test_landing_change_fails_until_the_contract_and_loader_are_repaired(tmp_path):
    assert list(SCHEMA) == ["invoice_id", "customer_id", "amount", "currency", "tax_region"]
    landing = tmp_path / "invoices.jsonl"
    copyfile(FIXTURE, landing)
    rows = read_rows(landing)
    before = validate(rows, PRE_DRIFT_SCHEMA)
    with pytest.raises(SchemaDrift, match=r"missing=\['tax_region'\]"):
        validate(rows, SCHEMA)
    seed(landing)
    changed = read_rows(landing)
    with pytest.raises(SchemaDrift, match=r"added=\['tax_region'\]"):
        validate(changed, PRE_DRIFT_SCHEMA)
    # The repaired contract accepts the drift without hiding or dropping existing values.
    after = validate(changed, SCHEMA)
    assert before == after
    assert [{k: row[k] for k in PRE_DRIFT_SCHEMA} for row in changed] == rows
    assert [list(row) for row in changed] == [list(SCHEMA)] * len(changed)


def test_contract_accepts_drifted_record_shape(tmp_path):
    landing = tmp_path / "drifted.jsonl"
    landing.write_text(DRIFTED)
    result = subprocess.run([sys.executable, "-m", "warehouse.databricks_operate.drift",
                             "check", "--landing", str(landing)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"rows": 1, "invoice_ids": [7], "amount": "120.00"}
    row = read_rows(landing)[0]
    assert row["amount"] == "120.00" and row["tax_region"] == "domestic"
    event = subprocess.run([sys.executable, "-m", "warehouse.databricks_operate.drift",
                            "event", "--landing", str(landing)], capture_output=True, text=True)
    assert event.returncode != 0 and "healthy" in event.stderr


@pytest.mark.parametrize("region", ["null", "1", '["domestic"]'])
def test_tax_region_must_be_a_string(tmp_path, region):
    landing = tmp_path / "region.jsonl"
    landing.write_text(DRIFTED.replace('"domestic"', region))
    with pytest.raises(SchemaDrift, match="tax_region is not a string"):
        validate(read_rows(landing), SCHEMA)


def test_duplicate_and_cent_changes_fail(tmp_path):
    landing = tmp_path / "invoices.jsonl"
    copyfile(FIXTURE, landing)
    seed(landing)
    rows = read_rows(landing)
    schema = SCHEMA
    validate(rows, schema)
    with pytest.raises(SchemaDrift, match="duplicate"):
        validate(rows + rows[:1], schema)
    bad = deepcopy(rows)
    bad[0]["amount"] = "120.001"
    with pytest.raises(SchemaDrift, match="cent"):
        validate(bad, schema)


def test_seed_refuses_source_fixture():
    with pytest.raises(ValueError, match="outside"):
        seed(FIXTURE)


@pytest.mark.parametrize("record", ['{"amount":', 'null', '[]'])
def test_invalid_record_emits_alert(tmp_path, record):
    landing = tmp_path / "bad.jsonl"
    landing.write_text(record + "\n")
    result = subprocess.run([sys.executable, "-m", "warehouse.databricks_operate.drift",
                             "event", "--landing", str(landing)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    event = json.loads(result.stdout)
    assert event["status"] == "firing"
    assert event["alerts"][0]["labels"]["alertname"] == "LandingSchemaDrift"


def test_json_amount_keeps_sub_cent_precision(tmp_path):
    landing = tmp_path / "amount.jsonl"
    landing.write_text('{"invoice_id":1,"customer_id":10,"amount":120.000000000000001,'
                       '"currency":"USD","tax_region":"domestic"}\n')
    schema = SCHEMA
    with pytest.raises(SchemaDrift, match="cent"):
        validate(read_rows(landing), schema)


def test_repeated_json_fields_are_rejected_before_values_are_lost(tmp_path):
    landing = tmp_path / "duplicate.jsonl"
    landing.write_text('{"invoice_id":1,"customer_id":10,"amount":"120.00",'
                       '"currency":"USD","tax_region":"domestic","amount":"1.00"}\n')
    with pytest.raises(SchemaDrift, match="duplicate field: amount"):
        read_rows(landing)


def test_seed_preserves_numeric_amounts_and_rejects_repeat_seeding(tmp_path):
    landing = tmp_path / "numeric.jsonl"
    landing.write_text('{"invoice_id":1,"customer_id":10,"amount":120.00,"currency":"USD"}\n')
    before = read_rows(landing)
    seed(landing)
    after = read_rows(landing)
    validate(after, SCHEMA)
    assert [{k: v for k, v in row.items() if k != "tax_region"} for row in after] == before
    assert '"amount":120.00' in landing.read_text()
    with pytest.raises(ValueError, match="already seeded"):
        seed(landing)
