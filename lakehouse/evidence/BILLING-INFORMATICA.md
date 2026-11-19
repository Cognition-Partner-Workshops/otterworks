# Billing Informatica conversion — Step 4

Scope: 35 SFX_BILLING inventory IDs: seven mappings, seven sessions, six sources,
seven targets, four tasks, workflow, worklet, Scheduler and default_session_config.
No legacy source changes. No consumer retargeting or whole-domain completion claim.

## State and precedence

Informatica runs after `dbt_billing_reporting`, with BTEQ load/monthly/close outputs
as explicit prior inputs. Its seven Delta targets are separate from BTEQ silver/gold:
`lakehouse/.data/{NS}/informatica/{business_date}/delta/{target}`. Staging targets
truncate; other targets preserve unmatched prior rows and apply the XML writer modes.
The independent PySpark writer uses XML port metadata, not the legacy expression
implementation. Typed Delta targets retain NULL versus empty and duplicate rows.
The added ordinal is comparison provenance, not a business key. ASCII-space trim,
uppercase, numeric prefix parsing, half-up rounding, currency defaults, static
lookups, router rejection, filters, update-else-insert, GL branches/pre-SQL and
sequence allocation are reproduced explicitly. GL tax branches omit zero tax.

The writer materializes a fixture-sized row set in driver memory, then publishes
each target through Delta and atomic sidecar files. It is not certified for
production scale or cross-target rollback. XML and shared parameters remain
read-only configuration dependencies. This is not native PowerCenter validation.

## Actual executable reference, matched inputs

`etl/informatica/README.md` and runner/{repo,engine,workflow,expr}.py establish an
executable emulator. The reference helper runs its actual Integration workflow,
MappingRun transformations and PostgreSQL writers. It clones physical column types,
nullability and constraints into the exclusively owned database
`lh_billing_infa_<crc32(NS)>`, never overwriting the legacy source database.

Before any modern mapping, `inputs/prior.json` freezes **only pre-Informatica**
BTEQ input states. Those exact values initialize both implementations. Landing
files are the same unchanged `warehouse/landing` date partitions. `inputs.json`
records default currency, tax rate, date and initial sequence counter; the reference
starts the native sequence at that identical counter. Native evaluation never uses
converted Informatica results. The counter persists across modern attempts, so
same-date retry changes sequence IDs like native pre-SQL/delete-and-reinsert;
financial row multiplicity is preserved rather than normalizing IDs out of parity.

Why freeze exact priors: earlier BTEQ gold parity intentionally allows
case-insensitive currency representatives. Eight retained journal rows had `usd`/
`Usd` in gold versus `USD` in native monthly state. Those are unchanged input rows,
not Informatica transformations. Freezing the chosen BTEQ boundary resolves that
input discrepancy **without** case-folding any Informatica target output. All 44
existing BTEQ/reporting specs still pass independently.

The reference captures exact writer `.bad` target/record lines. A thin MappingRun
subclass observes input contexts removed by native t_expression; evaluation and
rejection remain entirely native. It captures full transformation-rejected input
rows and checks that their count equals native FAILED_SOURCE_ROWS. An uncaptured
source/transformation error fails reference preparation rather than fabricating a
reference. Seven typed target specs, seven writer reject specs, seven full
transformation-reject specs and seven error-count specs make **28 new surfaces**.

## Workflow and alert

Each of seven pipeline export nodes executes an actual selected mapping. Worklet
ordering joins the two staging branches and account upsert, invoice header/line
join before GL, and the decision is unconditional after the GL status envelope.
Only a successful GL session with zero failed rows permits payment work. A caught
mapping error writes FAILED metadata; separate validation gates prevent stale data
parity while allowing the false decision and alert to execute. Successful sessions
can have rejects, matching Stop-on-errors=0 and the XML decision's exact GL check.

The false branch atomically queues `outbox/gl_posting_alert.json` for
finance-data-oncall@otterworks.example and **exits nonzero**, marking the workflow
FAILED. With SFX_LH_SMTP_HOST it also invokes SMTP; without it the durable outbox
and failed pipeline are the notification handoff. This is not a noop. A successful
decision does not queue/send an alert. Live SMTP delivery was not exercised.

Scheduler replacement uses the established daily UTC, logical-date-minus-one
contract, not an extra 01:30 trigger with an invented legacy timezone. Its start is
20261110 rather than native 20260701; earlier dates need explicit backfill with
available landing inputs. Automatic July–November historical scheduling is not
claimed. Performance
buffers, native log retention and commit intervals are not certified. Abrupt
process death can still block downstream nodes; platform failure monitoring is a
cutover requirement. See open/high A-120/A-122/A-123/A-124 and open/med A-119.

## Reproduction

Prepare the BTEQ boundary per BILLING-REPORTING.md first if it is not already built.
Then, from the repo root:

```sh
NS=sfx-d1110-after lakehouse/.venv/bin/python -m lakehouse.billing.informatica \
  --business-date 20261109 --landing warehouse/landing
NS=sfx-d1110-after LEGACY_NS=sfx-d1110-before \
  lakehouse/.venv/bin/python -m lakehouse.billing.informatica_reference \
  --business-date 20261109 --landing warehouse/landing
make sfx-lakehouse-parity NS=sfx-d1110-after LEGACY_NS=sfx-d1110-before BUSINESS_DATE=20261109
SFX_LH_INFA_NATIVE_TEST=1 make sfx-lakehouse-test NS=sfx-d1110-after BUSINESS_DATE=20261109
lakehouse/.venv/bin/python -m lakehouse.orchestration check
```

The first command is the single-session preparation equivalent of the seven actual
`--table` pipeline commands. Its completion metadata must be inspected (caught
errors deliberately return an envelope so the pipeline decision remains reachable).
The deployed graph includes real start/worklet/decision/payment/alert/finish tasks
and independent session validation nodes. The reference command must succeed
before parity; it fails on workflow errors or uncaptured transformation drops.

CI explicitly prepares the billing BTEQ snapshots and Informatica oracle before
the shared graph, like the users oracle. `informatica_reference --replay-next-run`
restores only the prepared sequence input so that the next graph execution consumes
the same counter range as the native oracle. Normal execution still advances its
persistent counter; this fixture-only flag does not change writer semantics.
Split sessions retain typed writer-order state separately from canonical parity
outputs, so a Delta partition read cannot reassign sequence values to other invoices.

## Verification evidence

All **72 billing parity specs PASS**, including all 28 new surfaces. Shared-input
target counts: staging account 300, account 300, staging header 2100, header 2100,
line 4184, GL 6451, payment 2000. Shared fixture has no rejected rows; each of the
seven error-count surfaces has one row containing zero, not one rejected row.
JSON evidence carries namespace/date/SHA/dirty/spec hash and full results.

`test_informatica_native_reject_row_parity` also executes the **actual emulator**
on independent nonempty edge fixtures. It compares every target/reject/error PSV
byte-for-byte against the modern implementation: duplicate/null account IDs,
missing account/amount header routes, malformed numeric/date rows, zero totals,
line fallback, repeated upserts and silently filtered line/payment rows. Native
reference inputs and outputs are isolated from the shared normal fixture.

Other named verification:
- `test_informatica_empty_normal_errors_and_writers`: empty, normal, malformed,
  numeric-prefix/default/trim/upsert, bounds and null constraints.
- `test_informatica_journal_filters_tax_sequence_and_retention`: zero/nonzero tax,
  balanced branches, credit/unselected retention, sequence exhaustion and bad rates.
- `test_informatica_decision_alert_and_scheduler`: both decision outcomes, session
  failure versus row rejection, payment gating, durable outbox, SMTP invocation
  (mock server), nonzero alert result, scheduler/date and pipeline dependencies.

Assumptions A-116–A-124 are linked from all 35 scoped coverage entries. They expose
the prior-state decision and unresolved operational risks, not acceptance of them.
