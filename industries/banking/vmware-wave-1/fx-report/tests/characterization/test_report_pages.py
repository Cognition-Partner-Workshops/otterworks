"""Characterization tests: the live report at BASE_URL against the Perl stand-in's golden pages.

Values are compared after parsing (report_page.parse), so CGI.pm markup is not part of the contract.
Run: BASE_URL=http://localhost:8086 pytest fx-report/tests/characterization
"""
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

import pytest

from report_page import ReportPage, parse

GOLDEN = Path(__file__).resolve().parent.parent / "golden"
COLUMNS = ["Pair", "Close", "Average mid", "Range", "Change"]
EMPTY_DAY = "No rates file for this day yet."


@dataclass(frozen=True)
class Case:
    name: str
    query: str


CASES = [
    Case("day-2026-10-14", "?day=2026-10-14"),
    Case("day-2026-10-15", "?day=2026-10-15"),
    Case("day-2026-10-16", "?day=2026-10-16"),
    Case("day-2026-10-17", "?day=2026-10-17"),
    Case("day-foo", "?day=foo"),
    Case("no-day", ""),
]


def _yesterday(tz: str) -> str:
    return (datetime.now(ZoneInfo(tz)) - timedelta(days=1)).strftime("%Y-%m-%d")


@dataclass(frozen=True)
class AcceptedDifference:
    case: str
    reason: str
    apply: Callable[[ReportPage, str], None]  # rewrites the golden page for the zone under test


def _default_day_is_yesterday(page: ReportPage, tz: str) -> None:
    day = _yesterday(tz)
    page.title = page.title.replace("2026-10-19", day)
    page.business_line = page.business_line.replace("2026-10-19", day)
    page.business_date = day


# Every intended difference from the golden pages, with its reason. Nothing else may differ.
ACCEPTED_DIFFERENCES = [
    AcceptedDifference(
        case="no-day",
        reason="no-day.html was captured on 2026-10-20 (UTC); without ?day the report shows yesterday "
               "in the zone under test (REPORT_TZ, default UTC), so 2026-10-19 is replaced by that date",
        apply=_default_day_is_yesterday,
    ),
]


def _golden_status(name: str) -> tuple[int, str]:
    lines = (GOLDEN / f"{name}.headers").read_text().splitlines()
    status = int(lines[0].split()[1])
    ctype = next(l.split(":", 1)[1].strip() for l in lines if l.lower().startswith("content-type:"))
    return status, ctype


def _golden_page(name: str, tz: str) -> ReportPage:
    page = parse((GOLDEN / f"{name}.html").read_text(encoding="utf-8"))
    for diff in ACCEPTED_DIFFERENCES:
        if diff.case == name:
            diff.apply(page, tz)
    return page


def _fetch(url: str) -> tuple[int, str, str]:
    with urllib.request.urlopen(url, timeout=10) as resp:
        return resp.status, resp.headers.get("Content-Type", ""), resp.read().decode("utf-8")


def _norm_ctype(value: str) -> str:
    return value.replace(" ", "").lower()


@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_page_matches_golden(case, base_url, report_path, report_tz):
    status, ctype, body = _fetch(base_url + report_path + case.query)
    live = parse(body)
    golden = _golden_page(case.name, report_tz)
    if case.name == "no-day" and live.business_date != golden.business_date:
        golden = _golden_page(case.name, report_tz)  # request straddled midnight in REPORT_TZ

    g_status, g_ctype = _golden_status(case.name)
    assert status == g_status
    assert _norm_ctype(ctype) == _norm_ctype(g_ctype)

    assert live.title == golden.title
    assert live.heading == golden.heading
    assert live.business_line == golden.business_line
    assert live.business_date == golden.business_date
    assert live.user == golden.user
    assert live.empty_message == golden.empty_message
    assert live.columns == golden.columns

    assert len(live.rows) == len(golden.rows), "row count"
    for i, (lrow, grow) in enumerate(zip(live.rows, golden.rows)):
        assert len(lrow) == len(grow), f"row {i} cell count"
        for col, lcell, gcell in zip(COLUMNS, lrow, grow):
            assert lcell == gcell, f"{grow[0]} {col}: live {lcell!r} != golden {gcell!r}"


@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_golden_parses(case):
    """Guards the parser itself: each golden page yields the structure the comparison relies on."""
    page = parse((GOLDEN / f"{case.name}.html").read_text(encoding="utf-8"))
    assert page.heading == "FX desk report"
    assert page.user == "unknown"
    if case.name in ("day-2026-10-14", "day-2026-10-15", "day-2026-10-16"):
        assert page.columns == COLUMNS
        assert [r[0] for r in page.rows] == ["EURCHF", "EURGBP", "EURJPY", "EURSEK", "EURUSD"]
        assert all(len(r) == 5 for r in page.rows)
        assert page.empty_message is None
    else:
        assert page.rows == [] and page.columns == []
        assert page.empty_message == EMPTY_DAY
