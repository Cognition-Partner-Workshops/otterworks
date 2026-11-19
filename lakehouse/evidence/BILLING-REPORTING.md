# Billing reporting and monthly conversion

Scope: five billing scripts/stages (10–14), both billing macros, the monthly
procedure including its OUT parameter, four owned views, and the additional
mutations of INVOICE_HDR, INVOICE_LINE and GL_JOURNAL_LINE. This does not claim
completion of billing Spark, Informatica or consumer integrations.

## State and orchestration contract

Silver remains the immutable load-stage snapshot. Gold publishes named states:

1. `monthly_invoice_line` replaces generated descriptions and preserves other lines.
2. `monthly_invoice_hdr` recalculates eligible invoice amounts and all currency controls.
3. `monthly_gl_journal_line` rebuilds the selected month's journal with cumulative
   invoice postings and eligible credit reversals; its dbt balance test must pass.
4. `closed_invoice_hdr` explicitly depends on the monthly journal as well as the
   monthly header, so close cannot precede monthly mutation/balance validation.
5. Final invoice views read the closed header. `currency_daily` deliberately reads
   the load snapshot; `currency_totals` reads the monthly snapshot. Subscription
   macro/view projections retain their different PLAN_CODE origins.

`dbt_billing` now selects only silver; `dbt_billing_reporting` follows it and
selects gold. Five ordered export nodes publish the seven report files. Eighteen
new parity tasks cover monthly states, the procedure result, macros/views and
actual files; the prior 26 table specs remain active. The named replacement test
is `lakehouse/tests/test_billing_reporting.py::test_billing_reporting_stage_replacement`.

## Matching legacy fixture, not mismatched final versus load snapshots

Namespaces are `sfx-d1110-before` / `sfx-d1110-after`, BUSINESS_DATE is `20261109`,
and the common landing inputs are the existing `warehouse/landing` feeds.
No landing files or legacy source files were changed. Existing emulator staging
is retained; all twelve staging parity specs independently verify its agreement
with the lakehouse's typed shared inputs.

Reproducible local fixture preparation (requires the already running emulator):

```sh
NS=sfx-d1110-after LEGACY_NS=sfx-d1110-before \
  warehouse/.venv/bin/python -m lakehouse.billing.fixture --business-date 20261109
```

The helper clears only the mutable billing journal fixture, replays history and
the five other billing load scripts, snapshots the three load outputs in
`sfx_billing_parity.load_*`, then runs scripts 10–14 in legacy order. Immediately
after script 12 it snapshots `sfx_billing_parity.monthly_*` and captures the
procedure's actual OUT `n` in `sfx_billing_parity.monthly_invoice_result`. Final
headers/views remain in `sfx_billing`. Earlier table specs for these three tables
read the load snapshots, not the subsequently mutated live tables. Other load
specs are unchanged. The helper was rerun successfully to restore the same stage
boundaries, not to substitute hand-computed reference values.

The emulator's sqlglot warning about unsupported CALL syntax is from query-log
parsing, not skipped execution: `Runner.execute` dispatches `routine(source)`
before SQL translation; `routine` recognizes CALL, loads the saved procedure,
invokes `spl.interpret`, and emits its OUT parameter. The `finally` path invokes
`log_statement`, where sqlglot falls back to Command. The helper requires exactly
one captured `n`, otherwise it fails. Evidence contains `n=2084` on both sides;
monthly invoice lines grow from 2000 to 4184 and monthly journal rows from 830 to
9466. All corresponding full-column parity checks pass, not just script exits.

## Actual file outputs and normalization

Legacy files: `.data/sfx-d1110-after/parity/legacy/billing/20261109/`.
Lakehouse files: `.data/sfx-d1110-after/exports/billing/20261109/`.

The seven files are `subscription_plans.psv`, `currency_daily.psv`,
`invoice_monthly.psv`, `gl_trial_balance.psv`, `invoice_periods.psv`,
`period_close.psv`, and `account_status_20261109.psv`. Specs read these actual
files; they do not replace file comparison with a query of the source tables.

The executable BTEQ emulator emits headerless UTF-8 pipe-separated rows for DATA
and REPORT. File specs compare rows, ignoring unspecified SQL row order, declared
CHAR right-padding and only case-insensitive grouped-key representative spelling.
Trial-balance numeric display is normalized to two decimals because ZEROIFNULL
can print `0` rather than `0.00`. Nullable decimal file fields instead preserve
their exact scale-two/empty representation, avoiding coercion of empty nulls.
Required invoice/status/trial-balance ordering is deterministic; CI keys sort by
lowercase/rtrim with nulls last. Account names and descriptions stay case-sensitive.
Native Teradata REPORT headings, pagination and terminal layout are not certified.

Publication streams to a same-directory temporary file, flushes/fsyncs, then
atomically replaces the destination. Retry replaces, never appends; empty results
replace stale content with an empty file. Malformed unquoted delimiter/newline
fields or publication errors leave the existing destination intact and remove the
temporary file. Files are atomic individually, not a multi-file transaction.

## Tests, assumptions and remaining limitations

`test_billing_reporting.py` exercises monthly amounts/tax/control totals, mixed-case
and padded plans/currencies/GL numbers, case-sensitive account names, null groups,
future generated-line removal, future invoices/credits, missing joins, cumulative
adjustments, journal month retention/rebuild and null dates, reversals, balanced and
imbalanced journals, same-input monthly replay, previous-month close boundaries,
leap/year calendar encodings, half-open history intervals, all-empty inputs,
divide-by-zero failure, actual export retry and CI ordering, empty decimal file
comparisons, malformed rows, atomic replace failure, cleanup and invalid dates.

New assumptions linked from affected coverage entries:

- A-108: immutable load/monthly/close ordering and serving surfaces.
- A-109: monthly procedure joins, dates, decimal rounding and OUT count.
- A-110: journal deletion/rebuild, null predicates, account/sign rules and balance.
- A-111: Teradata integer dates and previous-calendar-month close window.
- A-112: actual file contract, justified formatting normalization and atomic retry.
- A-113: CI joins/groups and unused macro parameters — **open/medium** for untested
  non-ASCII ICU equivalence beyond the tested case/trailing-space examples.
- A-114: failure/publication boundaries — **open/high**, preserving A-105's risk.
- A-115: as-of history extraction and null groups.

Delta publication is per model, not a cross-model rollback. dbt tests may detect
violations after a model publishes. Export tasks are blocked by gold build errors;
this is deliberately stricter than legacy early/partial export ordering. Native
procedure error codes and partial-commit behavior are not certified. These open
risks require cutover review; fixture PASS is not operational-risk acceptance.

Coverage changes are 12 pending-to-converted script/macro/procedure/view objects,
five pending-to-replaced_by_platform stages, plus extended targets/evidence for
the three already-converted mutable tables. No scoped object remains pending,
subject to the explicit open risks. Other domains' coverage entries are unchanged;
66 other owned billing objects remain pending outside this step. Working notes
`coverage/domains/billing-plan.md` remain deliberately untracked.

Machine-readable results are in `evidence/parity/billing.*.json`; the generated
`PARITY.md`, `COVERAGE.md` and `ASSUMPTIONS.md` summarize them. Verification commands:

```sh
NS=sfx-d1110-after BUSINESS_DATE=20261109 SPARK_LOCAL_IP=127.0.0.1 \
  lakehouse/.venv/bin/python -m lakehouse.runtime.dbt --select path:models/gold/billing
NS=sfx-d1110-after SPARK_LOCAL_IP=127.0.0.1 \
  lakehouse/.venv/bin/python -m lakehouse.billing.reports --business-date 20261109
make sfx-lakehouse-parity NS=sfx-d1110-after LEGACY_NS=sfx-d1110-before BUSINESS_DATE=20261109
make sfx-lakehouse-test NS=sfx-d1110-after BUSINESS_DATE=20261109
lakehouse/.venv/bin/python -m lakehouse.orchestration check
```

Final verification: all 44 billing parity specs PASS (26 prior load outputs plus
18 reporting/monthly/file outputs). Gold dbt and the full test command printed:

```text
Done. PASS=35 WARN=0 ERROR=0 SKIP=0 TOTAL=35
Assumptions: 63 entries, 0 errors
Coverage: 438 inventory objects, 438 map entries, 0 errors
Pipeline: 2 DAGs, 101 tasks, valid
92 passed, 1 warning in 96.37s (0:01:36)
```

The standalone orchestration check also printed `Pipeline: 2 DAGs, 101 tasks,
valid`. The warning is dbt-common's existing `datetime.utcnow()` deprecation.
Persistent execution logs are `/home/ubuntu/billing-reporting-{legacy,dbt,export,parity,test}.log`.
