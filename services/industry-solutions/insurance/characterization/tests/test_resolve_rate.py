"""resolve_rate: R22-R24."""

from datetime import date

import pytest


@pytest.mark.rule("R22", "R23")
@pytest.mark.parametrize(
    ("agent", "as_of", "rate_id"),
    [(1, date(2025, 6, 15), 4),     # agent override wins
     (2, date(2025, 6, 15), 1),     # no override: product default
     (None, date(2025, 6, 15), 1),  # default scope
     (1, date(2024, 5, 31), 1),     # day before the override starts
     (1, date(2024, 6, 1), 4),      # override's first day
     (4, date(2025, 6, 15), 1)],    # agent status is not checked
)
def test_agent_specific_rate_beats_product_default(h, agent, as_of, rate_id):
    out = h.resolve_rate("AUTO-STD", agent, as_of).assert_ok().assert_no_writes()
    assert out.outputs == {"rate_id": rate_id}


@pytest.mark.rule("R22")
def test_window_boundaries_after_supersession(h):
    h.upsert_commission_rate("AUTO-STD", None, "8.50", date(2026, 1, 1), "char").assert_ok()
    assert h.resolve_rate("AUTO-STD", 2, date(2025, 12, 31)).outputs == {"rate_id": 1}
    assert h.resolve_rate("AUTO-STD", 2, date(2026, 1, 1)).outputs == {"rate_id": 5}


@pytest.mark.rule("R23")
def test_latest_starting_rate_wins_within_a_scope(h):
    # Overlap within one scope is only reachable by ending a rate in the
    # future and then opening a new one inside that window.
    h.end_commission_rate("AUTO-STD", None, date(2026, 12, 31), "char").assert_ok()
    h.upsert_commission_rate("AUTO-STD", None, "8.50", date(2026, 1, 1), "char").assert_ok()
    assert h.rate(1)["effective_to"] == "2026-12-31"
    assert h.resolve_rate("AUTO-STD", 2, date(2026, 6, 15)).outputs == {"rate_id": 5}
    assert h.resolve_rate("AUTO-STD", 2, date(2025, 6, 15)).outputs == {"rate_id": 1}


@pytest.mark.rule("R23")
def test_agent_rate_wins_even_when_default_started_later(h):
    h.upsert_commission_rate("AUTO-STD", None, "12.00", date(2025, 1, 1), "char").assert_ok()
    assert h.resolve_rate("AUTO-STD", 1, date(2025, 6, 15)).outputs == {"rate_id": 4}


@pytest.mark.rule("R24")
@pytest.mark.parametrize(
    ("product", "agent", "as_of", "message"),
    [("AUTO-STD", 2, date(2023, 12, 31), "No rate in force for AUTO-STD/agent 2 on 2023-12-31"),
     ("NOPE", None, date(2025, 6, 15), "No rate in force for NOPE/agent default on 2025-06-15")],
)
def test_no_rate_in_force_rejected(h, product, agent, as_of, message):
    h.resolve_rate(product, agent, as_of).assert_error("ORA-20007", message).assert_no_writes()
