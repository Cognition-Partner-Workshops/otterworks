# Commission Pay: cutover reconciliation

This report covers what has moved off Oracle `COMMISSION_PKG`, `DW_ETL_PKG` and `MV_AGENT_COMMISSION_SUMMARY`, and what still has to. Each number is quoted from the pull request, or the nightly issue, that produced it. This report did not re-run anything and did not start any containers. Two figures were added up here from files committed on those PRs, and they are labelled where they appear.

Every pull request below is **open**. None has merged, so "moved" means "moved on a branch, with evidence". Nothing has cut over in production.

Short version for finance: [FINANCE_DIGEST.md](FINANCE_DIGEST.md).

## Branch heads read

| PR | What | Base | Head |
|---|---|---|---|
| [#2087](https://github.com/Cognition-Partner-Workshops/otterworks/pull/2087) | Assessment and wave plan (`industries/insurance/commission-pay/ASSESSMENT.md`) | demo-insurance | `ab7f3a0b2` |
| [#2088](https://github.com/Cognition-Partner-Workshops/otterworks/pull/2088) | Characterization harness, R1-R38, 104 golden cases (`services/industry-solutions/insurance/characterization/`) | main | `65e090d13` |
| [#2090](https://github.com/Cognition-Partner-Workshops/otterworks/pull/2090) | `commission-service` skeleton and `call_service` strangler route | main | `3593eae34` |
| [#2123](https://github.com/Cognition-Partner-Workshops/otterworks/pull/2123) | Rates rule group delegated to Java | main | `1e751f09a` |
| [#2122](https://github.com/Cognition-Partner-Workshops/otterworks/pull/2122) | Splits rule group delegated to Java | main | `83fae3748` |
| [#2124](https://github.com/Cognition-Partner-Workshops/otterworks/pull/2124) | Calculation rule group delegated to Java | main | `12a34be66` |
| [#2097](https://github.com/Cognition-Partner-Workshops/otterworks/pull/2097) | Oracle to PostgreSQL 16 schema, data and reconciliation | main | `65c01df96` |
| [#2115](https://github.com/Cognition-Partner-Workshops/otterworks/pull/2115) | dbt phase 1: Oracle month-end baseline and golden CSVs | main | `475fcd7ef` |
| [#2132](https://github.com/Cognition-Partner-Workshops/otterworks/pull/2132) | dbt phase 2: dbt-postgres project on PostgreSQL 16 (stacked on #2115) | main | `d38de4291` |
| [#2130](https://github.com/Cognition-Partner-Workshops/otterworks/pull/2130) | Commission statement and rate-history screens, `COMMISSION_BACKEND=oracle\|postgres` | main | `816d8f7c0` |
| [#2131](https://github.com/Cognition-Partner-Workshops/otterworks/issues/2131) | Nightly parity gate, first run (issue) | n/a | gate = main `f417322a6` + #2088 + #2097 + #2122 |

## What moved

One row per unit. A red row stays red, and its cause is in the same row.

| # | Unit | From | To | Source value (old) | Target value (new) | Difference | Verdict | Evidence |
|---|---|---|---|---|---|---|---|---|
| 1 | Legacy behaviour pinned (R1-R38) | `COMMISSION_PKG` on Oracle Free | 104 golden JSON files plus `rule_report` | 38 rules, `run_tests.sql` T1-T12 | 104/104 tests pass, 38/38 rules PASS | none | **GREEN** | [#2088](https://github.com/Cognition-Partner-Workshops/otterworks/pull/2088) |
| 2 | Strangler route (`call_service`, no rule moved) | PL/SQL | Java 21 / Spring Boot 3.3 `commission-service` | harness 104/104 | harness 104/104; `mvnw verify` 16/0 | none | **GREEN**. `call_service` is also where the red in rows 3-5 comes from. | [#2090](https://github.com/Cognition-Partner-Workshops/otterworks/pull/2090) |
| 3 | Rates group: `upsert_commission_rate`, `end_commission_rate`, `resolve_rate` (R1-R12, R22-R24) | PL/SQL | Java `rates/` | group 51/51, full 104/104 | group **45/51**, full **98/104** | 6 cases: ORA-00001 / ORA-01400 / ORA-01407 / ORA-02290 come back as ORA-20000 | **RED**. Cause: `call_service` re-raises only -20999..-20001 and wraps every other Oracle code as `ORA-20000: commission-service HTTP 422: <text>`. Not yet in the nightly gate. | [#2123](https://github.com/Cognition-Partner-Workshops/otterworks/pull/2123) |
| 4 | Splits group: `set_commission_splits` (R13-R21) | PL/SQL | Java `splits/` | group 31/31, full 104/104 | group **29/31**, full **102/104** | 2 cases: ORA-02290 and ORA-01400 come back as ORA-20000; R20, R21 and R37 FAIL | **RED**. Cause: the same `call_service` mapping. The rollback matches (no writes; policy 4 keeps splits 4,5,6). | [#2122](https://github.com/Cognition-Partner-Workshops/otterworks/pull/2122), [#2131](https://github.com/Cognition-Partner-Workshops/otterworks/issues/2131) |
| 5 | Calculation group: `calculate_policy_commission` (R25-R35) | PL/SQL | Java `calculation/` | group 22/22, full 104/104 | group **20/22**, full **102/104** | 2 cases: ORA-01843 and ORA-01400 come back as ORA-20000; R27, R34 and R35 FAIL | **RED**. Cause: the same `call_service` mapping. Every commission amount in the harness matches. Not yet in the nightly gate. | [#2124](https://github.com/Cognition-Partner-Workshops/otterworks/pull/2124) |
| 6 | Schema and data, `COMMISSION_PAY` + `COMMISSION_DW` (13 relations) | Oracle Free | PostgreSQL 16 | 382 rows | 382 rows | +0 rows, every row and column identical | **MATCH** 13/13 | [#2097](https://github.com/Cognition-Partner-Workshops/otterworks/pull/2097) |
| 7 | Commission ledger, total `commission_amt` | Oracle | PostgreSQL 16 | 1,418.50 (97 rows) | 1,418.50 (97 rows) | +0.00 | **MATCH** | [#2097](https://github.com/Cognition-Partner-Workshops/otterworks/pull/2097) |
| 8 | `MV_AGENT_COMMISSION_SUMMARY` (warehouse rollup) | Oracle MV | PostgreSQL 16 materialized view | 1,418.50 (86 rows) | 1,418.50 (86 rows) | +0.00 | **MATCH** 86/86 | [#2097](https://github.com/Cognition-Partner-Workshops/otterworks/pull/2097) |
| 9 | Commission arithmetic at the half cent (D4) | Oracle NUMBER | `commission_pay.commission_amount()` | 1,600,080 grid amounts | 1,600,080 identical | 0 differ | **MATCH**. D4 option A was taken in #2097. Finance has not confirmed it (see Decisions). | [#2097](https://github.com/Cognition-Partner-Workshops/otterworks/pull/2097) |
| 10 | Constraint probes P1-P8 | Oracle | PostgreSQL 16 | 8 probes | 5 same outcome; P1, P2 and P8 differ | 3 differ | **ACCEPTED** by recorded decisions D1 (identity NULL), D2 (varchar counts characters) and D5 (bigint ids). P7b (native numeric) is INFO only. | [#2097](https://github.com/Cognition-Partner-Workshops/otterworks/pull/2097) |
| 11 | Warehouse ETL `DW_ETL_PKG` + MV | Oracle PL/SQL | dbt-postgres on PostgreSQL 16 | baseline pinned: 115 ledger rows, 115 fact rows, 107 MV rows, **2,328.31**; regenerated byte-identical | **no dbt models yet**. `dbt build` runs 0 nodes. | not measured | **NOT DONE**. There is no month-end dbt parity yet. #2115 CI is red on `deps` (legacy-portal `AnnouncementServiceTest` sees an extra "Release" row; test-order dependent, unrelated to this work). #2132 CI was pending when this report was written. | [#2115](https://github.com/Cognition-Partner-Workshops/otterworks/pull/2115), [#2132](https://github.com/Cognition-Partner-Workshops/otterworks/pull/2132) |
| 12 | Commission statement screen, AG-100 + AG-101, 2026-03 | Oracle, rows by PL/SQL | Java `commission-service` on PostgreSQL 16, rows recalculated by Java | 64.25 + 38.75 | 64.25 + 38.75 | 0.00 | **MATCH**. Scope is one period, 2026-03, policies 1-4 only. | [#2130](https://github.com/Cognition-Partner-Workshops/otterworks/pull/2130) |
| 13 | Rate-history screen, AG-100 + AG-101 | Oracle `commission_rates` | PostgreSQL 16 `commission_rates` (migrated) | 5 + 4 rows | 5 + 4 rows | none | **MATCH** | [#2130](https://github.com/Cognition-Partner-Workshops/otterworks/pull/2130) |
| 14 | Nightly parity gate, first run | n/a | automation, `make insurance-characterize` + `insurance-pg-reconcile` | 228 units | 222 MATCH, 3 ACCEPTED, **3 MISMATCH** | R20, R21, R37 | **RED**. Cause: the shared `call_service` mapping in #2122 (`03_commission_pkg.sql` lines 152-156 at `83fae374`). | [#2131](https://github.com/Cognition-Partner-Workshops/otterworks/issues/2131) |
| | **Totals** | | | 14 units | | | **7 MATCH or GREEN** (1, 2, 6, 7, 8, 12, 13), **1 MATCH with a decision open** (9), **1 ACCEPTED** (10), **4 RED** (3, 4, 5, 14), **1 NOT DONE** (11) | |

Rows 3, 4, 5 and 14 have one cause between them. No commission amount differs in any of them: what changes is the error code a PL/SQL caller sees when a database constraint fires inside the service.

## Parity numbers, quoted from the PRs

### The number finance will argue about: monthly ledger per agent against the warehouse rollup

The ledger figures come from the per-agent and per-period tables in #2097 and #2131. The rollup is the sum of that agent and period's `MV_AGENT_COMMISSION_SUMMARY` rows (one per line of business) in the same reports.

| Agent, period | Old ledger (Oracle) | Old rollup (Oracle MV) | New ledger (PostgreSQL 16) | New rollup (PostgreSQL 16 MV) | Difference | Verdict | Who computed the new ledger |
|---|---:|---:|---:|---:|---:|---|---|
| AG-101, 2025-06 | 36.95 (3 rows) | 36.95 = AUTO 19.20 + HOME 8.00 + LIFE 9.75 | 36.95 (3 rows) | 36.95 | 0.00 | **MATCH** | Copied from Oracle by `migrate.py`. Java has not recalculated 2025-06. |
| AG-101, 2026-03 | 38.75 (3 rows) | 38.75 = AUTO 21.00 + HOME 8.00 + LIFE 9.75 | 38.75 (3 rows) | 38.75 (measured before the Java run in #2130) | 0.00 | **MATCH** | The Java calculation group on PostgreSQL 16, in #2130 (actor `commission-service`) |
| AG-100, all periods | 773.50 (38 rows) | 773.50 | 773.50 | 773.50 | 0.00 | **MATCH** | copy |
| AG-101, all periods | 437.60 (36 rows) | 437.60 | 437.60 | 437.60 | 0.00 | **MATCH** | copy |
| AG-102, all periods | 207.40 (23 rows) | 207.40 | 207.40 | 207.40 | 0.00 | **MATCH** | copy |
| **Total** | **1,418.50** | **1,418.50** | **1,418.50** | **1,418.50** | **0.00** | **39/39 agent-periods, 86/86 MV rows MATCH** | |

The rollup column is the PostgreSQL materialized view from #2097, not dbt. No dbt model exists yet (row 11). The dbt port will be measured against the month-end baseline in #2115, which is a different, larger scenario. In that baseline AG-101 2025-06 is **70.95** in both the ledger and the MV (AUTO 19.20, COMMERCIAL 25.00, HOME 8.00, LIFE 18.75), and the full year is **2,328.31**. This report added those two AG-101 figures up from `dbt/commission_dw/golden/commission_ledger.csv` and `mv_agent_commission_summary.csv` at `475fcd7ef`. The dbt side of that comparison does not exist yet.

### Harness (R1-R38), per group

| Group | PR | Group cases, old | Group cases, new | Full harness, new | Red cases (code: old -> new) | Verdict |
|---|---|---:|---:|---:|---|---|
| none (skeleton) | #2090 | 104/104 | 104/104 | 104/104 | none | GREEN |
| rates | #2123 | 51/51 | 45/51 | 98/104 | `test_backdated_rate_collides_with_open_rate` ORA-00001 -> 20000; `test_sub_cent_rate_passes_guard_then_fails_constraint_and_rolls_back` ORA-02290 -> 20000; `test_null_actor_fails_after_supersede_and_rolls_back` ORA-01400 -> 20000; `test_null_actor_on_same_day_correction_rolls_back` ORA-01407 -> 20000; `test_end_before_start_violates_check_and_rolls_back` ORA-02290 -> 20000; `test_end_null_actor_fails_at_audit_and_rolls_back` ORA-01400 -> 20000 | RED (call_service) |
| splits | #2122 | 31/31 | 29/31 | 102/104 | `test_rollback_after_delete_restores_previous_allocation` ORA-02290 -> 20000; `test_null_actor_fails_at_audit_and_rolls_back` ORA-01400 -> 20000 | RED (call_service) |
| calculation | #2124 | 22/22 | 20/22 | 102/104 | `test_invalid_period_rejected` ORA-01843 -> 20000; `test_null_actor_fails_at_audit_and_rolls_back` ORA-01400 -> 20000 | RED (call_service) |
| **Total** | | **104/104** | **94/104** if the 10 reds simply add up | not run with all three groups together | 10 cases, one cause | **RED** |

The 94/104 figure is inferred: each PR was measured on its own against the skeleton, and nobody has run the three groups together.

### Nightly gate, first run ([#2131](https://github.com/Cognition-Partner-Workshops/otterworks/issues/2131))

| Leg | Units | MATCH | ACCEPTED | MISMATCH | Cause if red |
|---|---:|---:|---:|---:|---|
| Data (Oracle Free vs PostgreSQL 16) | 190 | 187 | 3 | 0 | |
| Rules (R1-R38, harness against the delegated package) | 38 | 35 | 0 | 3 | R20, R21 and R37: `call_service` wraps ORA-02290 / ORA-01400 as ORA-20000 |
| **Gate** | **228** | **222** | **3** | **3** | |

The gate tests #2122 only. #2123 and #2124 are "not yet in the gate", and they carry the same mapping, so the gate will show more red once they are added.

### Half-cent rounding grid (D4, #2097)

Grid: premium 10,000.00 to 10,200.00 in one-cent steps × 8 rates × 10 splits = 1,600,080 amounts. Each arithmetic is compared with Oracle `COMMISSION_PKG`.

| Arithmetic | Cents that differ from Oracle | Status |
|---|---:|---|
| A: `commission_pay.commission_amount()`, Oracle NUMBER rule | 0 of 1,600,080 | used; the reconciliation fails on any difference |
| PostgreSQL native `numeric`, same formula | 96, one cent each (10,003.00 / 10 / 60: Oracle 50.01, native 50.02) | not used |
| B: exact `ROUND(premium × rate × split / 120000, 2)` half up | 107, one cent each and always up (10,000.00 / 7.33 / 30: Oracle 18.32, B 18.33) | not chosen |
| Stored ledger rows recomputed with A | 97 of 97 equal | MATCH |

### Screens (#2130), 2026-03

| Agent | Unit | Oracle PL/SQL | Java on PostgreSQL 16 | Difference | Verdict |
|---|---|---:|---:|---:|---|
| AG-100 | POL-2025-0001 / 0002 / 0004 | 14.25 / 12.00 / 38.00 | 14.25 / 12.00 / 38.00 | 0.00 | identical |
| AG-100 | Period total | 64.25 | 64.25 | 0.00 | identical |
| AG-101 | POL-2025-0002 / 0003 / 0004 | 8.00 / 9.75 / 21.00 | 8.00 / 9.75 / 21.00 | 0.00 | identical |
| AG-101 | Period total | 38.75 | 38.75 | 0.00 | identical |
| AG-100 / AG-101 | Rate history rows | 5 / 4 | 5 / 4 | none | identical |
| all | `commission_ledger` after the Java run (rows / sum) | 97 / 1,418.50 | 97 / 1,418.50 | 0.00 | identical |

## Decisions open (carrier standard rule 5: options with a recommendation, a human decides)

| # | Divergence | Options | Recommendation | Owner |
|---|---|---|---|---|
| D4 | Half-cent rounding at cutover | **A** keep Oracle's NUMBER arithmetic (0 of 1.6M differ). **B** exact half-up (107 of 1.6M differ, +0.01 each, so a re-run of a paid period can change a booked amount). | **A** for the cutover. If finance wants B, make it a separately dated policy change with its own cutover entry. | finance lead |
| ORA-20000 | `call_service` changes the SQLCODE of database errors raised inside the service (rows 3-5, 14) | 1 accept and document, then re-pin the 10 goldens in a reviewed PR; 2 `PRAGMA EXCEPTION_INIT` re-raise (the code matches, the message loses the constraint or column name); 3 service decides and the package writes (full parity, changes the #2090 transaction contract); 4 validate first (not parity). | The PRs disagree. #2122 and #2123 say 1. #2124 says 2, and accepting the lost column name. #2131 says 1 if no caller anywhere keys on ORA-00001/01400/01407/01843/02290 (none in this repo does), otherwise 3. **This report recommends #2131's position**: confirm callers outside the repo first, then choose 1 or 3 once for all three groups. | Commission Pay owners |
| D-1 | Split inputs with more than 2 dp are stored as totals of 99.99 or 100.01 | (a) reproduce; (b) reject at the edge; (c) round, then require 100.00 | (b), from #2087 | finance lead |
| D-2 | Penny drift across split rows (2.02 vs 2.01) | (a) per-row rounding (legacy); (b) largest remainder | (a) for parity, (b) as a later, announced change; from #2087 | finance lead |
| D-3 | Same-day amend of a referenced rate | (a) update in place; (b) new version row | (b), from #2087 | finance lead |

## Not done yet

- **dbt warehouse**: #2132 has the project and the PostgreSQL 16 fixture but no models. The month-end parity against the #2115 baseline (2,328.31 over 115 ledger rows, 107 MV rows) has not been run.
- **Java arithmetic on the 1.6M grid**: #2097 names its grid as the acceptance test for the Java port. That grid has not been run against `CommissionCalculator` (#2124). The calculator rounds at a fixed `MathContext(40, HALF_UP)` per step. The #2097 rule is 39 or 40 digits, depending on the leading base-100 digit, and #2097 measured that a fixed 38 digits is wrong on 105 amounts. Whether a fixed 40 gives any differences has not been measured. The Java run matched all 97 stored ledger rows in #2130.
- **Java has recalculated one period only**: #2130 recalculated policies 1-4 for 2026-03. Every other ledger row on PostgreSQL is the copy from Oracle.
- **ORA-20000 decision** (above). It applies to all three rule groups, and the gate stays red until it is recorded.
- **#2123 and #2124 are not in the nightly gate.**
- **Legacy defects that the target reproduces on purpose**: the second rate supersede still fails with ORA-00001 (R-5, `ux_rates_open`), and the ETL `MERGE` never deletes, so a re-split leaves fact 100.02 against ledger 92.02 (R-6, #2087 probe P16). The dbt plan in #2087 moves to `delete+insert`, which fixes R-6 but stops matching Oracle on a re-split. That needs its own sign-off when the dbt models land.
- **Known flake**: the legacy OLAP test E4 sometimes fails with ORA-04020 (#2097). The CI workflow can go red for that reason alone.
- Nothing has merged, and Oracle has not been retired.

## Housekeeping

This report was written from PR bodies, the PR branches and issue #2131. No Oracle, PostgreSQL or service container was started, so none is left running. The four screenshots in `screens/` are the AG-101 pairs that the #2130 session attached, cropped to the page.
