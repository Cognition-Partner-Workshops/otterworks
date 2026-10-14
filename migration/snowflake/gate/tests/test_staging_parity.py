from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
staging_parity = importlib.import_module("staging_parity")

SPEC = """package: pkg_demo
sqlserver_table: stg.stg_demo
snowflake_model: STAGING.STG_DEMO
keys: [id]
columns: [name]
rename: {id: demo_id}
"""


def write(tmp_path: Path, text: str) -> Path:
    (tmp_path / "pkg_demo.yaml").write_text(text, encoding="utf-8")
    return tmp_path


def test_load_spec_defaults_and_rename(tmp_path: Path) -> None:
    spec = staging_parity.load_spec("pkg_demo", write(tmp_path, SPEC))
    (destination,) = spec["destinations"]
    assert destination["unit"] == "ssis:pkg_demo"
    assert destination["excluded"] == {}
    assert staging_parity.target_name(destination, "id") == "demo_id"
    assert staging_parity.target_name(destination, "name") == "name"


def test_load_spec_multiple_destinations(tmp_path: Path) -> None:
    text = """package: pkg_demo
destinations:
  - {sqlserver_table: stg.stg_a, snowflake_model: STAGING.STG_A, keys: [id], columns: [x]}
  - {sqlserver_table: stg.stg_b, snowflake_model: STAGING.STG_B, keys: [id], columns: [y]}
"""
    spec = staging_parity.load_spec("pkg_demo", write(tmp_path, text))
    assert [d["unit"] for d in spec["destinations"]] == [
        "ssis:pkg_demo:stg_a",
        "ssis:pkg_demo:stg_b",
    ]


def test_load_spec_rejects_missing_keys(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="columns"):
        staging_parity.load_spec("pkg_demo", write(tmp_path, SPEC.replace("columns: [name]\n", "")))


def test_load_spec_rejects_key_listed_as_column(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="both keys and columns"):
        staging_parity.load_spec(
            "pkg_demo", write(tmp_path, SPEC.replace("columns: [name]", "columns: [id, name]"))
        )


@pytest.mark.parametrize("spec_path", sorted(staging_parity.SPEC_DIR.glob("*.yaml")))
def test_committed_specs_load(spec_path: Path) -> None:
    spec = staging_parity.load_spec(spec_path.stem)
    for destination in spec["destinations"]:
        assert destination["sqlserver_table"].startswith("stg.")
        assert destination["snowflake_model"].startswith("STAGING.")


def test_write_result_carries_explanation_forward(tmp_path: Path) -> None:
    spec = staging_parity.load_spec("pkg_demo", write(tmp_path, SPEC))
    unit = {
        "unit": "ssis:pkg_demo",
        "status": "DIVERGE",
        "source_rows": 1,
        "target_rows": 1,
        "differing_key_count": 1,
        "differences": [{"key": {"id": 1}, "column": "name", "sqlserver": "a", "snowflake": "b"}],
    }
    out = tmp_path / "out"
    staging_parity.write_result(out, "sfm-20261012-bd", "2026-09-30", spec, [dict(unit)])
    markdown = out / "pkg_demo.md"
    text = markdown.read_text().replace("Explanation: ", "Explanation: kept legacy")
    markdown.write_text(text + "\n### Business decisions\n\nExplanation: blank flag stays NULL\n")
    staging_parity.write_result(out, "sfm-20261012-bd", "2026-09-30", spec, [dict(unit)])
    assert "Explanation: kept legacy" in markdown.read_text()
    assert markdown.read_text().startswith("Staging parity pkg_demo DIVERGE 1 / 1")
    passed = {**unit, "status": "PASS", "differing_key_count": 0, "differences": []}
    staging_parity.write_result(out, "sfm-20261012-bd", "2026-09-30", spec, [passed])
    assert "Explanation: blank flag stays NULL" in markdown.read_text()
