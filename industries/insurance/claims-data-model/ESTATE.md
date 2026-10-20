# Claims data model (PostgreSQL 16 + dbt, next to the Commission Pay facts)

The warehouse used to know only commissions. This directory adds the claims and policy side next to them: a
PostgreSQL 16 model of policyholders, policies, claims, claim payments and adjuster assignments, seeded from
the claims hub corpus (`industries/insurance/biztalk-claims-intake/corpus` on
`devin/1792473658-insurance-biztalk-fixture`, read here with `git archive` and never written) and from the
Commission Pay fixture (`services/industry-solutions/insurance/`, Oracle Free). A dbt project
(`carrier_warehouse`, `dbt-postgres`) stages both sides and builds two marts. Parity against the legacy
sources is the gate before any mart is trusted. The names in this file are fixed; changing one changes this
file in the same commit.

## How to run

```bash
make up NS=dev       # Oracle Free (make insurance-up) and PostgreSQL 16 (docker-compose.yml)
make check NS=dev    # the gate: corpus, Oracle ledger, load, dbt build, parity; fails on any RED row
make down NS=dev     # stops both containers and drops their volumes
```

Ports derive from `NS` (Oracle `51521 + crc32(NS) % 1000`, PostgreSQL `57432 + crc32(NS) % 1000`), so two
namespaces run side by side. `CORPUS_REF` selects the corpus commit (default
`origin/devin/1792473658-insurance-biztalk-fixture`); the commit read is written to `.corpus/REF` and named
in the parity report.

| Target | Does |
| --- | --- |
| `corpus` | `git archive` of the corpus at `CORPUS_REF` into `.corpus/` (git-ignored) |
| `oracle-ledger` | `oracle/01_calculate_ledger.sql`: `COMMISSION_PKG.calculate_policy_commission` for every in-force policy with splits, periods `2025-06` to `2026-10`; `oracle/02_load_star.sql`: `DW_ETL_PKG.load_commission_facts` and a complete refresh of `MV_AGENT_COMMISSION_SUMMARY` |
| `schema` | `sql/01_schema.sql`: drops and recreates schemas `commission`, `claims`, `stg`, `marts` |
| `load` | `loader/load_oracle.py` (Oracle to `commission`), then `loader/load_corpus.py` (corpus and Commission Pay policies to `claims`) |
| `dbt` | `dbt build` over `dbt/` (models and tests) |
| `parity` | `parity/parity.py` writes `parity/REPORT.md` and `parity/REPORT.json`; reads `parity/accepted_differences.yaml` |

## Schemas and tables

| Schema | Table | Grain | Source |
| --- | --- | --- | --- |
| `commission` | `agents`, `products`, `policies`, `commission_rates`, `commission_splits`, `commission_ledger` | as in `COMMISSION_PAY` | Oracle, copied column for column |
| `claims` | `policyholders` | one insured party | `CP-<policy_id>` per Commission Pay policy; `InsuredPartyId` from `stubs/policy` |
| `claims` | `policies` | one policy | Commission Pay `POLICIES` (premium, product) and `stubs/policy` (deductible, limit, expiry) |
| `claims` | `claims` | one FNOL claim number (16) | `inputs/fnol` with its policy stub; `triage_outcome` from `golden/triage` |
| `claims` | `claim_payments` | one payment instruction (14) | `inputs/payment`; `vendor_rounding_difference` = vendor file net - `net_amount` |
| `claims` | `adjuster_assignments` | one assignment request (10) | `inputs/assignment` with `stubs/roster` |

The loader derives every claims column from the corpus inputs and stubs with the hub's own rules (net
exposure, in-force at loss, reserve, report delay, policy age, ledger and vendor amounts, least-loaded
adjuster, SLA). The one value it carries rather than derives is `triage_outcome`, the `ClaimTriage` rules
policy's answer; `entered_claims_system` is that outcome not being `DECLINE_NOT_IN_FORCE`. Parity reads the
goldens independently, so a derivation that drifts from the hub goes red.

## Money and rounding

Money is `numeric(12,2)` everywhere. Where a value is rounded, the mode is the one the legacy code used:

| Value | Legacy code | Rounding |
| --- | --- | --- |
| `commission_ledger.commission_amt` | Oracle `ROUND(premium / 12 * pct / 100 * split / 100, 2)` | HALF_UP (Oracle `ROUND`), copied, never re-rounded |
| `loss_ratio_by_product_period.earned_premium` | `annual_premium / 12`, the base `COMMISSION_PKG` uses | HALF_UP: PostgreSQL `round(numeric, 2)` rounds half away from zero, as Oracle `ROUND` does |
| `claims.reserve_estimate` | C# functoid `ComputeReserve`, .NET `Math.Round` | **HALF_EVEN**, differs from Oracle |
| `claim_payments.indemnity_amount`, `expense_amount`, `salvage_credit`, `net_amount` | C# functoid `FormatMoney` on the per-type sums, .NET `Math.Round` | **HALF_EVEN**, differs from Oracle |
| `claim_payments.vendor_debit_total`, `vendor_credit_total` | XSLT `round()` on each line's absolute cents, then summed | HALF_UP per line on the absolute value |
| `claim_payments.vendor_rounding_difference` | difference of the two rows above, no rounding of its own | none (HALF_UP vendor net less HALF_EVEN ledger net) |
| `loss_ratio_by_product_period.loss_ratio` | new; ratio, not money | half away from zero, 4 decimals |

`loader/common.py` names the two Python modes (`half_even`, `half_up`); no call site rounds without one of them.

## dbt (`dbt/`)

| Model | Schema | Materialized | Grain |
| --- | --- | --- | --- |
| `stg_commission__ledger`, `stg_commission__agents`, `stg_commission__policies`, `stg_commission__products` | `stg` | view | source grain |
| `stg_claims__policies`, `stg_claims__claims`, `stg_claims__claim_payments`, `stg_claims__adjuster_assignments` | `stg` | view | source grain |
| `int_period_spine` | none | ephemeral | one calendar month, first to last ledger period or payment month |
| `commission_by_agent_period` | `marts` | table | agent x ledger period |
| `loss_ratio_by_product_period` | `marts` | table | line of business x month; earned premium, reported claims and reserve, paid indemnity, expense, salvage and net loss, vendor rounding difference, commission paid, paid loss ratio |

"Product" in `loss_ratio_by_product_period` is the line of business: the claims hub policies carry `LOBCd`
and no Commission Pay product code, so line of business is the only key both sides share.

Tests: `unique` and `not_null` on every key, `relationships` on every foreign key, `unique_combination` on
every mart grain, `money_scale_2` on every money column, `sum_equals` from each mart money column back to
the staging column it summarises, `earned_premium_matches_policy_months`, and
`vendor_rounding_difference_closes_ledger_to_vendor_file` with `vendor_rounding_difference_per_payment` (net
plus the difference is the vendor net, in total and row by row). `ledger_net_equals_vendor_file_net` is
severity `warn` and stays a warning by decision: it is the `PI-2026-880107` cent below.

## Parity (`parity/parity.py`)

One row per table and measure: row count, and the sum of each money column, source against target; totals
at the bottom; to the cent with no tolerance. Sources are Oracle `COMMISSION_PAY` / `COMMISSION_DW` for the
commission side and the corpus (inputs, stubs and the hub's goldens: `insert-claim`, `triage-facts`,
`triage`, `ledger-post`, `vendor-remittance-ff`, `assignment-notice`) for the claims side. A row that does
not match is RED and stays RED. `make check` passes only when every RED row is listed in
`parity/accepted_differences.yaml` (`row`, exact `difference`, `decided_on`, `decided_by`, `decision`,
`reason`); the row's cause is then that reason and decision. A RED row that is not listed, or whose difference
no longer equals the listed one, reads `UNEXPLAINED` and fails the gate; so does a listed row that is no
longer RED. The line under the totals states the gate and its counts.

## Accepted differences

`PI-2026-880107` (claim `CLM-2026-100405`, policy `POL-AUTO-48177`, value date 2026-10-08) has indemnity
lines 0.015 and 1234.565 and an expense line 0.50. The ledger post sums indemnity first and rounds half to even
(1234.58), netting **1235.08**; the vendor file rounds each line half up (0.02, 1234.57, 0.50), netting
**1235.09**. Decided 2026-10-20 by the claims and finance owner: **the ledger is the book of record.** Paid
loss in the marts is `net_amount`; the cent is carried in `vendor_rounding_difference` and not allocated.
Parity row `claim_payments.net_amount_vs_vendor_file` stays RED with this cause and is listed in
`parity/accepted_differences.yaml`; row `claim_payments.gap_equals_vendor_rounding_difference` checks that the
gap is exactly the carried difference.
