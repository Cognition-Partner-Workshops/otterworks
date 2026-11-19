# Billing load-layer evidence

Scope: six billing load/history BTEQ scripts, twelve FastLoad controls,
twenty-six staging/base/history tables and the six corresponding daily-chain
stages. This is not whole-domain acceptance: 83 other billing-owned IDs remain
pending. Ownership is recorded in `coverage/domains/billing.yaml`.

## Fixture and comparison boundary

Both engines used the existing `warehouse/landing` files for business date
`20261109`, with `NS=sfx-d1110-after` and `LEGACY_NS=sfx-d1110-before`.
No landing data was regenerated. The already-running legacy emulator's full
daily chain had also executed later monthly/period-close mutations. To compare
the requested load layer rather than those later transformations, its local
`sfx_billing.gl_journal_line` fixture state was truncated and these read-only
legacy scripts were replayed through `warehouse.teradata.bteq.Runner`:

1. `load_account_history.bteq`
2. `01_load_accounts.bteq`
3. `02_load_subscriptions.bteq`
4. `03_load_invoices.bteq`
5. `04_load_payments.bteq`
6. `05_load_usage.bteq`

All six returned code 0. Existing staging tables came from those same landing
files. See A-106. This changes only local fixture database state, not legacy
source. Subsequent period-close/report parity must prepare its own matching
boundary instead of treating these mutable PostgreSQL tables as as-of readers.

The silver build was run with:

```sh
NS=sfx-d1110-after BUSINESS_DATE=20261109 SPARK_LOCAL_IP=127.0.0.1 \
  lakehouse/.venv/bin/python -m lakehouse.runtime.dbt --select tag:billing
```

```text
Finished running 26 table models, 40 data tests
Done. PASS=66 WARN=0 ERROR=0 SKIP=0 TOTAL=66
```

`make sfx-lakehouse-parity NS=sfx-d1110-after LEGACY_NS=sfx-d1110-before
BUSINESS_DATE=20261109` passed all 26 specs. Per-table counts, fingerprints,
normalization, spec hashes, Git SHA/dirty state and timestamps are in
`PARITY.md` and `parity/billing.*.json`. CHAR trailing-space normalization is
restricted to declared CHAR columns (A-101); numeric/date values have no added
tolerance, and null/empty strings are not conflated. This initial-load fixture
does not by itself prove native FastLoad sessions/reject tables or history replay.

## Stateful and failure checks

`test_billing_history_replay_and_order` executes the actual rendered SQL against
isolated Delta tables across four completed dates. It checks identical replay,
changed and corrected latest-day replay, null transitions, new/absent customers,
case/trailing-space comparisons, empty input, batch tracking, older-date
rejection and unchanged outputs after invalid/null/duplicate input keys.

The normal dbt build above was also repeated for the same date successfully.
An actual dbt run with `BUSINESS_DATE=20261108` and
`--select customer_account_hist+` then produced the expected rejection:

```text
Older-date dbt exit: 1
java.lang.RuntimeException: A completed later account-history business date already exists
Done. PASS=0 WARN=0 ERROR=1 SKIP=8 TOTAL=9
```

The final 26-spec parity pass followed that rejected run, proving the fixture's
history and batch outputs still matched. Guard macros use fetched `run_query`
calls: ordinary session-adapter pre-hook SELECTs are lazy and would not force
Spark's assertions to evaluate.

Other tests exercise all twelve typed loads with normal/empty/different-date
inputs and invalid keys, staging width errors, base text truncation, padding,
decimal rounding and null/empty distinctions. Journal tests cover same-date
retention, newly seen posting dates, empty input and SQL NULL-date append
behavior. Existing ingestion tests cover malformed and missing feeds. A named
graph test verifies the six replaced billing stages, models and all output
parity dependencies; existing graph tests cover readiness, retries and dates.

## Finishing checks and limitations

`make sfx-lakehouse-test NS=sfx-d1110-after BUSINESS_DATE=20261109`:

```text
Assumptions: 55 entries, 0 errors
Coverage: 438 inventory objects, 438 map entries, 0 errors
Pipeline: 2 DAGs, 77 tasks, valid
89 passed, 1 warning in 62.29s (0:01:02)
```

The warning is dbt-common's `datetime.utcnow()` deprecation. Standalone
`lakehouse/.venv/bin/python -m lakehouse.orchestration check` also reported
`Pipeline: 2 DAGs, 77 tasks, valid`.

Coverage updates affect only 50 billing-owned IDs: 25 pending tables and six
pending scripts become `converted`; six pending cron stages become
`replaced_by_platform`. The existing converted customer-account pilot and
twelve already-replaced FastLoad controls receive current parity/assumption
links without changing status. No other domain's entry was changed.

Assumptions A-100 through A-107 describe types, text/collation, loader
replacement, snapshot/journal semantics, SCD2, failure boundaries, parity stage
and scheduling. **A-105 remains open/high risk:** Delta publishes each model
atomically, not the legacy two-table SCD2 transaction. Cross-model failure can
leave partial outputs requiring same-date retry and operational review; dbt
key tests also run after publication rather than enforcing every database
constraint at insertion. This needs explicit risk acceptance before production
cutover. Native Teradata/FastLoad and production scheduler execution were not
tested; no full-domain or whole-estate completion is claimed.
