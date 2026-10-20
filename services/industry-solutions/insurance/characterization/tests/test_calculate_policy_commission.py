"""calculate_policy_commission: R25-R35, R37."""

from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal

import pytest

ACTOR = "char"


def ledger_row(ledger_id, policy, agent, rate_id, split, premium, amount, period="2025-06"):
    return {"ledger_id": ledger_id, "policy_id": policy, "agent_id": agent, "period_month": period,
            "rate_id": rate_id, "split_pct": split, "base_premium": premium, "commission_amt": amount}


def calc_audit(audit_id, policy, detail, product="AUTO-STD"):
    return {"audit_id": audit_id, "action": "COMMISSION_CALC", "product_code": product, "agent_id": None,
            "policy_id": policy, "detail": detail, "actor": ACTOR}


@pytest.mark.rule("R27", "R29", "R30", "R32", "R34")
def test_three_way_split_ledger(h):
    # premium 9600 / 12 = 800. Agent 1 has the 9.50 override, agents 2 and 3 the 8.00 default.
    out = h.calculate_policy_commission(4, "2025-06", ACTOR).assert_ok()
    assert out.writes == {
        "commission_ledger": {"inserted": [
            ledger_row(1, 4, 1, 4, "50", "9600", "38"),
            ledger_row(2, 4, 2, 1, "30", "9600", "19.2"),
            ledger_row(3, 4, 3, 1, "20", "9600", "12.8"),
        ]},
        "rate_audit_log": {"inserted": [calc_audit(1, 4, "2025-06 rows=3")]},
    }


@pytest.mark.rule("R28", "R34")
def test_rerun_is_idempotent(h):
    first = h.calculate_policy_commission(4, "2025-06", ACTOR).assert_ok()
    second = h.calculate_policy_commission(4, "2025-06", ACTOR).assert_ok()
    strip = [{k: v for k, v in r.items() if k != "ledger_id"} for r in first.rows("commission_ledger")]
    assert [{k: v for k, v in r.items() if k != "ledger_id"} for r in second.rows("commission_ledger")] == strip
    assert second.rows("commission_ledger", "deleted") == first.rows("commission_ledger")
    assert [r["ledger_id"] for r in h.ledger(4, "2025-06")] == [4, 5, 6]
    # Each run writes its own audit row.
    assert second.rows("rate_audit_log") == [calc_audit(2, 4, "2025-06 rows=3")]


@pytest.mark.rule("R28")
def test_rerun_only_touches_its_own_period_and_follows_split_changes(h):
    h.calculate_policy_commission(4, "2025-05", ACTOR).assert_ok()
    h.calculate_policy_commission(4, "2025-06", ACTOR).assert_ok()
    h.set_commission_splits(4, [(2, "100")], ACTOR).assert_ok()
    out = h.calculate_policy_commission(4, "2025-06", ACTOR).assert_ok()
    assert [r["ledger_id"] for r in out.rows("commission_ledger", "deleted")] == [4, 5, 6]
    assert out.rows("commission_ledger") == [ledger_row(7, 4, 2, 1, "100", "9600", "64")]
    assert [r["ledger_id"] for r in h.ledger(4, "2025-05")] == [1, 2, 3]


@pytest.mark.rule("R30", "R31", "R37")
def test_half_cent_rounds_up_per_row_and_rows_exceed_naive_total(h):
    # premium 1200 -> 100/month; 100 * 8.77% = 8.77 for the policy. Each
    # 50% row is exactly 4.385, which ROUND takes to 4.39 (HALF_EVEN would
    # give 4.38), so the agents are paid 8.78 against a naive 8.77.
    h.upsert_commission_rate("TERM-20", None, "8.77", date(2025, 1, 1), ACTOR).assert_ok()
    h.set_commission_splits(3, [(2, "50"), (3, "50")], ACTOR).assert_ok()
    out = h.calculate_policy_commission(3, "2025-06", ACTOR).assert_ok()
    amounts = [Decimal(r["commission_amt"]) for r in out.rows("commission_ledger")]
    assert amounts == [Decimal("4.39"), Decimal("4.39")]
    assert sum(amounts) == Decimal("8.78")
    naive = h.scalar("SELECT ROUND(1200 / 12 * 8.77 / 100, 2) FROM dual")
    assert naive == Decimal("8.77")
    assert Decimal("4.385").quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN) == Decimal("4.38")
    h.note("naive_policy_total", naive)


@pytest.mark.rule("R30", "R31", "R37")
@pytest.mark.parametrize(
    ("product", "splits", "expected"),
    [("AUTO-STD", [(2, "50"), (3, "50")], ["3.33", "3.33"]),
     ("HOME-PLUS", [(1, "33.34"), (2, "33.33"), (3, "33.33")], ["2.78", "2.78", "2.78"])],
    ids=["rows-short-of-naive", "rows-over-naive"],
)
def test_rows_do_not_sum_to_naive_total(h, product, splits, expected):
    # premium 1000 -> 83.333.../month. Rows are rounded independently and the
    # residue cent is neither allocated nor clawed back.
    h.setup("INSERT INTO policies (policy_id, policy_no, product_code, holder_name, annual_premium,"
            " issued_date, status) VALUES (6, 'POL-2025-0006', :product, 'Rounding Case', 1000.00,"
            " DATE '2025-06-01', 'IN_FORCE')", {"product": product})
    h.set_commission_splits(6, splits, ACTOR).assert_ok()
    out = h.calculate_policy_commission(6, "2025-06", ACTOR).assert_ok()
    rows = out.rows("commission_ledger")
    assert [r["commission_amt"] for r in rows] == expected
    rows_total = sum(Decimal(r["commission_amt"]) for r in rows)
    naive = h.scalar(
        "SELECT ROUND(SUM(1000 / 12 * r.rate_pct / 100 * l.split_pct / 100), 2)"
        " FROM commission_ledger l JOIN commission_rates r ON r.rate_id = l.rate_id"
        " WHERE l.policy_id = 6 AND l.period_month = '2025-06'")
    assert rows_total != naive
    h.note("rows_total_vs_naive", [rows_total, naive])


@pytest.mark.rule("R27")
@pytest.mark.parametrize(
    ("new_from", "june_rate_id", "june_amounts"),
    [(date(2025, 6, 15), 5, ["14.4", "9.6"]),    # mid-month change applies to all of June
     (date(2025, 6, 30), 5, ["14.4", "9.6"]),    # change on the last day still applies
     (date(2025, 7, 1), 2, ["12", "8"])],        # change next month does not
)
def test_rate_resolved_on_last_day_of_period(h, new_from, june_rate_id, june_amounts):
    # policy 2: HOME-PLUS, 2400 -> 200/month, splits agent 1 60% / agent 2 40%.
    h.upsert_commission_rate("HOME-PLUS", None, "12.00", new_from, ACTOR).assert_ok()
    out = h.calculate_policy_commission(2, "2025-06", ACTOR).assert_ok()
    rows = out.rows("commission_ledger")
    assert {r["rate_id"] for r in rows} == {june_rate_id}
    assert [r["commission_amt"] for r in rows] == june_amounts
    may = h.calculate_policy_commission(2, "2025-05", ACTOR).assert_ok()
    assert [r["commission_amt"] for r in may.rows("commission_ledger")] == ["12", "8"]


@pytest.mark.rule("R26")
def test_lapsed_policy_rejected(h):
    h.calculate_policy_commission(5, "2025-06", ACTOR) \
        .assert_error("ORA-20008", "Policy 5 is LAPSED").assert_no_writes()


@pytest.mark.rule("R26")
def test_cancelled_policy_rejected_and_earlier_rows_kept(h):
    h.calculate_policy_commission(1, "2025-06", ACTOR).assert_ok()
    h.setup("UPDATE policies SET status = 'CANCELLED' WHERE policy_id = 1")
    h.calculate_policy_commission(1, "2025-06", ACTOR) \
        .assert_error("ORA-20008", "Policy 1 is CANCELLED").assert_no_writes()
    assert len(h.ledger(1, "2025-06")) == 1


@pytest.mark.rule("R25")
def test_unknown_policy_rejected(h):
    h.calculate_policy_commission(999, "2025-06", ACTOR) \
        .assert_error("ORA-20005", "Unknown policy: 999").assert_no_writes()


@pytest.mark.rule("R26")
def test_status_checked_before_period_is_parsed(h):
    h.calculate_policy_commission(5, "2025-13", ACTOR).assert_error("ORA-20008", "Policy 5 is LAPSED")


@pytest.mark.rule("R27", "R35")
def test_invalid_period_rejected(h):
    out = h.calculate_policy_commission(1, "2025-13", ACTOR)
    assert out.error.code == "ORA-01843"
    out.assert_no_writes()


@pytest.mark.rule("R33")
def test_policy_without_splits_rejected(h):
    h.calculate_policy_commission(3, "2025-06", ACTOR) \
        .assert_error("ORA-20006", "Policy 3 has no split allocation").assert_no_writes()


@pytest.mark.rule("R33", "R35")
def test_no_splits_after_delete_restores_previous_rows(h):
    h.calculate_policy_commission(1, "2025-06", ACTOR).assert_ok()
    h.setup("DELETE FROM commission_splits WHERE policy_id = 1")
    h.calculate_policy_commission(1, "2025-06", ACTOR) \
        .assert_error("ORA-20006", "Policy 1 has no split allocation").assert_no_writes()
    assert h.ledger(1, "2025-06") == [
        {"ledger_id": 1, "agent_id": 1, "rate_id": 4, "split_pct": "100", "base_premium": "1800",
         "commission_amt": "14.25"}]


@pytest.mark.rule("R29")
@pytest.mark.parametrize(
    ("splits", "order"),
    [([(3, "50"), (2, "50")], [2, 3]),          # tie on split_pct: agent_id ascending
     ([(2, "30"), (3, "70")], [3, 2]),          # larger split first
     ([(1, "20"), (3, "40"), (2, "40")], [2, 3, 1])],
)
def test_ledger_rows_written_in_split_order(h, splits, order):
    h.set_commission_splits(3, splits, ACTOR).assert_ok()
    out = h.calculate_policy_commission(3, "2025-06", ACTOR).assert_ok()
    assert [r["agent_id"] for r in out.rows("commission_ledger")] == order


@pytest.mark.rule("R24", "R35")
def test_failure_midway_rolls_back_partial_ledger(h):
    # Agent 1 (50%) resolves its override and gets a row; agent 2 (30%) then
    # finds no default in force on 2025-06-30, after the old rows were deleted.
    h.calculate_policy_commission(4, "2025-06", ACTOR).assert_ok()
    h.end_commission_rate("AUTO-STD", None, date(2025, 5, 31), ACTOR).assert_ok()
    h.calculate_policy_commission(4, "2025-06", ACTOR) \
        .assert_error("ORA-20007", "No rate in force for AUTO-STD/agent 2 on 2025-06-30").assert_no_writes()
    assert [r["ledger_id"] for r in h.ledger(4, "2025-06")] == [1, 2, 3]


@pytest.mark.rule("R34", "R35")
def test_null_actor_fails_at_audit_and_rolls_back(h):
    h.calculate_policy_commission(4, "2025-06", ACTOR).assert_ok()
    out = h.calculate_policy_commission(4, "2025-06", None)
    assert out.error.code == "ORA-01400"
    out.assert_no_writes()
    assert [r["ledger_id"] for r in h.ledger(4, "2025-06")] == [1, 2, 3]
