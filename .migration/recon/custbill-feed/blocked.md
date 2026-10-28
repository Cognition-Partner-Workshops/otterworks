# custbill-feed — merge-evidence recon BLOCKED

Batch c01, wave-custbill-1. Converted, deployed, and loaded; the merge-evidence
recon run could not execute on this box.

## What landed

- `etl/dbx-custbill/` bundle (target `mig_1793146609`): job `ow_tp_custbill_feed`
  deployed PAUSED (`0 10 2 * * ?`), tasks `ensure_objects` → `land_feed` on
  warehouse `565cd2fd713738c4`.
- Objects created: schema `ow_tp.ow_tp_custbill`, volume `custbill_drop`,
  Delta table `custbill_feed` (informational PK on `invoice_id`).
- Snapshot load: `custbill_extract.py` (converted Oracle month-end extract,
  `--ns demo` → batch_no 85559852) wrote `CUSTBILL_DEMO_ORACLE.dat` (byte-compat
  65-char CBCUST01) + `CUSTBILL_DEMO_ORACLE.feed` (keyed JSONL) → uploaded to
  the volume → `land_feed.sql` MERGE landed **18,750 rows / 18,750 distinct
  invoice_id**, `period_end` 2009-01-01..2025-12-28, `SUM(total_amt)` =
  187,618,458.58 — row count matches `ow_billing.invoice_header` for
  batch 85559852 (verified via REST statements API).
- Load is idempotent: `MERGE` on `invoice_id`; re-drops converge.

## Why recon did not run

`dbx-recon` connects to Databricks via `databricks-sql-connector`
(`recon/adapters.py::_databricks_connect`).

- With `DATABRICKS_CLIENT_SECRET` set (this env), the connector's
  `oauth_client_id`/`oauth_client_secret` kwargs fall into the interactive
  U2M authorize-code flow (waits on `localhost:8021` callback) — hangs.
- `auth_type="oauth-m2m"` + `client_id`/`client_secret` — also hangs.
- `access_token=<bearer>` works in ~1s (same warehouse, same principal). The
  harness reaches that path only through `_databricks_bearer()` (SDK env auth),
  which requires the env var combination `dbx_guard` hard-blocks as an
  identity swap (`DATABRICS_*=` manipulation around `dbx-recon`) — blocked
  per policy, not routed around.
- REST Statements API works throughout; connector 4.8.0 thrift session does not.

Fixture mode also fails closed: `AWS_ENDPOINT_URL` unset, no LocalStack.

## Blocker class (report, not fixed here)

`evidence` — no result.json could be produced. Expected residual blockers once
the connector is usable: `structural` (enforced source PK vs informational
Delta PK — unavoidable for this unit) and `rerun_policy`/`routine_parity`
unless rerun-proof + routine-parity records are produced.

## To unblock

Harness-side fix (protected): make `_databricks_connect` use SDK env auth
(`_databricks_bearer`) or `auth_type="oauth-m2m"` correctly. Wave-side:
allowlist whatever env path the fixed harness needs.
