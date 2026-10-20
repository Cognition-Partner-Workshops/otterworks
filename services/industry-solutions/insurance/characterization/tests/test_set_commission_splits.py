"""set_commission_splits: R13-R21, R37-R38."""

from decimal import Decimal

import pytest

ACTOR = "char"


@pytest.mark.rule("R18", "R19", "R20")
@pytest.mark.parametrize(
    "splits",
    [[(1, "50.00"), (2, "50.00")], [(1, "60.01"), (2, "39.99")], [(1, "100")],
     [(1, "33.33"), (2, "33.33"), (3, "33.34")]],
    ids=["50-50", "60.01-39.99", "sole-100", "33.33-33.33-33.34"],
)
def test_split_total_exactly_100_accepted(h, splits):
    out = h.set_commission_splits(3, splits, ACTOR).assert_ok()
    assert [(r["agent_id"], r["split_pct"]) for r in out.rows("commission_splits")] == [
        (a, format(Decimal(p).normalize(), "f")) for a, p in splits
    ]
    assert out.rows("rate_audit_log") == [{
        "audit_id": 1, "action": "SPLIT_SET", "product_code": None, "agent_id": None,
        "policy_id": 3, "detail": f"{len(splits)} agents", "actor": ACTOR}]


@pytest.mark.rule("R18", "R21", "R38")
@pytest.mark.parametrize(
    ("splits", "total"),
    [([(1, "60.00"), (2, "39.99")], "99.99"),
     ([(1, "60.01"), (2, "40.00")], "100.01"),
     ([(1, "70"), (2, "40")], "110"),
     ([(1, "50"), (2, "49.5")], "99.5")],
    ids=["99.99", "100.01", "110", "99.5"],
)
def test_split_total_not_100_rejected(h, splits, total):
    h.set_commission_splits(4, splits, ACTOR).assert_error(
        "ORA-20006", f"Split percentages must total 100.00, got {total}").assert_no_writes()
    assert len(h.splits(4)) == 3


@pytest.mark.rule("R19", "R20")
def test_allocation_replaced_wholesale_in_collection_order(h):
    out = h.set_commission_splits(4, [(3, "35"), (2, "65")], ACTOR).assert_ok()
    assert out.writes["commission_splits"] == {
        "inserted": [{"split_id": 7, "policy_id": 4, "agent_id": 3, "split_pct": "35"},
                     {"split_id": 8, "policy_id": 4, "agent_id": 2, "split_pct": "65"}],
        "deleted": [{"split_id": 4, "policy_id": 4, "agent_id": 1, "split_pct": "50"},
                    {"split_id": 5, "policy_id": 4, "agent_id": 2, "split_pct": "30"},
                    {"split_id": 6, "policy_id": 4, "agent_id": 3, "split_pct": "20"}],
    }
    assert out.rows("rate_audit_log")[0]["detail"] == "2 agents"


@pytest.mark.rule("R13")
def test_unknown_policy_rejected_before_anything_else(h):
    h.set_commission_splits(999, [(1, "100")], ACTOR) \
        .assert_error("ORA-20005", "Unknown policy: 999").assert_no_writes()
    h.set_commission_splits(999, [], ACTOR).assert_error("ORA-20005", "Unknown policy: 999")


@pytest.mark.rule("R13")
def test_lapsed_policy_allocation_is_accepted(h):
    # The status is read but not checked: allocations on LAPSED policies are allowed.
    h.set_commission_splits(5, [(1, "100")], ACTOR).assert_ok()
    assert h.splits(5) == [{"split_id": 7, "agent_id": 1, "split_pct": "100"}]


@pytest.mark.rule("R14")
@pytest.mark.parametrize("splits", [[], None], ids=["empty", "null"])
def test_empty_or_null_allocation_rejected(h, splits):
    h.set_commission_splits(1, splits, ACTOR).assert_error(
        "ORA-20006", "At least one split allocation is required").assert_no_writes()


@pytest.mark.rule("R15")
@pytest.mark.parametrize(
    "splits",
    [[(1, "50"), (1, "50")], [(1, "0"), (1, "100")], [(None, "100")]],
    ids=["same-agent", "checked-before-pct", "null-agent"],
)
def test_duplicate_agent_rejected(h, splits):
    # COUNT(DISTINCT agent_id) ignores NULL, so a NULL agent reads as a duplicate.
    h.set_commission_splits(1, splits, ACTOR).assert_error(
        "ORA-20006", "Duplicate agent in split allocation").assert_no_writes()


@pytest.mark.rule("R16")
@pytest.mark.parametrize(
    ("splits", "agent"),
    [([(1, "0"), (2, "100")], 1), ([(1, "-5"), (2, "105")], 1), ([(1, "100.01")], 1),
     ([(1, None), (2, "100")], 1), ([(1, "50"), (2, None)], 2), ([(1, "50"), (2, "0")], 2)],
    ids=["zero", "negative", "over-100", "null-first", "null-second", "zero-second"],
)
def test_split_pct_outside_bounds_rejected(h, splits, agent):
    h.set_commission_splits(1, splits, ACTOR).assert_error(
        "ORA-20006", f"Split pct must be in (0, 100]: agent {agent}").assert_no_writes()


@pytest.mark.rule("R16", "R17")
@pytest.mark.parametrize(
    ("splits", "code", "message"),
    [([(4, "50"), (1, "0")], "ORA-20003", "Agent 4 is SUSPENDED"),
     ([(1, "0"), (4, "50")], "ORA-20006", "Split pct must be in (0, 100]: agent 1"),
     ([(1, "50"), (999, "50")], "ORA-20002", "Unknown agent: 999"),
     ([(999, "150"), (1, "50")], "ORA-20006", "Split pct must be in (0, 100]: agent 999"),
     ([(5, "50"), (1, "50")], "ORA-20003", "Agent 5 is TERMINATED")],
    ids=["suspended-first", "pct-first", "unknown-agent", "pct-before-agent", "terminated"],
)
def test_agent_checks_run_per_item_in_order(h, splits, code, message):
    h.setup("INSERT INTO agents (agent_id, agent_code, full_name, license_no, status, hired_date)"
            " VALUES (5, 'AG-104', 'Terminated Agent', 'LIC-TX-55005', 'TERMINATED', DATE '2016-01-04')")
    h.set_commission_splits(1, splits, ACTOR).assert_error(code, message).assert_no_writes()


@pytest.mark.rule("R18", "R37")
def test_sum_checked_on_unrounded_input_then_stored_rounded(h):
    out = h.set_commission_splits(3, [(1, "33.333"), (2, "33.333"), (3, "33.334")], ACTOR).assert_ok()
    stored = [r["split_pct"] for r in out.rows("commission_splits")]
    assert stored == ["33.33", "33.33", "33.33"]
    assert h.scalar("SELECT SUM(split_pct) FROM commission_splits WHERE policy_id = 3") == Decimal("99.99")


@pytest.mark.rule("R21", "R37")
def test_rollback_after_delete_restores_previous_allocation(h):
    # Each item and the total pass the checks; 0.001 is stored as 0.00 and
    # ck_splits_range fires on insert, after the old rows were deleted.
    out = h.set_commission_splits(4, [(1, "99.999"), (2, "0.001")], ACTOR)
    assert out.error.code == "ORA-02290"
    assert "CK_SPLITS_RANGE" in out.error.message
    out.assert_no_writes()
    assert [r["split_id"] for r in h.splits(4)] == [4, 5, 6]


@pytest.mark.rule("R20", "R21")
def test_null_actor_fails_at_audit_and_rolls_back(h):
    out = h.set_commission_splits(4, [(1, "100")], None)
    assert out.error.code == "ORA-01400"
    assert '"RATE_AUDIT_LOG"."ACTOR"' in out.error.message
    out.assert_no_writes()
    assert [r["split_id"] for r in h.splits(4)] == [4, 5, 6]
