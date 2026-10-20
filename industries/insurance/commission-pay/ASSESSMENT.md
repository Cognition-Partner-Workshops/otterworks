# Commission Pay: modernization assessment and wave plan

Scope: the Oracle fixture under `services/industry-solutions/insurance/` on `demo-insurance`
(schema `COMMISSION_PAY` with `COMMISSION_PKG`, schema `COMMISSION_DW` with `DW_ETL_PKG` and
`MV_AGENT_COMMISSION_SUMMARY`, the suites under `db/tests/`). Measured against the
organization skill `carrier-modernization-standard`.

> **Status: one decision open.** The warehouse target (§7, question Q1) decides what Wave 1
> contains and what Oracle footprint the renewal has to cover. Wave 1 and the renewal line are
> written both ways and marked OPEN until we hear back. Nothing else in the plan depends on it.

Line references are `file:line` relative to `services/industry-solutions/insurance/db/` unless
another path is given, at the `demo-insurance` commit this branch was cut from.

## 1. How this was assessed

1. **DeepWiki on the repository** (three questions: the fixture and its callers; its history and
   design intent; the "Industry Solutions: Insurance Oracle Estate" page's operational notes).
2. **Repository skills**: `.agents/skills/stored-procs-to-microservices` (the procs harness
   pattern: rule ledger, recorded transcripts, rules gate, replay parity), `oracle-billing-estate`
   (how to drive an Oracle Free container with no host `sqlplus`), and the org skills
   `carrier-modernization-standard` and `modernization-target-standard`.
3. **The SQL**, every file under `db/`, plus `Makefile:41-56` and `docker-compose.insurance.yml`.
4. **The running system**: `make insurance-up NS=assess` (Oracle AI Database 26ai Free 23.26.3.0.0,
   pulled from `:latest`), both suites, then the risk probes committed alongside this file
   (`probes/oltp_risk_probes.sql`, `probes/olap_risk_probes.sql`) on a fresh volume.
5. **Open and merged PRs** touching the same estate (#836, #1282, #1413, #1414).

### What DeepWiki told us that the code alone would not

- **The house pattern for this kind of work already exists.** DeepWiki tied the fixture to the
  `procs/` harness and the `stored-procs-to-microservices` playbook (rule ledger with approved
  decisions, immutable recorded transcripts, `rules_gate`, replay parity with exit codes). Nothing in
  `services/industry-solutions/insurance/` mentions it. The plan below reuses that shape instead
  of inventing a new parity harness.
- **There is no CI caller.** It stated that no workflow runs `insurance-test`; `grep` over
  `.github/` on `demo-insurance` confirms it. The suites only run when someone runs them by hand,
  so "green" today means "green the last time someone looked".
- **The ordering dependency between the suites is intentional**, and the healthcheck/skip guard both
  key off `FIXTURE_META`. Both are visible in the code once you know to look; DeepWiki surfaced them
  up front.

Where DeepWiki was **wrong**, checked against the code:

- It said `COMMISSION_DW` gets `SELECT` on four named tables. The actual grant is schema-wide:
  `GRANT SELECT ANY TABLE ON SCHEMA commission_pay TO commission_dw` (`setup/01_users.sql:16`), so
  the warehouse can also read `rate_audit_log`, `commission_rates` and `commission_splits`.
- It said the MV is `REFRESH FORCE ON DEMAND`. It is `REFRESH COMPLETE ON DEMAND` (`olap/02_etl_pkg.sql:100`).
- It found no prior extraction attempts. There are two, found through GitHub, not DeepWiki:
  PR #1282 (open, against `main`) moves the rules into a Python/FastAPI `commission-service` and turns
  `COMMISSION_PKG` into a `UTL_HTTP` delegate; PRs #1413/#1414 scope `COMMISSION_DW` to **Databricks**
  on a `tp-run/...` branch. Both conflict with the carrier standard (§6).

## 2. Baseline (pinned before anything moves)

| Suite | Checks | Result |
|---|---:|---|
| `tests/run_tests.sql` (OLTP, as `COMMISSION_PAY`), fresh volume | 17 | OLTP TESTS: ALL PASS |
| `tests/run_olap_tests.sql` (OLAP, as `COMMISSION_DW`), fresh volume | 5 | OLAP TESTS: ALL PASS |
| Both suites again after the risk probes, same volume | 22 | OLTP ALL PASS; **E2 FAIL** `fact=100.02 ledger=92.02` (R-6 below) |

The post-probe E2 failure comes from the probes' deliberate re-split, not from a source defect
introduced here. It shows that the existing suite catches R-6 only when the data happens to
exercise it. Wall-clock time was not captured, so there is no runtime baseline yet (§8).

Objects actually present (from `user_objects`): `COMMISSION_PAY` has 1 package (+body), 2 types,
8 tables (7 business + `FIXTURE_META`), 3 named indexes. `COMMISSION_DW` has 1 package (+body),
4 tables, 1 materialized view. **There are no plain views and no triggers in either schema.**

## 3. Units, callers and modernization pattern

Callers are everything in the repository that invokes, reads or deploys the unit. "Deploy" means
`startup/00_init.sh` running the creating script. No application service, Helm chart or CI job calls
any of these units today.

| # | Unit | Kind | Callers | Pattern | Reason |
|---|---|---|---|---|---|
| U1 | `COMMISSION_PKG` (spec `oltp/03_commission_pkg.sql:14-82`, body `84-348`) | PL/SQL package | `tests/run_tests.sql`; deploy `startup/00_init.sh:64`; PR #1282 rewrites the body | **Extract to service** | Every business rule is here. Target is `commission-service` on Java 21 / Spring Boot 3.3. Its ORA-20001..20008 contract becomes the service's error contract. |
| U2 | `upsert_commission_rate` (`03_commission_pkg.sql:122-176`) | procedure | `run_tests.sql` T1, T1b, T2, T3 | **Extract to service** | Effective-dating rules. Its history defect (R-5) must be decided before translating. |
| U3 | `end_commission_rate` (`:178-201`) | procedure | **none**: no test, no caller | **Extract to service** | Small, but it has no test today. Pin it first (Wave 1). |
| U4 | `set_commission_splits` (`:203-257`) | procedure | `run_tests.sql` T4, T5, T6, T11 | **Extract to service** | Hosts the exact-100.00 rule and the precision defect (R-3). |
| U5 | `resolve_rate` (`:259-283`) | function | `run_tests.sql` T7, T7b; `calculate_policy_commission:317` | **Extract to service** | Pure read with no side effects, so it is the safest first slice to run in shadow. |
| U6 | `calculate_policy_commission` (`:285-345`) | procedure | `run_tests.sql` T8-T10 | **Extract to service** | The money path. Rounding, idempotency and the audit row all live here. |
| U7 | `log_action` (`:86-97`) | private procedure | U2, U3, U4, U6 | **Rewrite** | Becomes an audit write in the service's own transaction, with before and after values and the authenticated principal instead of the free-text `p_actor`. |
| U8 | `assert_product`, `assert_active_agent` (`:99-120`) | private procedures | U2, U4 | **Translate** | One-to-one guard methods. |
| U9 | `split_alloc_t`, `split_alloc_tab` (`:5-12`) | object types | U4 signature; `run_tests.sql` | **Retire** | They become a request DTO with `BigDecimal` at scale 2. The unscaled `NUMBER` attribute causes R-3. |
| U10 | Exceptions `e_invalid_rate`..`e_policy_not_active` (`:16-32`) | package exceptions | `run_tests.sql` handlers | **Translate** | They become typed domain exceptions that map 1:1 to the same codes, so the parity harness can compare verdicts. |
| U11 | `agents` (`oltp/01_tables.sql:6-14`) | table | U2, U4 (status); `DW_ETL_PKG:22`; seed | **Translate** | PostgreSQL 16 table with the same checks. Agent master data is probably owned upstream (§7 Q-later). |
| U12 | `products` (`:16-21`) | table | U2; `DW_ETL_PKG:34`; seed | **Translate** | Reference data. |
| U13 | `commission_rates` + `ux_rates_open` (`:26-43`) | table + function-based unique index | U2, U3, U5, U6; ledger FK | **Translate** (index **rewrite**) | The index needs rewriting. It is meant to allow one open rate per scope, but it also allows only one *closed* rate (R-5). In PostgreSQL this becomes a partial unique index `WHERE effective_to IS NULL`, plus an exclusion constraint on the date range. |
| U14 | `policies` (`:45-54`) | table | U4, U6; `DW_ETL_PKG:67` | **Translate** | Probably policy-admin owned. Commission Pay should read it, not own it. |
| U15 | `commission_splits` (`:59-66`) | table | U4, U6 | **Translate** | `NUMERIC(5,2)` with a deferred constraint, or a service-level check, that the stored total = 100.00. |
| U16 | `commission_ledger` (`:70-81`) | table | U6 (delete+insert); `DW_ETL_PKG:45,66`; `run_olap_tests.sql` E2 | **Translate** | The payout record. Parity is to the cent, per row. |
| U17 | `rate_audit_log` (`:84-93`) | table | U7; `run_tests.sql` T12 | **Translate** | Append-only. Add `before`, `after` and `request_id`. |
| U18 | `fixture_meta` (`startup/00_init.sh:93-99`) | table | compose healthcheck; `00_init.sh:21` skip guard | **Keep** (fixture only) | Init marker. Not business data. |
| U19 | `DW_ETL_PKG.load_commission_facts` (`olap/02_etl_pkg.sql:5-95`) | PL/SQL package | `run_olap_tests.sql` E1, E3; deploy `00_init.sh:66` | **Translate** (Q1 decides the target) | Four MERGEs map directly to dbt-postgres incremental models (carrier standard). Fix the missing delete path (R-6) at the same time. |
| U20 | `dim_agent`, `dim_product`, `dim_period`, `fact_commission` (`olap/01_star_schema.sql:5-39`) | tables | U19; MV; `run_olap_tests.sql` | **Translate** | dbt models. `dim_agent` is SCD-1 today (status overwritten), so history is lost. |
| U21 | `MV_AGENT_COMMISSION_SUMMARY` (`olap/02_etl_pkg.sql:98-112`) | materialized view | `run_olap_tests.sql` E4 only | **Rewrite** as a dbt model | No refresh is scheduled anywhere, and the ETL does not refresh it (R-7). As a dbt model it is rebuilt in the same run as the fact table. |
| U22 | `tests/run_tests.sql` | test suite (17 checks) | `Makefile:55` (`insurance-test`) | **Keep** during Waves 1-2, then **retire** | It is the legacy oracle for the strangler. It must stay green against the delegating package. Retire it with Oracle. |
| U23 | `tests/run_olap_tests.sql` | test suite (5 checks) | `Makefile:56`; depends on U22 running first | **Keep**, then **translate** to dbt tests | E2 (fact reconciles to ledger) becomes a dbt test that runs on every load. |
| U24 | `setup/01_users.sql`, `startup/00_init.sh`, `oltp/02_seed.sql` | fixture plumbing | compose (`docker-compose.insurance.yml:15-16`) | **Keep** (fixture), **retire** at cutover | The seed becomes the PostgreSQL fixture seed for the target suite. |

## 4. Business rules

Numbered for the rule ledger the target will carry (`procs/rules/<module>.rules.yaml` shape).
"Test" names the existing case that covers the rule. "none" means the rule is pinned only by the
probes in this PR, or not pinned at all.

| # | Rule | Implemented at | Test |
|---|---|---|---|
| BR-1 | A commission rate must be non-NULL and in (0, 50], else ORA-20001 | `oltp/03_commission_pkg.sql:131-134`; also `oltp/01_tables.sql:31` | T2 (only >50) |
| BR-2 | The product must exist, else ORA-20004 | `03_commission_pkg.sql:99-106,135` | none |
| BR-3 | An agent-specific rate needs an existing agent (ORA-20002) whose status is ACTIVE (ORA-20003). Product defaults (agent NULL) skip the check | `:108-120,136-138` | T3 (SUSPENDED only) |
| BR-4 | Same-day correction: an open rate that starts on the same `effective_from` is amended in place, keeping the same `rate_id`, and `created_by` is overwritten | `:142-149` | T1b |
| BR-5 | Supersede: the open rate for the scope that started earlier is closed at `effective_from - 1`, then a new open row is inserted. History is never deleted | `:154-165` | T1 |
| BR-6 | Only one open rate per (product, agent-or-default) scope | `oltp/01_tables.sql:39-43` | indirectly T1b |
| BR-7 | `end_commission_rate` closes the open rate for a scope at the given date. With no open rate it raises ORA-20007. It does not validate the product or the agent | `03_commission_pkg.sql:185-193` | none |
| BR-8 | Splits: the policy must exist (ORA-20005). Policy status is **not** checked, so lapsed policies can be re-split | `:212-217` | none |
| BR-9 | Splits: at least one allocation (ORA-20006) | `:219-221` | T11 |
| BR-10 | Splits: no duplicate agent (ORA-20006). A NULL agent also reports as "Duplicate" | `:223-226` | T5 |
| BR-11 | Splits: each percentage in (0, 100] (ORA-20006); every agent ACTIVE (ORA-20003) | `:228-235`; `01_tables.sql:64` | none for range; none for inactive split agent |
| BR-12 | Splits: percentages must total exactly 100 (ORA-20006). The comparison is on the **unscaled** input | `:236,239-242` | T4, T6 |
| BR-13 | Splits replace the policy's whole allocation atomically (delete then insert) | `:244-248` | T6 |
| BR-14 | Rate resolution: an agent-specific rate beats the product default. Both ends of the effective window are inclusive. The latest `effective_from` wins. No rate gives ORA-20007 | `:267-282` (precedence `:274`) | T7, T7b |
| BR-15 | Calculation needs an existing policy (ORA-20005) whose status is IN_FORCE (ORA-20008) | `:297-306` | T10 (LAPSED) |
| BR-16 | The rate used for a period is the one in force on the **last day** of the month, applied to the whole month (no proration) | `:308,317` | none (probe P9) |
| BR-17 | Commission per agent row = `ROUND(annual_premium / 12 * rate_pct / 100 * split_pct / 100, 2)`. Oracle `ROUND` is half away from zero, so HALF_UP for these always-positive amounts. Intermediates are not rounded | `:320-322` | T8a-c (no half-cent case; probe P6) |
| BR-18 | Rows are written in `split_pct DESC, agent_id` order. There is no remainder allocation, so agent rows can sum to a cent more or less than the policy-level amount | `:313-316` | none (probe P7) |
| BR-19 | Re-running a (policy, period) deletes and rewrites its ledger rows (idempotent) | `:310-311`; `01_tables.sql:80` | T9 |
| BR-20 | A policy with no split rows cannot be calculated (ORA-20006). The DELETE is rolled back with it | `:333-336` | **none**: T11 is named for this but tests BR-9 |
| BR-21 | Agent status is **not** re-checked at calculation. An agent suspended after the split was set is still paid | absence at `:313-329` | none (probe P10) |
| BR-22 | The calculation does not check `issued_date`, so commission can be computed for months before issue | absence at `:297-308` | none (probe P4) |
| BR-23 | The ledger stores the **annual** premium in `base_premium`, not the monthly base | `:329` | none |
| BR-24 | Every successful management call writes one audit row: RATE_UPSERT, RATE_END, SPLIT_SET or COMMISSION_CALC. A rejected call writes none | `:168-170,194-195,250-251,338-339` | T12 (>= 4 rows only) |
| BR-25 | Every public procedure ends its own transaction: COMMIT on success, and ROLLBACK plus re-raise on any error | `:171-175,196-200,252-256,340-344` | none (probe P11) |
| BR-26 | ETL: dimensions are fully MERGEd from OLTP (SCD-1), `dim_period` is insert-only, and facts are MERGEd on (policy, agent_key, period_key). A NULL period means all periods | `olap/02_etl_pkg.sql:22-84` | E1, E3 |
| BR-27 | ETL never deletes fact rows | absence in `olap/02_etl_pkg.sql:58-84` | none (probe P16) |
| BR-28 | `o_rows_merged` reports only the fact MERGE's row count | `olap/02_etl_pkg.sql:86` | E1 |
| BR-29 | The summary MV is a complete refresh on demand. Nothing in the ETL refreshes it | `olap/02_etl_pkg.sql:98-112` | E4 (the test refreshes it itself) |

## 5. Risks

Every row was observed on the running fixture (`probes/*.sql`; output in the PR body) unless marked
*reading*.

| # | Area | Finding | Evidence | Consequence for the plan |
|---|---|---|---|---|
| R-1 | Rounding | Oracle `ROUND` gives 1.005 → **1.01** per agent. Java `BigDecimal` with `HALF_EVEN`, or a .NET `Math.Round` default, gives 1.00 | P6: `241.20/12*10%*50%` stored `1.01/1.01` | The target must name `RoundingMode.HALF_UP` at the one call site (carrier standard rule 3). Add a half-cent case to the pinned suite. Today's T8 has none. |
| R-2 | Rounding (allocation) | Rounding per agent row with no remainder allocation lets the agent rows drift from the policy amount | P7: rows sum **2.02** vs policy-level **2.01** | Finance will argue about this cent. Parity is per row, which reproduces the drift. Changing it is a human decision (§7 D-2). |
| R-3 | Exact 100.00 split totals | The total check runs on the unscaled `split_alloc_t.split_pct NUMBER`. The column is `NUMBER(5,2)`, which rounds on insert. Allocations that "total 100" are stored as **99.99** or **100.01** | P1: 33.333+33.333+33.334 stored total **99.99**; P2: 33.335+33.335+33.33 stored total **100.01** | Any commission calculated from such a split pays 0.01% too little or too much. The target must reject input with more than 2 dp, or round before checking. That is a divergence from legacy, so it is a human decision (§7 D-1). Scan production splits for `SUM(split_pct) <> 100` before Wave 2. |
| R-4 | Effective dating | The month-end rate applies to the whole month, with no proration | P9: a 14% rate from 2026-03-15 paid the full March | Pin it as-is. Confirm with finance that this is policy, not accident. |
| R-5 | Effective dating (history) | `ux_rates_open` keys closed rows as `(product, NVL(agent,-1), NULL)`. That key is still unique, so each scope can hold **one** closed rate. The second supersede of any scope fails with ORA-00001. Back-dating fails the same way, rather than with a business error | P15: AUTO-STD default with 1 closed row, next supersede → `ORA-00001 UX_RATES_OPEN`; P5 back-date → `ORA-00001` | A real production estate cannot have run like this for long. Either production has a different index, or rate changes are worked around (deleted, or edited in place via BR-4). **Compare production DDL before Wave 2.** The target uses a partial unique index. Its parity harness has to treat ORA-00001 as a recorded legacy verdict, not crash on it. |
| R-6 | Idempotent re-runs | The OLTP re-run is idempotent (T9). The ETL is not when a re-run removes rows: MERGE never deletes, so a split change that drops an agent leaves an orphan fact row | P16: fact **100.02** vs ledger **92.02** (orphan 8.00 for policy 2 / agent 2). The existing E2 check then FAILS | The warehouse can over-report commission after any re-split. The target ETL loads (policy, period) slices as replace-partition, or uses dbt `delete+insert`. Add a reconciliation check per period on every load. |
| R-7 | Idempotent re-runs (MV) | The MV is stale until someone refreshes it, and nothing schedules a refresh | P17: fact 100.02, MV 92.02 after ETL | Reports can disagree with the fact table. Find out who refreshes it in production (§7 Q1 covers consumers). |
| R-8 | Same-day amend rewrites history | BR-4 updates `rate_pct` on a `rate_id` that ledger rows already reference. The ledger is not recalculated, so the stored amount no longer matches the stored rate | P8: ledger 15.00 at rate_id 3, which now says 12% | The target makes rates immutable once referenced: insert a new version instead of updating. That is a divergence, so it needs a decision (D-3). Parity compares ledger rows, not rate rows. |
| R-9 | Audit rows | Rejected calls leave no audit row. The amend path records only the new pct, not the old. `actor` is a caller-supplied string | P12: audit 19/19 around a rejected upsert; *reading* `:168-170` | The target writes audit rows in the same transaction (keeping BR-24 parity) and, separately, logs rejected attempts. That is additive, so no parity break. Count audit rows by action at every parity run. |
| R-10 | Transaction boundaries | Every procedure COMMITs or ROLLBACKs the **caller's** transaction too. A caller cannot group two calls atomically. A failed call silently discards the caller's earlier uncommitted work | P11a: caller row gone after a failed call; P11b: caller row survives the caller's own ROLLBACK | The service owns one transaction per command. During the strangler period, delegating PL/SQL must keep this behaviour or the legacy suite changes meaning. PR #1282's `UTL_HTTP` delegate also commits in the service, outside Oracle's transaction, so the two can disagree under failure. |
| R-11 | Period key | `period_month` is a free `VARCHAR2(7)`. `'2025-6'` is accepted and becomes a separate period | P3 | Validate `YYYY-MM` at the service edge. Scan production for non-canonical keys. |
| R-12 | Eligibility gaps | Suspended agents are still paid on existing splits (P10). Months before `issued_date` are calculable (P4). Lapsed policies can be re-split (BR-8) | P4, P10 | Pin as-is. These are product decisions, not migration decisions. List them in the ledger with `question`/`answer`. |
| R-13 | Grants | The DW has `SELECT ANY TABLE ON SCHEMA commission_pay`, which includes audit and rates | `setup/01_users.sql:16` | The target gives the warehouse a read-only role on the ledger and dimensions only. |
| R-14 | Reproducibility | Image `database/free:latest` is unpinned (today 23.26.3.0.0). No CI runs the suites | `docker-compose.insurance.yml:9`; no `.github` match | Pin the image digest and add the suites to CI in Wave 1. Otherwise "before" numbers can move under us. |

## 6. Conflicts with work already in flight

| PR | What it does | Conflict with `carrier-modernization-standard` | Recommendation |
|---|---|---|---|
| #1282 (open, base `main`) | Rules moved into Python 3.12/FastAPI `commission-service`; `COMMISSION_PKG` becomes a `UTL_HTTP` delegate; `RULE_LEDGER.md` R1-R38 | Rule 2: the target is Java 21 / Spring Boot 3.3, not Python. Rule 6: insurance-only source goes to `demo-insurance`, not `main`. Rule 1: no pinned golden baseline before target code. R-10: the transaction split across HTTP | Reuse its rule ledger (R1-R38, written against the same package source) as input to Wave 1. Do not merge the service. Close or retarget it after you decide. |
| #1413 / #1414 (base `tp-run/databricks-...`) | `COMMISSION_DW` → Databricks lakehouse, setup docs approved at STOP A | Rule 2 names dbt-postgres as the warehouse target | This is Q1 below. |

The org skill `modernization-target-standard` says PostgreSQL **15**. The carrier standard, which is
specific to this estate, says **16**. This plan follows the carrier standard.

## 7. Wave plan

Common to every wave: work happens on a `demo-insurance` branch, the PR stays open with its evidence
in the body, and parity uses the one report shape (one row per unit, with source, target,
difference, verdict, and totals). Parity is to the cent with no tolerance band. A red row names its
cause.

> **Q1 (open, waiting on you):** Is the target for `COMMISSION_DW` still **dbt-postgres on
> PostgreSQL 16**, as `carrier-modernization-standard` names it, or **Databricks**, which PRs
> #1413/#1414 already scoped and approved for setup? With dbt-postgres, the warehouse moves first
> and Oracle leaves entirely in this plan. With Databricks, this plan covers `COMMISSION_PAY`
> only, Wave 1 changes, and the renewal must keep `COMMISSION_DW` licensed on the Databricks
> track's timeline.

### Wave 1: Pin the legacy and prove the harness (no money moves)  — **OPEN on Q1**

Always in Wave 1, whatever the answer:

- Pin the image digest. Add `insurance-up` / `insurance-test` / `insurance-down` to CI on `demo-insurance`.
- Extend the legacy suites into a characterization baseline recorded from the running fixture, in the
  `procs/` transcript shape: every BR above, including the uncovered ones (BR-2, 7, 8, 11, 16, 18,
  20-23), the half-cent case (R-1), the split precision cases (R-3), the second supersede (R-5), and
  the re-split ETL orphan (R-6). Commit the transcripts and source fingerprints.
- Write a rule ledger for `COMMISSION_PKG` + `DW_ETL_PKG`, seeded from #1282's R1-R38. Divergence
  decisions D-1..D-3 go in as `question` entries with no `answer` until finance answers.
- Scan production (read-only) for R-3, R-5 and R-11 evidence: split totals ≠ 100.00, more than one
  closed rate per scope, and non-canonical period keys.

Then one of:

- **If Q1 = dbt-postgres (carrier standard):** move the warehouse first. `DW_ETL_PKG` + star schema + MV
  become dbt-postgres models on PostgreSQL 16, fed nightly from a read-only extract of
  `commission_ledger`, `agents`, `products` and `policies`. R-6 is fixed with `delete+insert`
  per period, the MV becomes a model, and reconciliation runs as a dbt test.
  **Proves:** the parity harness, reporting to the cent, and that the team can run the target stack in
  production with nothing at stake for payouts.
- **If Q1 = Databricks (PRs #1413/#1414):** the warehouse leaves this plan. Wave 1 then ends with
  `resolve_rate` (U5) live in `commission-service` in **shadow**: Java 21 reads Oracle and compares its
  answer with `COMMISSION_PKG.resolve_rate` for every calculation.
  **Proves:** the harness and the Java stack against real rate history, still with nothing at stake for payouts.

### Wave 2: Extract the rules (strangler, Oracle still the store)

- `commission-service` (Java 21, Spring Boot 3.3, Maven wrapper; `BigDecimal` scale 2, `HALF_UP`
  named at the one rounding site) implements U2-U8 against the **existing Oracle tables**.
- Strangle in this order: `resolve_rate`, then `set_commission_splits` / rate management, then
  `calculate_policy_commission`. Each step runs in shadow first: both paths write to a scratch
  ledger, and the service's ledger is compared row by row with Oracle's for a full month close.
  Only then does the delegating package route to it.
- The legacy `run_tests.sql` must stay green against the delegating package at every step (carrier
  standard evidence rule).
- Transaction semantics (R-10): one command, one transaction. The delegating PL/SQL keeps
  commit-on-return so legacy callers see no change.
- **Proves:** every business rule lives in one place, outside Oracle, and produces the same ledger to
  the cent for real month closes. After this wave the Oracle licence covers storage only.

### Wave 3: Move the data and retire Oracle

- `COMMISSION_PAY` tables move to PostgreSQL 16, with the rewritten `commission_rates` index
  (partial unique + exclusion constraint) and a split-total constraint. Backfill, dual-read verify,
  then cut over.
- The service switches its datasource. The warehouse extract (if Q1 = dbt-postgres) repoints to
  PostgreSQL. `COMMISSION_PKG`, `DW_ETL_PKG`, the types and `run_tests.sql` are retired.
- **Proves:** zero Oracle dependency for Commission Pay, and full-history reconciliation (every ledger
  row and every audit row count) between the Oracle export and PostgreSQL.

### What to take to the renewal meeting — **OPEN on Q1**

- If Q1 = dbt-postgres: ask for a bridge term long enough for Waves 1-3 on both schemas, with no
  growth in cores. After Wave 2, Oracle is a data store only.
- If Q1 = Databricks: the bridge term for `COMMISSION_PAY` is the same, but `COMMISSION_DW` must stay
  licensed until the Databricks track cuts over. Its timeline is set by that track, not this plan.

### Decisions finance must make before Wave 2 code (carrier standard rule 5)

| # | Divergence | Options | Recommendation |
|---|---|---|---|
| D-1 | Split inputs with > 2 dp (R-3) | (a) reproduce the stored 99.99/100.01; (b) reject >2 dp at the edge; (c) round to 2 dp, then require = 100.00 | (b). Fix any stored totals ≠ 100.00 first, with sign-off. |
| D-2 | Penny drift across split rows (R-2) | (a) keep per-row rounding (legacy); (b) largest-remainder allocation so rows sum to the policy amount | (a) in Waves 2-3 for parity. Consider (b) as a separate, announced change afterwards. |
| D-3 | Same-day amend of a referenced rate (R-8) | (a) keep in-place update; (b) new version row, old row frozen | (b). It is additive for ledger parity, and it restores rate-to-ledger traceability. |

## 8. What to measure, before and after

Measured on the legacy fixture now (the "before"), and on the target at the end of each wave in the
same report shape.

| Measure | Before (fixture, this run) | After target |
|---|---|---|
| Legacy suite result | OLTP 17/17, OLAP 5/5 | Unchanged against the delegating package (Waves 1-2) |
| Characterization checks covering BR-1..BR-29 | 17 of 29 rules touched by an existing test, 6 of them only partly (BR-1, 3, 6, 12, 17, 24) | 29 of 29 |
| Ledger rows and `SUM(commission_amt)` per period, per agent | e.g. 2025-06 = 92.02 after probes | Identical to the cent, every row |
| Fact vs ledger reconciliation per period | 2025-06: fact 100.02 vs ledger 92.02 after a re-split (FAIL) | Equal on every load |
| MV/report vs fact per period | stale until refreshed (P17) | Equal on every load |
| Re-run idempotency: row counts after run 1 and run 2 (ledger, fact) | Ledger equal; fact grows orphans | Equal for both |
| Audit rows by `action` per run | 19 after suites + probes | Same counts for parity actions, plus a rejected-attempt log |
| Error verdict parity (ORA-20001..20008, ORA-00001) per scenario | Recorded in the transcripts | Same code per scenario |
| Split allocations with stored total ≠ 100.00 | 0 in seed; production unknown | 0, enforced by a constraint |
| Scopes with > 1 closed rate | Impossible in the fixture (R-5); production unknown | Unlimited history |
| Month-close wall time (all policies) and p95 per-policy calc | Not yet measured; capture in Wave 1 on a production-sized extract | ≤ legacy |
| Oracle objects owned by Commission Pay | 2 packages, 2 types, 11 business tables, 1 MV | 0 |

## 9. Housekeeping

The Oracle container started for this assessment (`otterworks-insurance-assess-insurance-oracle-1`)
was stopped and its volume removed with `make insurance-down NS=assess`.
