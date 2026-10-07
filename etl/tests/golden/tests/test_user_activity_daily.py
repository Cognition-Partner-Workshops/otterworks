"""user_activity_daily only reads Postgres: every golden keeps the seeded rows."""

import json

import pytest

from harness import scenario
from harness.normalize import VOLATILE_PG_COLUMNS, placeholder

TABLE = "analytics_daily_summary"
SCENARIOS = scenario.discover("user_activity_daily")
VOLATILE = {column for table, column in VOLATILE_PG_COLUMNS if table == TABLE}


@pytest.mark.parametrize("scn", SCENARIOS, ids=lambda s: s.label)
def test_postgres_golden_equals_seed(scn):
    golden = json.loads((scn.golden_dir / "postgres.json").read_text())
    assert set(golden) == {TABLE}
    rows = golden[TABLE]["rows"]
    seeded = sorted(
        scn.seed.get("postgres", {}).get(TABLE, []), key=lambda r: r["report_date"]
    )
    assert len(rows) == len(seeded)
    for row, seed in zip(rows, seeded):
        for column in VOLATILE:
            assert row.pop(column) == placeholder(column)
            seed = {k: v for k, v in seed.items() if k != column}
        assert row == seed
