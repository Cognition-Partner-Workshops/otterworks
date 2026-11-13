"""Transaction boundaries the callers inherit: R9, R21, R35.

Every procedure ends with a bare COMMIT or ROLLBACK, so it also commits or
discards whatever the calling session had pending. resolve_rate does neither.
"""

from datetime import date

import pytest

PENDING = ("INSERT INTO rate_audit_log (action, detail, actor)"
           " VALUES ('CALLER_PENDING', 'uncommitted caller work', 'caller')")
COUNT = "SELECT COUNT(*) FROM rate_audit_log WHERE action = 'CALLER_PENDING'"


def pend(h):
    with h.caller.cursor() as cur:
        cur.execute(PENDING)
    assert h.scalar(COUNT, conn=h.caller) == 1
    assert h.scalar(COUNT) == 0


@pytest.mark.rule("R9")
def test_success_commits_callers_pending_work(h):
    pend(h)
    out = h.upsert_commission_rate("AUTO-STD", None, "8.50", date(2026, 1, 1), "char").assert_ok()
    assert [r["action"] for r in out.rows("rate_audit_log")] == ["CALLER_PENDING", "RATE_UPSERT"]
    assert h.scalar(COUNT) == 1


@pytest.mark.rule("R9")
def test_rejection_discards_callers_pending_work(h):
    pend(h)
    h.upsert_commission_rate("AUTO-STD", 4, "9", date(2026, 1, 1), "char") \
        .assert_error("ORA-20003", "Agent 4 is SUSPENDED").assert_no_writes()
    assert h.scalar(COUNT, conn=h.caller) == 0


@pytest.mark.rule("R10", "R11")
def test_end_rate_rejection_discards_callers_pending_work(h):
    pend(h)
    h.end_commission_rate("TERM-20", 2, date(2026, 1, 1), "char").assert_error(
        "ORA-20007", "No open rate for TERM-20/2")
    assert h.scalar(COUNT, conn=h.caller) == 0


@pytest.mark.rule("R21")
def test_split_rejection_discards_callers_pending_work(h):
    pend(h)
    h.set_commission_splits(3, [(1, "60"), (2, "39.99")], "char").assert_error(
        "ORA-20006", "Split percentages must total 100.00, got 99.99")
    assert h.scalar(COUNT, conn=h.caller) == 0


@pytest.mark.rule("R35")
def test_calculation_rejection_discards_callers_pending_work(h):
    pend(h)
    h.calculate_policy_commission(5, "2025-06", "char").assert_error("ORA-20008", "Policy 5 is LAPSED")
    assert h.scalar(COUNT, conn=h.caller) == 0


@pytest.mark.rule("R24")
def test_resolve_rate_failure_leaves_callers_transaction_open(h):
    pend(h)
    h.resolve_rate("AUTO-STD", 2, date(2023, 1, 1)).assert_error(
        "ORA-20007", "No rate in force for AUTO-STD/agent 2 on 2023-01-01")
    assert h.scalar(COUNT, conn=h.caller) == 1
    assert h.scalar(COUNT) == 0
    h.caller.rollback()
