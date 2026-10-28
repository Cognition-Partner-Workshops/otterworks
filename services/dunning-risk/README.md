# Dunning risk: snapshot → Delta → Lakebase

An explainable 0–100 score, not a probability or a suspension action. All billing
reads are one SELECT-only snapshot of legacy Oracle `OW_BILLING` (tenants,
subscriptions, invoices, dunning_attempts, credit_notes) taken by the read-only
principal named by secret `OW_BILLING_RO_DSN` inside a `SET TRANSACTION READ ONLY`
transaction. Oracle is never written. No federation, JDBC or CDC: the snapshot is a
one-off extract copy. Existing environment OAuth M2M configuration is used unchanged.

## Rules (`ow_tp_dunning_v1`)

Legacy authority: `../legacy-billing/db/oracle/packages/05_pkg_dunning.sql`.
`fn_overdue_accounts` means **status 40, issued before the as-of calendar date**;
age is calendar days since issue, not a nonexistent due date. Paid means status
30. `sp_suspend_overdue` considers active tenants with status-40 invoices at least
14 days old; credits do **not** cancel that eligibility. This service only reports
it, never suspends tenants/subscriptions or schedules attempts.

| Component | Points |
|---|---|
| Oldest overdue invoice | 0 / 10 / 25 / 40 for 0 / 1–6 / 7–13 / ≥14 days |
| Payment record | `round(25 × overdue_count / max(paid_count + overdue_count, 1))` |
| Past dunning | `5 × min(sent_attempt_count, 4)`; sent status 20, scheduled on/before as-of |
| Uncovered exposure | `round(15 × max(overdue_total − remaining_credit, 0) / overdue_total)`; zero if no positive overdue total |

Sum the four integer components. Bands: low <35, medium 35–69, high ≥70.
With no paid/overdue invoices or past sent attempts, the band is
`insufficient_history`, **not low risk**. Future invoices, credit notes and attempts
are excluded. Credit amounts remaining are floored at zero and capped by exposure
in the calculation; already-applied credits are not deducted again. Monetary
arithmetic uses fixed-point decimals; rounding is SQL half-up. Current paid status
is payment-history evidence, not proof of payment punctuality (no payment date).

Invoices, attempts and credit notes are attributed to tenants, not subscriptions.
`risk_scope = 'tenant'` is explicit: the same tenant features repeat on each
subscription that has started by as-of, including suspended/cancelled ones. Never
sum the repeated exposure across subscriptions. A tenant with no started
subscription has key `NO_SUBSCRIPTION`. Composite key: `(tenant_id, subscription_id)`.
An active tenant meeting the legacy threshold has `suspension_eligible = true`;
the row's subscription status is shown separately. Missing required fields,
duplicate IDs, missing tenant attribution and cross-tenant attempts fail closed.

## Run manually

Run from this directory. Use the preconfigured service principal; **never export
host/auth/identity variables**, use a PAT, or use `LAKEBASE_MIGRATION_DSN`.
`snapshot.py` needs `OW_BILLING_RO_DSN` in the environment (`user/pass@host:port/service`
or JSON `{user, password, dsn}`); it is read by name and never printed. The Lakebase
branch `mig-dunning-risk` already exists, based on `production` with a seven-day TTL.
All Lakebase writes are through the Databricks-managed synced table, never a direct
Postgres connection.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
mkdir -p .local
.venv/bin/python snapshot.py .local/ow_tp_snapshot.json
.venv/bin/python prepare.py .local/ow_tp_snapshot.json .local/ow_tp_stage.sql
databricks experimental aitools tools query --warehouse 565cd2fd713738c4 --file .local/ow_tp_stage.sql
databricks experimental aitools tools query --warehouse 565cd2fd713738c4 --file score.sql
```

The immutable JSON snapshot is stored in Delta `ow_tp.ow_tp_dunning_risk.ow_tp_snapshots`
with its SHA-256 ID. Exact payload replays do not append another snapshot. The score
table is atomically overwritten from the latest captured snapshot, with deterministic
tie-breaking by snapshot ID. Oracle DATE columns are rendered as dates, `issued_at`
as a timestamp, NUMBER(12,2) amounts exactly; as-of is the capture's UTC date read
from the Oracle clock (`SYS_EXTRACT_UTC`). Empty tenant snapshots are rejected.
This bounded demo uses inline SQL up to 8 MB; it is not a bulk-ingestion system.

Initial sync creation (once only; the live instance already exists). The guard
requires a literal name and inline JSON, **not `@sync.json` or variable expansion**:

```sh
databricks postgres create-synced-table ow_tp.ow_tp_dunning_risk.ow_tp_scores_synced --json '{"spec":{"source_table_full_name":"ow_tp.ow_tp_dunning_risk.ow_tp_scores","primary_key_columns":["tenant_id","subscription_id"],"branch":"projects/ow-tp-billing/branches/mig-dunning-risk","postgres_database":"databricks_postgres","scheduling_policy":"SNAPSHOT","create_database_objects_if_missing":true,"new_pipeline_spec":{"storage_catalog":"ow_tp","storage_schema":"ow_tp_dunning_risk"}}}' --output json
databricks postgres get-synced-table synced_tables/ow_tp.ow_tp_dunning_risk.ow_tp_scores_synced --output json
```

`sync.json` records that spec for inspection only. The standard `ow_tp` catalog is
supported; no Lakebase catalog registration is needed. Wait for
`SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE`. Native sync provisions only the target
branch's `databricks_postgres.ow_tp_dunning_risk.ow_tp_scores_synced` table plus its
managed pipeline metadata. Pipeline ID is returned in `status.pipeline_id`.

The bundle defines a **PAUSED** daily job: SQL scoring on existing warehouse
`565cd2fd713738c4`, then a full refresh of that managed sync pipeline. No warehouse
or cluster resources are defined. Supply the pipeline ID when validating/deploying:

```sh
databricks bundle validate -t mig_ow_tp_billing_20261028 --var sync_pipeline_id=0688c8f0-0812-479f-910c-d1a8c1c2ff81
databricks bundle deploy -t mig_ow_tp_billing_20261028 --var sync_pipeline_id=0688c8f0-0812-479f-910c-d1a8c1c2ff81
```

For a **new source snapshot**, first repeat the snapshot/staging commands above.
The job intentionally does not extract operational state automatically. Running it
without staging a new snapshot recomputes the previous as-of, not today's risk.
Leave its schedule paused; a manual `bundle run ow_tp_dunning_risk_refresh` with
the same target/variable triggers both tasks. Concurrent manual staging/scoring
runs are unsupported; the job itself allows only one concurrent run. No automated
cleanup is defined: Lakebase expires with the branch; retained Delta snapshots and
evidence are not deleted by a refresh.

## Verify

```sh
.venv/bin/python -m unittest -v test_dunning
.venv/bin/python test_dunning.py --warehouse-sql .local/ow_tp_score_tests.sql
databricks experimental aitools tools query --warehouse 565cd2fd713738c4 --file .local/ow_tp_score_tests.sql --output json
databricks experimental aitools tools query --warehouse 565cd2fd713738c4 --file export.sql --output json > .local/ow_tp_delta_rows.json
.venv/bin/python verify.py .local/ow_tp_delta_rows.json > .local/ow_tp_parity.json
```

The warehouse regression query exercises the **actual scoring SQL**, not a second
implementation: age 0/1/6/7/13/14, future data, mixed paid/overdue history, sent vs
scheduled/skipped attempts, attempt cap, full/partial/excess/negative credits,
negative totals, suspended tenants, and subscription fan-out/no-subscription.
The verifier SELECTs the complete Lakebase copy using a separately minted target
credential and read-only connection. It compares every column as multisets,
including duplicate multiplicity, snapshot provenance and component points;
matching row counts alone cannot pass. It then replays the body of legacy
`pkg_dunning.fn_overdue_accounts` on Oracle as one SELECT (status 40, issued before
the as-of calendar day, calendar-day age; no package execution, read-only
transaction) aggregated per tenant, and requires the Lakebase rows'
`overdue_invoices`, `oldest_overdue_days` and `overdue_total` to match it exactly
for every tenant. `verify.py` therefore needs `OW_BILLING_RO_DSN` too. It emits equal SHA-256 hashes and examples
selected from the **Lakebase rows**: Tenant One plus two or three distinct tenants,
preferring overdue, paid and credit history when available. Missing one category
does not invalidate full-row parity; fewer than two examples fail this demo proof.
Raw snapshots/exports and credentials are never
committed or bundled. Live results belong in the PR description.

Repository `make tp-smoke` was attempted: it passed the pre-Go gates, then stopped
at `go: command not found`. The requester approved skipping that unavailable Go
smoke; it is not reported as passed.
