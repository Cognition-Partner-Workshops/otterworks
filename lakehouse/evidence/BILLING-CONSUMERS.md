# Billing consumers, BI and partner extraction

## Scope and interfaces

The final 13 billing-owned inventory IDs are covered by `consumer_queries.py`,
`consumer_exports.py`, 13 output-specific parity specs and named tests in
`test_billing_consumers.py`. The actual ownership file has **133 IDs**, all with
non-pending status. This is inventory coverage, not production cutover approval.
No source under `warehouse/`, `etl/`, `consumers/` or `services/` is modified.

Services are not rewritten or automatically retargeted. Their warehouse-read
responsibility can use `query(spark, name, business_date, clock=None, **parameters)`.
HTTP serialization, authentication, feature flags and caches stay in the services.
Seven service SQL results, billing CSV, partner raw/processed/transfer surfaces,
typed BI rows and workbook count feed each have their own parity spec.

The default pinned clock is UTC business date plus one day, not wall clock.
`--clock-date YYYYMMDD` explicitly overrides it. Analytics status/plan and report
period are validated parameters. SQL is extracted from fixed read-only Python,
Ruby, Java, Scala and BTEQ sources. Bindings use billing silver and **final
monthly/closed gold**, not Informatica or alternate-schema Spark outputs.
Runtime packaging must retain those read-only SQL source files; it does not
need a connection to their legacy warehouse. Freezing extracted SQL instead
would be a separate deployment decision.
The 44 existing warehouse parity specs establish matching stage-specific inputs.
The legacy fixture remains the consistently restored final reporting state from
`BILLING-REPORTING.md`; these readers require no new legacy data mutation.

## Actual legacy readers and boundaries

`consumer_reference` runs all eight actual source SQL statements through the
repository Teradata emulator, binding only clock/caller parameters first. It
does **not** call the lakehouse AST compiler. Both backends share SQLGlot parsing,
not rewrite logic. The actual fixed billing DTO and CSV exporter ASTs execute
directly; partner postprocessing and simulated SFTP invoke the unchanged shell
scripts. Source hashes are in `BILLING-CONSUMERS-PROVENANCE.json`.

Power Query/Excel are unavailable. Independent typed readers consume the actual
legacy and lakehouse PSV files with the PQ date/text/Int64 contract. Empty text
remains unknown/null, never count zero. Workbook output sums status/currency
counts. This is explicit emulation, not an executed Excel refresh (A-136).

The native-clock test creates isolated PostgreSQL temporary tables and matching
Spark views, including mixed-case NOCASE currency grouping. All eight readers
are compared at clocks 20261109, 20261110 and 20270115. Partner gating yields 0
rows on bill date and 3 on the next day; future reconciliation yields 2 overdue
invoices, so that surface is not verified only with empty data.

Money comparisons are exact cents; only DSO/open-ratio permit 1e-6 absolute
tolerance. CHAR right padding and declared NOCASE currency/status representatives
are normalized, never CASESPECIFIC region/plan/customer names. Comparison-only
ordinals preserve duplicate/null query rows. Billing CSV uses actual file-row
comparison with invoice-number keys; duplicate-row emission is additionally
byte-checked against the source exporter. Partner validation rejects duplicates.

## Publication and orchestration

Artifacts are under `lakehouse/.data/<NS>/exports/`:

- `billing_consumers/<date>/current/`: query JSONL, invoices CSV, typed account
  status and workbook feed. JSONL canonicalization is comparison-only; `query()`
  exposes the original result aliases and values.
- `billing_partner/<date>/current/`: raw rows, `partner-invoices-<YYYYMMDD>.csv`
  and transfer receipt. The legacy nightly CLI permits explicit output paths,
  so its reference uses this same eight-digit filename.

Private 0600 files are flushed/fsynced and local POSIX version pointers publish
atomically. Validation and transfer configuration fail **before** the partner
pointer changes, intentionally stronger than legacy publish-before-SFTP failure.
Receipts verify actual native dry-run destination and physical CSV SHA256/bytes;
no live transmission occurs. Separate partner/other-output transactions, orphan
cleanup, distributed storage, whole-DAG leases and production volume remain open.

Daily export waits for billing gold and dated history export, then runs all 13
comparisons. A separate paused UTC `15 2 * * *` partner DAG waits for the dated
export, runs `--partner-only` and verifies all three partner surfaces. Cadence,
readiness and dependencies have named tests. Source cron ID is
`cron_entry:warehouse/teradata/jobs/crontab.example#c583c86ce8ed`.

## Reproduction and recorded evidence

Use NS `sfx-d1110-after`, LEGACY_NS `sfx-d1110-before`, business date 20261109 and
landing `warehouse/landing`. Export `TD_PG_PORT=55395` first for the existing
local emulator. A native-suite invocation without that environment used default
port 5432 and failed only its native consumer test; load the documented port
rather than changing the test or probing alternate shared endpoints.

The first full local Airflow DAG run passed the new consumer export/parity tasks
but failed the existing billing Informatica GL parity: 5877 generated IDs moved
by one 5877-row sequence range; all other columns matched. The shared fixture
requires the already documented `informatica_reference --replay-next-run`
preparation before each identical graph replay (see `BILLING-INFORMATICA.md`).
This restores the prepared sequence input and regenerates the actual isolated
native oracle; normal production counter advancement is unchanged. The repeated
exact Airflow command passed: `2 passed in 2.13s`, followed by all 219 daily DAG
tasks succeeding and `DagRun Finished: ... state=success`.

```sh
export NS=sfx-d1110-after LEGACY_NS=sfx-d1110-before TD_PG_PORT=55395
lakehouse/.venv/bin/python -m lakehouse.billing.consumer_reference --business-date 20261109
lakehouse/.venv/bin/python -m lakehouse.billing.consumer_exports --business-date 20261109
make sfx-lakehouse-coverage NS=sfx-d1110-after
# Execute the unchanged guide DOMAIN=billing ownership script.
make sfx-lakehouse-parity NS=sfx-d1110-after LEGACY_NS=sfx-d1110-before BUSINESS_DATE=20261109
SFX_LH_INFA_NATIVE_TEST=1 SFX_LH_BILLING_CONSUMER_NATIVE_TEST=1 make sfx-lakehouse-test NS=sfx-d1110-after
lakehouse/.venv/bin/python -m lakehouse.billing.informatica_reference --landing warehouse/landing --business-date 20261109 --replay-next-run
make sfx-lakehouse-airflow-test NS=sfx-d1110-after LEGACY_NS=sfx-d1110-before BUSINESS_DATE=20261109 SFX_LH_LANDING=warehouse/landing
lakehouse/.venv/bin/python -m lakehouse.orchestration check
```

Recorded full parity: **209 PASS, 0 FAIL**. New counts: 6 BI, 10 admin overdue,
1 admin summary, 60 rollups, 667 invoice-query/CSV, 100 aging, 669 partner CSV
lines (667 records plus header/trailer), 667 partner raw, 1 transfer receipt,
1 reconciliation summary, 0 current unreconciled and 6 workbook rows.
Full native-enabled suite: **309 passed, 9 warnings in 273.96s (0:04:33)**.
Warnings are the existing dbt `datetime.utcnow()` deprecations. Orchestration:
`Pipeline: 26 DAGs, 311 tasks, valid`. Exact ownership check:
`billing: 133 owned objects, zero pending`.
Focused native tests: **28 passed**. They include normal/empty/error, duplicates,
malformed money, signed zero, CSV quoting, Int64 overflow, live-transfer refusal
and injected rename failures. Actual awk golden tests verify empty, fractional
and signed-zero CSV bytes.

Semgrep with p/default, p/owasp-top-ten and p/security-audit:
`Ran 323 rules on 4 files: 0 findings.` One narrow exec-audit annotation explains
execution of fixed repository DTO/exporter ASTs. No scanner config changed.

Assumptions **A-131..A-138** document clocks, source/input precedence, numeric/
collation rules, service interfaces, partner behavior, BI emulation, publication
and cron. A-136..A-138 and earlier A-105/A-114/A-130 remain open cutover risks.
Native Teradata, Excel rendering, live SFTP, live scheduler dispatch, production
scale and automatic service cutover are not verified.
