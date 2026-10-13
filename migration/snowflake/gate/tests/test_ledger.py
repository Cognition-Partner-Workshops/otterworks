from __future__ import annotations

import json
from pathlib import Path

from migration.snowflake.gate.parity import exit_code, read_explanations, write_ledger


def test_explanation_round_trip_carries_forward(tmp_path: Path) -> None:
    units = [
        {
            "unit": "example",
            "status": "DIVERGE",
            "source_rows": 1,
            "target_rows": 1,
            "differing_key_count": 1,
            "differences": [
                {
                    "key": {"id": "1"},
                    "column": "value",
                    "sqlserver": "source",
                    "snowflake": "target",
                }
            ],
            "explanation": "",
        }
    ]
    write_ledger(tmp_path, "sfm-20261012-bd", "2026-09-15", units)
    markdown = tmp_path / "ledger.md"
    markdown.write_text(
        markdown.read_text().replace("Explanation: ", "Explanation: expected rounding"),
        encoding="utf-8",
    )
    write_ledger(tmp_path, "sfm-20261012-bd", "2026-09-15", units)
    assert read_explanations(markdown) == {"example": "expected rounding"}
    payload = json.loads((tmp_path / "ledger.json").read_text())
    assert payload["units"][0]["explanation"] == "expected rounding"


def test_exit_code_rules() -> None:
    assert exit_code([{"status": "PENDING", "explanation": ""}]) == 1
    assert exit_code([{"status": "DIVERGE", "explanation": ""}]) == 1
    assert (
        exit_code(
            [
                {"status": "DIVERGE", "explanation": "accepted"},
                {"status": "PASS", "explanation": ""},
            ]
        )
        == 0
    )
