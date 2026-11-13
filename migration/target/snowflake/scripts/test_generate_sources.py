import pytest

from generate_sources import generate


def test_sources():
    manifest = {"version": 1, "objects": [{"name": "LEDGER", "columns": [{"name": "AMOUNT", "type": "decimal128(14, 4)"}]}]}
    source = generate(manifest, "MIGRATION_RUN42_AFTER")["sources"][0]
    assert source["database"] == "MIGRATION_RUN42_AFTER"
    assert source["tables"][0]["identifier"] == "LEDGER"
    assert source["tables"][0]["columns"][0]["name"] == "AMOUNT"


def test_empty():
    assert generate({"version": 1, "objects": []})["sources"][0]["tables"] == []


def test_errors():
    with pytest.raises(ValueError):
        generate({"version": 2})
    with pytest.raises(ValueError):
        generate({"version": 1, "objects": [{"name": "x;drop"}]})
