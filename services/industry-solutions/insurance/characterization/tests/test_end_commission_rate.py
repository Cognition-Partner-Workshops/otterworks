"""end_commission_rate: R10-R12."""

from datetime import date

import pytest

ACTOR = "char"


@pytest.mark.rule("R10", "R12")
def test_end_closes_open_default_rate(h):
    out = h.end_commission_rate("AUTO-STD", None, date(2025, 12, 31), ACTOR).assert_ok()
    assert out.writes == {
        "commission_rates": {"updated": [{"rate_id": 1, "changes": {"effective_to": [None, "2025-12-31"]}}]},
        "rate_audit_log": {"inserted": [{
            "audit_id": 1, "action": "RATE_END", "product_code": "AUTO-STD", "agent_id": None,
            "policy_id": None, "detail": "to=2025-12-31", "actor": ACTOR}]},
    }


@pytest.mark.rule("R10", "R22", "R24")
def test_end_date_is_inclusive(h):
    h.end_commission_rate("AUTO-STD", None, date(2025, 12, 31), ACTOR).assert_ok()
    assert h.resolve_rate("AUTO-STD", 2, date(2025, 12, 31)).assert_ok().outputs == {"rate_id": 1}
    h.resolve_rate("AUTO-STD", 2, date(2026, 1, 1)).assert_error(
        "ORA-20007", "No rate in force for AUTO-STD/agent 2 on 2026-01-01")


@pytest.mark.rule("R10", "R12", "R36")
def test_end_agent_scope_leaves_default_open(h):
    out = h.end_commission_rate("AUTO-STD", 1, date(2025, 12, 31), ACTOR).assert_ok()
    assert out.rows("commission_rates", "updated") == [
        {"rate_id": 4, "changes": {"effective_to": [None, "2025-12-31"]}}
    ]
    assert out.rows("rate_audit_log")[0]["agent_id"] == 1
    assert h.rate(1)["effective_to"] is None


@pytest.mark.rule("R11")
@pytest.mark.parametrize(
    ("product", "agent", "message"),
    [
        ("TERM-20", 2, "No open rate for TERM-20/2"),
        ("NOPE", None, "No open rate for NOPE/default"),   # product is not validated
        ("AUTO-STD", 4, "No open rate for AUTO-STD/4"),    # agent status is not checked
    ],
)
def test_end_without_open_rate_rejected(h, product, agent, message):
    h.end_commission_rate(product, agent, date(2025, 12, 31), ACTOR) \
        .assert_error("ORA-20007", message).assert_no_writes()


@pytest.mark.rule("R11")
def test_end_twice_rejected_second_time(h):
    h.end_commission_rate("AUTO-STD", None, date(2025, 12, 31), ACTOR).assert_ok()
    h.end_commission_rate("AUTO-STD", None, date(2026, 6, 30), ACTOR) \
        .assert_error("ORA-20007", "No open rate for AUTO-STD/default").assert_no_writes()


@pytest.mark.rule("R10")
def test_end_before_start_violates_check_and_rolls_back(h):
    out = h.end_commission_rate("AUTO-STD", 1, date(2024, 5, 31), ACTOR)
    assert out.error.code == "ORA-02290"
    assert "CK_RATES_DATES" in out.error.message
    out.assert_no_writes()


@pytest.mark.rule("R10", "R12")
def test_end_null_actor_fails_at_audit_and_rolls_back(h):
    out = h.end_commission_rate("AUTO-STD", None, date(2025, 12, 31), None)
    assert out.error.code == "ORA-01400"
    assert '"RATE_AUDIT_LOG"."ACTOR"' in out.error.message
    out.assert_no_writes()
    assert h.rate(1)["effective_to"] is None
