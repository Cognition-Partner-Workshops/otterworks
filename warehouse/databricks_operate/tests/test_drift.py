from copy import deepcopy
import json

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
