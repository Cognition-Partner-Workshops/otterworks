from __future__ import annotations

from pathlib import Path

from migration.snowflake.gate.parity import load_manifest


def test_manifest_has_25_unique_units_with_keys_and_columns() -> None:
    manifest = load_manifest(Path(__file__).parents[1] / "manifest.yaml")
    assert len(manifest) == 25
    assert len({unit["unit"] for unit in manifest}) == 25
    assert all(unit["keys"] and unit["columns"] for unit in manifest)
