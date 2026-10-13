from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path
from runpy import run_path

import pytest

from migration.snowflake.target.python.capacity_forecast import _forecast

ORIGINAL_FORECAST: Callable[[list[tuple[date, int]], date], int] = run_path(
    str(Path(__file__).resolve().parents[5] / "etl" / "scripts" / "capacity_forecast_weekly.py")
)["_forecast"]


@pytest.mark.parametrize(
    ("values", "business_date"),
    [
        (
            [
                (date(2026, 9, 1), 10),
                (date(2026, 9, 2), 20),
                (date(2026, 9, 3), 30),
            ],
            date(2026, 9, 3),
        ),
        (
            [
                (date(2026, 9, 1), 100),
                (date(2026, 9, 2), 100),
                (date(2026, 9, 3), 100),
            ],
            date(2026, 9, 3),
        ),
        (
            [
                (date(2026, 9, 1), 100),
                (date(2026, 9, 2), 50),
                (date(2026, 9, 3), 0),
            ],
            date(2026, 9, 3),
        ),
        (
            [(date(2026, 9, 3), 10), (date(2026, 9, 3), 20)],
            date(2026, 9, 3),
        ),
    ],
)
def test_forecast_matches_the_source_algorithm(
    values: list[tuple[date, int]], business_date: date
) -> None:
    assert _forecast(values, business_date) == ORIGINAL_FORECAST(values, business_date)
