# w1-b01 billing_history — recon notes

## Verdict

`dbx-recon run --mode live --depth sampled` (tolerances `tol-20261027-v1`, oracle family):
**row parity PASS** on all tiers (counts_through_mapping, per_field_aggregates, keyed_diffs)
across the five invoicing-history tables; `merge_eligible=false`, merge blocked on class
`structural` only.

Blockers (`merge_block_reasons`):

- `structural_gap` — `structural_parity` tier could not read `information_schema.table_privileges`
  for any of the five target tables (ServerOperationError → `dictionary_unavailable` per table).
- `warnings` — the five UNVERIFIED structural warnings that follow from the same read failure.

## Harness defect (root cause of the structural blocker)

`recon/adapters.py::_uc_schema_facts` joins
`information_schema.table_privileges tp JOIN information_schema.tables t ...` on the target
catalog and references `t.owner`. This workspace's `information_schema.tables` has no `owner`
column (Databricks names it `table_owner`), so the grants read raises UNRESOLVED_COLUMN →
`dictionary_unavailable` for every object → `structural_gap`. Platform-side hole, not a data
mismatch; the harness plugin is read-only so it cannot be patched in-session. Same defect hit
by batch c01 of wave-custbill-1 (PR #2290 notes).

## Other environment deltas this unit derived

- `databricks-sql-connector` 4.8.0 has no oauth-m2m client_credentials path in `sql.connect`
  (hangs waiting for interactive U2M at localhost:8021). `recon_wrap.py` shims
  `credentials_provider=lambda: cfg.authenticate` from the SDK `Config()`, preserving the
  declared SP identity `d9d1c4ec-…` — no env stripping, no identity swap.
- `DATABRICKS_HTTP_PATH` in the VM env points at a stopped/stale warehouse; all target ops
  override to `/sql/1.0/warehouses/565cd2fd713738c4` (Serverless Starter Warehouse, RUNNING).
- Committed `mapping_spec.json` objects carry 3-part `object` names
  (`ow_tp.ow_tp_invoicing_history.<t>`, needed by the workflow's write-target collision check);
  `DatabricksTargetAdapter._q`/`quote_ident` requires bare names → derived
  `.migration/recon/billing_history/mapping_spec.normalized.json` (same version/keys, bare
  objects; catalog/schema enforced by `--target-catalog`/`--target-schema` + allowlist).
- `databricks fs cp` needs the `dbfs:` scheme on `/Volumes/...` and the parent dir must exist;
  `fs mkdirs dbfs:/Volumes/.../<dir>` first.
- The dbx-migration-factory guard blocks shell expansion (`$var`, `for` loops) inside command
  strings it parses as SQL-adjacent — upload/copy commands must be fully literal.

## Evidence produced

- Fixture-first run: `.migration/recon/billing_history/fixture_run/` (parity PASS — fixture
  evidence is never merge-eligible).
- Merge-evidence run: `result.json` + `report.md` + `recon.summary.md` (this dir, live mode).
- Routine parity: `routine_parity.json` — 3/5 writers proven, run records in `routine_runs/`
  (golden = committed fixture parquet under `dbx/.../extract/fixture/`, observed = dedicated
  exec schema `ow_tp.billing_history_exec`). `snapshot.customer_master` and
  `snapshot.invoice_line` are `unproven`: the contract's full-row-dict run records come to
  162MB / 183MB, over GitHub's 100MB file cap — the remote refused the push, so those two
  records could not be committed (unproven rows are carried, not blocking, per the harness's
  `parity_missing` rule; same shape batch c01 reported).
- Rerun proof: `rerun/rerun_proof.json` — fresh `pass`, evolved `unsupported` with
  `nothing_evolved` (valid `first_run_baseline`); bound to the current job-source digest.
- Gate report: `.migration/recon/billing_history/w1-recon.report.json` — the manifest declares
  `.migration/recon/wave-invoicing-1/w1-b01/report.json` as gate evidence, but the batch's write
  surface is `.migration/recon/<unit_id>/` only; a copy written to the declared path was removed
  by the wave owner (commit `ebe435a11`, "stray batch report.json outside unit recon dir"). The
  file inside the unit dir carries the same payload plus a `declared_path` note.
