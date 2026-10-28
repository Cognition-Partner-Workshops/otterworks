# w1-b01 billing_history — recon notes

## Verdict (final run, patched harness)

`dbx-recon run --mode live --depth sampled` (tolerances `tol-20261027-v1`, oracle family):
**row parity PASS** on all row tiers (counts_through_mapping, per_field_aggregates,
keyed_diffs) across the five invoicing-history tables; `merge_eligible=false`, merge
blocked on class `structural`.

The brief's two local plugin patches were applied to the session's harness copy of
`recon/adapters.py` (`tp.grantee <> t.table_owner`; `sql.connect(..., access_token=
_databricks_bearer())`). With those, the grants probe reads cleanly: checks now report
constraints=checked, triggers=checked, sequences_identity=checked, grants=direct_only
(indexes=unsupported, an access path). The structural blocker remains as REAL findings,
verbatim:

- `primary_key_mismatch` x5 — source PK exists but the Delta tables declare no
  informational PRIMARY KEY: customer_master (cust_id), customer_master_hist (hist_id),
  entity_attr_value (eav_id), invoice_header (invoice_id), invoice_line (line_id).
- `grant_extra` x10 — two target grantees with no source counterpart on all five
  tables: `2e90bc1d-e9a1-4703-8c48-ad28ebb1864d` (all_privileges) and
  `bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d` (modify,select).

Blockers (`merge_block_reasons`): `structural_gap`, `tier_failed` (both class
`structural`). Reported verbatim per the brief; `mo-invoicing-w1-structural` not widened
(it covers only the five packages, not billing_history).
## Harness defect (superseded by the patched harness)

The earlier run's `dictionary_unavailable` hole was a harness defect
(`_uc_schema_facts` referenced `t.owner`; UC names it `table_owner`, and
`sql.connect(oauth_client_*)` drives interactive U2M that hangs headless).
Both are patched in this session's harness copy per the brief; the clean probe
now returns real grants rows and the residual blocker is real findings, above.
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
- Gate report: `.migration/recon/wave-invoicing-1/w1-b01/report.json`.
