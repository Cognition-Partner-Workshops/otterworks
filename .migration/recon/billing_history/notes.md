# w1-b01 billing_history — recon notes

## Verdict

`dbx-recon run --mode live --depth sampled` (tolerances `tol-20261027-v1`, oracle family):
**row parity PASS** on all data tiers (counts_through_mapping, per_field_aggregates,
keyed_diffs) across the five invoicing-history tables; `merge_eligible=false`, merge blocked
on class `structural` only.

Blockers (`merge_block_reasons`): `structural_gap`, `tier_failed`.

Tier 0 `structural_parity` findings (15): `grant_extra` x10, `primary_key_mismatch` x5 —
the Delta tables carry no primary keys (Delta has no enforced PK) and the target schema holds
grants absent from the Oracle source surface. These are platform-structural deltas between
Oracle and Delta, not row mismatches; tiers 1–3 (the data) are clean.

## Harness patch applied this run (required by brief)

- `recon/adapters.py::_uc_schema_facts`: `tp.grantee <> t.owner` → `tp.grantee <> t.table_owner`
  (this workspace's `information_schema.tables` exposes `table_owner`, not `owner`; the prior
  wave's `structural_gap`/`dictionary_unavailable` findings came from that defect and are now
  replaced by real structural reads).
- `recon/adapters.py::_databricks_connect`: `sql.connect(server_hostname=…, http_path=…,
  access_token=_databricks_bearer())` — oauth-m2m via the SDK-minted bearer (the connector's
  `oauth_client_id/secret` path hangs on an interactive U2M loop in 4.8.0). Patch lives in the
  local plugin cache; the harness plugin itself is read-only.

## Environment deltas this unit derived

- `DATABRICKS_HTTP_PATH` in the VM env points at a stopped/stale warehouse; all target ops
  override to `/sql/1.0/warehouses/565cd2fd713738c4` (Serverless Starter Warehouse, RUNNING).
  `--target-http-path` needs the full warehouse path; the bare id fails OpenSession.
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
- Merge-evidence run: `result.json` + `report.md` (this dir, live mode).
- Routine parity: `routine_runs/routine_parity.json` — 3/5 writers proven (golden = committed
  fixture parquet under `dbx/.../extract/fixture/`, observed = dedicated exec schema
  `ow_tp.billing_history_exec` loaded from the same fixture). `snapshot.customer_master` and
  `snapshot.invoice_line` are `unproven`: the contract's full-row-dict run records come to
  162MB / 183MB, over GitHub's 100MB file cap, so those two records could not be committed
  (unproven rows are carried, not blocking; same shape the prior wave-1b run reported).
- Rerun proof: `rerun/rerun_proof.json` — fresh `pass`, evolved `unsupported` with
  `nothing_evolved` (valid `first_run_baseline`); bound to the current job-source digest.
- Gate report: `.migration/recon/billing_history/w1-recon.report.json` — the manifest's
  declared gate path is manager-owned; the batch's write surface is
  `.migration/recon/<unit_id>/` only, so gate evidence lands here.

## Merge authority

`harness`. The committed wave manifest's `merge_overrides` covers
`[pkg_dunning, pkg_invoicing, pkg_ow_util, pkg_plans, pkg_rating]` only — not
`billing_history` — so no `human_override` applies. The structural gap stays open until a
plan decision resolves Delta-side PK/trigger/grant semantics for this unit.
