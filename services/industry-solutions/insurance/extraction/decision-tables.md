# Commission decision tables

These describe **observed source logic**, not an approved replacement. All amounts are currency units (the scan uses dollars); no currency code is persisted in the fixture. Dates are Oracle DATE values, not normalized day-only values. `MONTHS_BETWEEN` may be fractional and has Oracle month-end semantics.

## Premium tiers — CP-018/019/045/046 (amber D1/D2)

| Current annual premium | Payment tier | Warehouse tier | CP-114 p1 §3 |
|---|---|---|---|
| 0 < p < 50,000 | T1 | T1 | T1 at issue |
| p = 50,000 | T2 | T1 | T2 at issue |
| p > 50,000 | T2 | T2 | T2 at issue |
| Premium subsequently changes across boundary | Recomputed on payment rerun | Recomputed on ETL load | Tier must remain fixed at issue |

Zero/negative policy premiums are rejected by the table constraint. The public premium_tier function itself has no validation (NULL returns T2), but calculation receives a mandatory positive policy premium. ETL can assign a tier to a chargeback even though its OLTP tier_code is null.

## WL-PAR tier schedule — CP-020/021/022 (activation amber D3)

| Tier | Policy issue date | Payment schedule rate | Spec rate |
|---|---|---|---|
| T1 | d <= 2020-01-01 | No rate, -20007 | 45% on 2020-01-01; earlier not specified |
| T1 | 2020-01-01 < d < 2025-07-01 | 45% | 45% |
| T1 | d = 2025-07-01 | 45% | 40% |
| T1 | d > 2025-07-01 | 40% | 40% |
| T2 | d <= 2020-01-01 | No rate, -20007 | 30% on 2020-01-01; earlier not specified |
| T2 | d > 2020-01-01 | 30% | 30% |

For DATE values with a time component, `d > change_date` is a timestamp comparison: midnight on change day fails the new row, a later time that day qualifies. The scan speaks in calendar dates; the fixture test boundaries use midnight. The rate is a whole-premium bracket rate, **not** a marginal rate on the part above $50,000.

## FIA-7 tier schedule — CP-020/021/022

| Tier | Policy issue date | Payment schedule rate | Spec rate |
|---|---|---|---|
| T1 | d <= 2020-01-01 | No rate, -20007 | 6% on 2020-01-01; earlier not specified |
| T1 | d > 2020-01-01 | 6% | 6% |
| T2 | d <= 2020-01-01 | No rate, -20007 | 4.5% on 2020-01-01; earlier not specified |
| T2 | d > 2020-01-01 | 4.5% | 4.5% |

CP-017/052: any schedule row makes a product tiered, even if all changes are in the future. Missing issue-date coverage is an error, not a fallback to flat percentage. A flat rate must nevertheless resolve at payment month end (CP-022).

## Flat-rate selection — CP-015/016/024

| Qualifying agent-specific row at period end? | Qualifying default? | Outcome |
|---|---|---|
| Yes | Either | Agent-specific row with latest effective_from |
| No | Yes | Default with latest effective_from |
| No | No | -20007; entire calculation rolled back |

Both effective_from and effective_to are inclusive; null effective_to means open. Flat defaults: AUTO-STD 8%, HOME-PLUS 10%, TERM-20 15%; AUTO-STD agent 1 override 9.5% starts 2024-06-01. Tiered products retain a flat reference rate but use the issue-date tier percentage instead.

## Chargeback bands — CP-033/034/035/036 (amber D5/D6/D7)

| Oracle elapsed months m | Existing lapse behavior | CP-114 p3 §6.1 |
|---|---|---|
| m < 0 | 100% of all ledger commission, even future periods | Invalid chronology not specified; first-year language presumes in-force policy |
| 0 <= m < 6 | 100% | Policy months 1–6: 100% |
| 6 <= m < 12 | 100% | Policy months 7–12: 50% |
| m = 12 | None | Owner must settle elapsed-month versus policy-month boundary |
| m > 12 | None | Policy month 13 onward: none |
| Surrender | No entrypoint/status | Same chargeback bands required |

The scan gives ordinal policy months, while code compares elapsed `MONTHS_BETWEEN`; do not silently equate their anniversary boundaries. For every affected agent the code reverses the entire signed sum of COMMISSION rows (post-cap paid amounts), not the current split or a recomputed entitlement. Booking month comes from the supplied lapse date. No stored lapse-processing date or future-ledger cutoff exists.

## Monthly cap — CP-029/030/031 (lifecycle amber D4)

Let P = sum of COMMISSION rows for the same agent/month on **other** policies, A = newly calculated and rounded amount.

| Condition | Stored amount |
|---|---|
| P + A <= 2,500 | A |
| P + A > 2,500 and P < 2,500 | 2,500 - P |
| P >= 2,500 and A >= 0 | 0 |
| CHARGEBACK insert | Unchanged; not counted in P |
| Direct UPDATE of a commission | Trigger does not run |

The code excludes this policy from P; it does not implement a monthly batch allocation. Earlier calculations consume allowance first. Reruns can redistribute allowance but do not top up other rows automatically; excess is not carried forward. Concurrent writers are not serialized by the source; concurrency is not characterized by this suite.
