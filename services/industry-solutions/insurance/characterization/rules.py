"""RULE_LEDGER.md numbering (R1-R38) and what the legacy SQL suite covered.

``legacy`` is the coverage column from the ledger: ``covered``, ``partial``
(the ledger lists an uncovered half) or ``none``.
"""

RULES: dict[str, tuple[str, str, str]] = {
    # id: (procedure / area, rule, legacy run_tests.sql coverage)
    "R1": ("upsert_commission_rate", "rate_pct non-NULL and in (0, 50], else ORA-20001", "partial: T2 (>50 only)"),
    "R2": ("upsert_commission_rate", "product must exist, else ORA-20004", "none"),
    "R3": ("upsert_commission_rate", "named agent must exist, else ORA-20002", "none"),
    "R4": ("upsert_commission_rate", "named agent must be ACTIVE, else ORA-20003", "partial: T3 (SUSPENDED only)"),
    "R5": ("upsert_commission_rate", "same-day correction amends the open rate in place", "covered: T1b"),
    "R6": ("upsert_commission_rate", "prior open rate closed the day before the new one", "covered: T1"),
    "R7": ("upsert_commission_rate", "new open rate inserted, id returned", "covered: T1"),
    "R8": ("upsert_commission_rate", "audit RATE_UPSERT 'rate_id=<id> pct=<pct> from=<date>'", "partial: T12 (count only)"),
    "R9": ("upsert_commission_rate", "atomic: COMMIT on success, ROLLBACK + re-raise on error", "none"),
    "R10": ("end_commission_rate", "closes the open rate for a scope at p_effective_to", "none"),
    "R11": ("end_commission_rate", "no open rate raises ORA-20007", "none"),
    "R12": ("end_commission_rate", "audit RATE_END 'to=<date>'", "none"),
    "R13": ("set_commission_splits", "policy must exist, else ORA-20005", "none"),
    "R14": ("set_commission_splits", "at least one allocation (NULL/empty -> ORA-20006)", "covered: T11"),
    "R15": ("set_commission_splits", "no duplicate agent -> ORA-20006", "covered: T5"),
    "R16": ("set_commission_splits", "each split_pct non-NULL and in (0, 100], in order", "none"),
    "R17": ("set_commission_splits", "each agent exists and ACTIVE (-20002/-20003), per item", "none"),
    "R18": ("set_commission_splits", "split_pct total exactly 100 -> else ORA-20006", "partial: T4 (over 100 only)"),
    "R19": ("set_commission_splits", "wholesale replace, inserted in collection order", "partial: T6 (count/sum)"),
    "R20": ("set_commission_splits", "audit SPLIT_SET '<n> agents'", "partial: T12 (count only)"),
    "R21": ("set_commission_splits", "atomic: rejected allocation leaves the previous one", "none"),
    "R22": ("resolve_rate", "candidates: product, window contains as_of, agent or default", "covered: T7/T7b"),
    "R23": ("resolve_rate", "agent rate beats default; latest-starting wins in scope", "partial: T7 (no tie-break)"),
    "R24": ("resolve_rate", "no rate in force raises ORA-20007", "none"),
    "R25": ("calculate_policy_commission", "policy must exist, else ORA-20005", "none"),
    "R26": ("calculate_policy_commission", "LAPSED/CANCELLED raise ORA-20008", "partial: T10 (LAPSED only)"),
    "R27": ("calculate_policy_commission", "rate resolved on the last day of the period month", "partial: T8 (indirect)"),
    "R28": ("calculate_policy_commission", "re-run replaces the period's rows (idempotent)", "covered: T9"),
    "R29": ("calculate_policy_commission", "splits processed split_pct DESC, agent_id", "none"),
    "R30": ("calculate_policy_commission", "ROUND(premium/12*rate/100*split/100, 2) per agent row", "covered: T8a-c"),
    "R31": ("calculate_policy_commission", "no remainder redistribution across agent rows", "none"),
    "R32": ("calculate_policy_commission", "row records rate_id, split_pct, annual premium as base", "partial: T8 (amount only)"),
    "R33": ("calculate_policy_commission", "no split allocation raises ORA-20006, after the delete", "none"),
    "R34": ("calculate_policy_commission", "audit COMMISSION_CALC '<period> rows=<n>'", "partial: T12 (count only)"),
    "R35": ("calculate_policy_commission", "atomic: COMMIT on success, ROLLBACK + re-raise", "none"),
    "R36": ("cross-cutting", "rate scope is (product_code, NVL(agent_id,-1)); one open per scope", "covered: T1/T1b"),
    "R37": ("cross-cutting", "exact Oracle NUMBER arithmetic, never binary float", "partial: implied by T8"),
    "R38": ("cross-cutting", "default TO_CHAR in messages/audit (8.50 -> 8.5, 0.5 -> .5)", "none"),
}
