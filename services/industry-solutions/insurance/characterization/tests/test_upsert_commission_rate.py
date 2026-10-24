"""upsert_commission_rate: R1-R9, R36-R38."""

from datetime import date

import pytest

ACTOR = "char"


def audit_row(audit_id, detail, product="AUTO-STD", agent=None, actor=ACTOR):
    return {"audit_id": audit_id, "action": "RATE_UPSERT", "product_code": product, "agent_id": agent,
            "policy_id": None, "detail": detail, "actor": actor}


@pytest.mark.rule("R6", "R7", "R8", "R36")
def test_supersession_closes_prior_rate_the_day_before(h):
    out = h.upsert_commission_rate("AUTO-STD", None, "8.50", date(2026, 1, 1), ACTOR).assert_ok()
    assert out.outputs == {"o_rate_id": 5}
    assert out.writes == {
        "commission_rates": {
            "inserted": [{"rate_id": 5, "product_code": "AUTO-STD", "agent_id": None, "rate_pct": "8.5",
                          "effective_from": "2026-01-01", "effective_to": None, "created_by": ACTOR}],
            "updated": [{"rate_id": 1, "changes": {"effective_to": [None, "2025-12-31"]}}],
        },
        "rate_audit_log": {"inserted": [audit_row(1, "rate_id=5 pct=8.5 from=2026-01-01")]},
    }
    # R36: the agent-1 override (rate 4) is a different scope and stays open.
    assert h.rate(4)["effective_to"] is None


@pytest.mark.rule("R6")
@pytest.mark.parametrize(
    ("effective_from", "closed_on"),
    [
        (date(2028, 3, 1), "2028-02-29"),   # leap day
        (date(2025, 1, 1), "2024-12-31"),   # year boundary
        (date(2024, 1, 2), "2024-01-01"),   # prior rate closes on its own start day
    ],
)
def test_supersession_day_before_boundaries(h, effective_from, closed_on):
    out = h.upsert_commission_rate("AUTO-STD", None, "8.00", effective_from, ACTOR).assert_ok()
    assert out.rows("commission_rates", "updated") == [
        {"rate_id": 1, "changes": {"effective_to": [None, closed_on]}}
    ]


@pytest.mark.rule("R5", "R8")
def test_same_day_correction_amends_instead_of_inserting(h):
    first = h.upsert_commission_rate("AUTO-STD", None, "8.50", date(2026, 1, 1), "alice").assert_ok()
    second = h.upsert_commission_rate("AUTO-STD", None, "8.75", date(2026, 1, 1), "bob").assert_ok()
    assert first.outputs == second.outputs == {"o_rate_id": 5}
    assert second.writes == {
        "commission_rates": {
            "updated": [{"rate_id": 5, "changes": {"created_by": ["alice", "bob"], "rate_pct": ["8.5", "8.75"]}}]
        },
        "rate_audit_log": {"inserted": [audit_row(2, "rate_id=5 pct=8.75 from=2026-01-01", actor="bob")]},
    }
    open_rows = h.query("SELECT rate_id FROM commission_rates WHERE product_code = 'AUTO-STD'"
                        " AND agent_id IS NULL AND effective_to IS NULL")
    assert open_rows == [{"rate_id": 5}]
    assert h.rate(1)["effective_to"] == "2025-12-31"


@pytest.mark.rule("R5", "R36")
def test_same_day_correction_of_a_seeded_rate(h):
    out = h.upsert_commission_rate("AUTO-STD", 1, "9.75", date(2024, 6, 1), ACTOR).assert_ok()
    assert out.outputs == {"o_rate_id": 4}
    assert out.rows("commission_rates", "updated") == [
        {"rate_id": 4, "changes": {"created_by": ["seed", ACTOR], "rate_pct": ["9.5", "9.75"]}}
    ]
    assert out.rows("commission_rates") == []


@pytest.mark.rule("R36", "R9")
def test_backdated_rate_collides_with_open_rate(h):
    # Nothing starts earlier than 2023-06-01, so nothing is closed, and the
    # second open row for the scope trips ux_rates_open.
    out = h.upsert_commission_rate("AUTO-STD", None, "7.00", date(2023, 6, 1), ACTOR)
    out.assert_error("ORA-00001", out.error.message)
    assert "UX_RATES_OPEN" in out.error.message
    out.assert_no_writes()


@pytest.mark.rule("R36")
def test_agent_and_default_scopes_are_independent(h):
    agent2 = h.upsert_commission_rate("AUTO-STD", 2, "9.00", date(2026, 1, 1), ACTOR).assert_ok()
    assert agent2.outputs == {"o_rate_id": 5}
    assert agent2.rows("commission_rates", "updated") == []
    agent1 = h.upsert_commission_rate("AUTO-STD", 1, "10.00", date(2026, 1, 1), ACTOR).assert_ok()
    assert agent1.rows("commission_rates", "updated") == [
        {"rate_id": 4, "changes": {"effective_to": [None, "2025-12-31"]}}
    ]
    assert h.rate(1)["effective_to"] is None


@pytest.mark.rule("R1", "R38")
@pytest.mark.parametrize(
    ("rate_pct", "shown"),
    [("0", "0"), ("-1", "-1"), ("-0.5", "-.5"), (None, "NULL"), ("50.01", "50.01"),
     ("55", "55"), ("50.001", "50.001")],
)
def test_rate_outside_bounds_rejected(h, rate_pct, shown):
    out = h.upsert_commission_rate("AUTO-STD", None, rate_pct, date(2026, 2, 1), ACTOR)
    out.assert_error("ORA-20001", f"Rate must be in (0, 50]: {shown}").assert_no_writes()


@pytest.mark.rule("R1", "R38")
@pytest.mark.parametrize(("rate_pct", "shown"), [("50", "50"), ("0.01", ".01"), ("0.5", ".5")])
def test_rate_bounds_inclusive_edges_accepted(h, rate_pct, shown):
    out = h.upsert_commission_rate("HOME-PLUS", None, rate_pct, date(2026, 2, 1), ACTOR).assert_ok()
    (audit,) = out.rows("rate_audit_log")
    assert audit["detail"] == f"rate_id=5 pct={shown} from=2026-02-01"


@pytest.mark.rule("R9", "R37")
def test_sub_cent_rate_passes_guard_then_fails_constraint_and_rolls_back(h):
    # 0.001 is > 0 so the guard passes; NUMBER(5,2) stores it as 0.00, which
    # ck_rates_range rejects after the prior rate was already closed.
    out = h.upsert_commission_rate("AUTO-STD", None, "0.001", date(2026, 1, 1), ACTOR)
    assert out.error.code == "ORA-02290"
    assert "CK_RATES_RANGE" in out.error.message
    out.assert_no_writes()
    assert h.rate(1)["effective_to"] is None


@pytest.mark.rule("R37", "R38")
def test_three_decimal_rate_stored_rounded_but_audited_unrounded(h):
    out = h.upsert_commission_rate("AUTO-STD", None, "8.555", date(2026, 1, 1), ACTOR).assert_ok()
    assert h.rate(5)["rate_pct"] == "8.56"
    (audit,) = out.rows("rate_audit_log")
    assert audit["detail"] == "rate_id=5 pct=8.555 from=2026-01-01"


@pytest.mark.rule("R2")
def test_unknown_product_rejected(h):
    h.upsert_commission_rate("NOPE", None, "5", date(2026, 1, 1), ACTOR) \
        .assert_error("ORA-20004", "Unknown product: NOPE").assert_no_writes()


@pytest.mark.rule("R1", "R2", "R3")
def test_validation_order_rate_then_product_then_agent(h):
    h.upsert_commission_rate("NOPE", 999, "60", date(2026, 1, 1), ACTOR) \
        .assert_error("ORA-20001", "Rate must be in (0, 50]: 60")
    h.upsert_commission_rate("NOPE", 999, "5", date(2026, 1, 1), ACTOR) \
        .assert_error("ORA-20004", "Unknown product: NOPE")
    h.upsert_commission_rate("AUTO-STD", 999, "5", date(2026, 1, 1), ACTOR) \
        .assert_error("ORA-20002", "Unknown agent: 999").assert_no_writes()


@pytest.mark.rule("R4")
def test_suspended_agent_rejected(h):
    h.upsert_commission_rate("AUTO-STD", 4, "9", date(2026, 2, 1), ACTOR) \
        .assert_error("ORA-20003", "Agent 4 is SUSPENDED").assert_no_writes()


@pytest.mark.rule("R4")
def test_terminated_agent_rejected(h):
    h.setup("INSERT INTO agents (agent_id, agent_code, full_name, license_no, status, hired_date)"
            " VALUES (5, 'AG-104', 'Terminated Agent', 'LIC-TX-55005', 'TERMINATED', DATE '2016-01-04')")
    h.upsert_commission_rate("AUTO-STD", 5, "9", date(2026, 2, 1), ACTOR) \
        .assert_error("ORA-20003", "Agent 5 is TERMINATED").assert_no_writes()


@pytest.mark.rule("R9")
def test_null_actor_fails_after_supersede_and_rolls_back(h):
    out = h.upsert_commission_rate("AUTO-STD", None, "8.50", date(2026, 1, 1), None)
    assert out.error.code == "ORA-01400"
    assert '"COMMISSION_RATES"."CREATED_BY"' in out.error.message
    out.assert_no_writes()
    assert h.rate(1)["effective_to"] is None


@pytest.mark.rule("R5", "R9")
def test_null_actor_on_same_day_correction_rolls_back(h):
    out = h.upsert_commission_rate("AUTO-STD", None, "8.25", date(2024, 1, 1), None)
    assert out.error.code == "ORA-01407"
    out.assert_no_writes()
    assert h.rate(1)["rate_pct"] == "8"


@pytest.mark.rule("R8")
def test_one_audit_row_per_change_and_none_per_rejection(h):
    h.upsert_commission_rate("AUTO-STD", None, "8.50", date(2026, 1, 1), ACTOR).assert_ok()
    h.upsert_commission_rate("AUTO-STD", None, "8.60", date(2026, 1, 1), ACTOR).assert_ok()
    h.upsert_commission_rate("AUTO-STD", 2, "9", date(2026, 1, 1), ACTOR).assert_ok()
    h.upsert_commission_rate("AUTO-STD", 4, "9", date(2026, 1, 1), ACTOR).assert_error(
        "ORA-20003", "Agent 4 is SUSPENDED")
    rows = h.query("SELECT audit_id, action, agent_id, detail FROM rate_audit_log ORDER BY audit_id")
    assert rows == [
        {"audit_id": 1, "action": "RATE_UPSERT", "agent_id": None, "detail": "rate_id=5 pct=8.5 from=2026-01-01"},
        {"audit_id": 2, "action": "RATE_UPSERT", "agent_id": None, "detail": "rate_id=5 pct=8.6 from=2026-01-01"},
        {"audit_id": 3, "action": "RATE_UPSERT", "agent_id": 2, "detail": "rate_id=6 pct=9 from=2026-01-01"},
    ]
