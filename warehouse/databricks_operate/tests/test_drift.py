from copy import deepcopy
import json
import subprocess
import sys

import pytest

from warehouse.databricks_operate.drift import ROOT, SchemaDrift, read_rows, seed, validate


def test_landing_change_fails_until_the_contract_and_loader_are_repaired(tmp_path):
    rows = read_rows(ROOT / "landing/invoices.jsonl")
    schema = json.loads((ROOT / "schema.json").read_text())
    before = validate(rows, schema)
    landing = tmp_path / "invoices.jsonl"
    landing.write_text((ROOT / "landing/invoices.jsonl").read_text())
    seed(landing)
    changed = read_rows(landing)
    with pytest.raises(SchemaDrift, match="tax_region"):
        validate(changed, schema)
    # Proves the fixture can be repaired without hiding or dropping existing values.
    fixed_schema = dict(schema, tax_region="string")
    after = validate(changed, fixed_schema)
    assert before == after
    assert [{k: row[k] for k in schema} for row in changed] == rows


def test_duplicate_and_cent_changes_fail():
    rows = read_rows(ROOT / "landing/invoices.jsonl")
    schema = json.loads((ROOT / "schema.json").read_text())
    with pytest.raises(SchemaDrift, match="duplicate"):
        validate(rows + rows[:1], schema)
    bad = deepcopy(rows)
    bad[0]["amount"] = "120.001"
    with pytest.raises(SchemaDrift, match="cent"):
        validate(bad, schema)


def test_seed_refuses_source_fixture():
    with pytest.raises(ValueError, match="outside"):
        seed(ROOT / "landing/invoices.jsonl")


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
                       '"currency":"USD"}\n')
    schema = json.loads((ROOT / "schema.json").read_text())
    with pytest.raises(SchemaDrift, match="cent"):
        validate(read_rows(landing), schema)


def test_repeated_json_fields_are_rejected_before_values_are_lost(tmp_path):
    landing = tmp_path / "duplicate.jsonl"
    landing.write_text('{"invoice_id":1,"customer_id":10,"amount":"120.00",'
                       '"currency":"USD","amount":"1.00"}\n')
    with pytest.raises(SchemaDrift, match="duplicate field: amount"):
        read_rows(landing)


def test_seed_preserves_numeric_amounts_and_rejects_repeat_seeding(tmp_path):
    landing = tmp_path / "numeric.jsonl"
    landing.write_text('{"invoice_id":1,"customer_id":10,"amount":120.00,"currency":"USD"}\n')
    before = read_rows(landing)
    seed(landing)
    after = read_rows(landing)
    assert [{k: v for k, v in row.items() if k != "tax_region"} for row in after] == before
    assert '"amount":120.00' in landing.read_text()
    with pytest.raises(ValueError, match="already seeded"):
        seed(landing)


def test_total_of_valid_cent_amounts_is_exact():
    schema = json.loads((ROOT / "schema.json").read_text())
    rows = [{"invoice_id": i, "customer_id": 10, "amount": "99999999999999999999999999.99",
             "currency": "USD"} for i in (1, 2)]
    assert validate(rows, schema)["amount"] == "199999999999999999999999999.98"


def test_compact_zero_exponent_does_not_widen_the_total():
    schema = json.loads((ROOT / "schema.json").read_text())
    rows = [{"invoice_id": 1, "customer_id": 10, "amount": "1.00", "currency": "USD"},
            {"invoice_id": 2, "customer_id": 10, "amount": "0E-1000000000", "currency": "USD"}]
    assert validate(rows, schema)["amount"] == "1.00"
