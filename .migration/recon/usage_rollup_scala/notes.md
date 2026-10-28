# usage_rollup_scala recon notes (batch a01, wave-analytics-1 relaunch)

## Outcome

`mode=live depth=full`: parity PASS (3 rows both sides, keyed_diffs clean,
counts clean). `merge_eligible=false` — class `structural`:

- `grant_extra` x2: migration-side SP grants on
  ow_tp.ow_tp_analytics.usage_rollup (2e90bc1d-…, bc8a2ef7-…) have no
  source-side counterpart — catalog-inherited platform grants outside worker
  scope.
- `grant_missing`: the session SP (d9d1c4ec-…) appears as a grantee on the
  source staging table (all_privileges, select); on the target it is the
  table owner, so information_schema carries no grant row. Platform-inherent.

No committed `merge_overrides` entry covers this unit -> merge_authority harness.

## Fixture

Fixture-first fails closed: `fixture_endpoints` lists only `AWS_ENDPOINT_URL`;
no Databricks fixture endpoint exists for family `databricks` (source reads
as the session identity). Live run is the merge evidence.

## Evidence chain

- Deploy: `databricks bundle deploy -t mig_1793146609` from
  `etl/dbx-usage-rollup` (bundle `mig_1793146609_usage_rollup`, job
  `ow_tp_analytics_usage_rollup`, PAUSED schedule, per-task retries).
- Fresh leg: bundle run 316251899760649 on empty target (reset via
  `bin/reset_target.py`) — ensure_objects created schema+volume+table,
  rollup_load merged 3 day rows.
- Evolved leg: bundle run 288842258229958 over the landed table in committed
  DDL shape — MERGE converged; `rerun_proof.json` fresh pass / evolved pass.
- `routine_parity.json`: 0 proven, 2 unproven (no committed run records),
  0 failed.

## Review round 1 (PR #2296)

Three Devin Review bugs on `rollup_load.sql`, all real, fixed and re-proven:

1. Session-tz-dependent day bucketing
   (`CAST(from_utc_timestamp(..., 'UTC') AS DATE)`): replaced with
   `date_from_unix_date(floor(unix_timestamp(instant)/86400))` — epoch-based,
   session-timezone independent, matches `dateOf`'s UTC-day contract.
2. Epoch-millisecond timestamps dropped: legacy `instantFormat` accepts
   JsNumber as epoch ms; numeric `timestamp` strings now route through
   `timestamp_millis`, ISO strings through `to_timestamp`.
3. Snapshot semantics: legacy `run` rewrote the complete report per day-set;
   added `WHEN NOT MATCHED BY SOURCE THEN DELETE` so days absent from the
   current input are removed rather than retained stale.

Legs + rerun proof + recon run regenerated (digest bound to the new source).

## Harness workarounds needed (flag for plugin fix — same as prior attempt)

1. `recon/adapters.py` `_uc_schema_facts`: table_privileges join read
   `t.owner`; the column is `table_owner`. Patched in the local plugin-cache
   copy; verifier hits the same wall until the plugin is fixed.
2. `_databricks_connect` oauth-m2m (`oauth_client_id`/`oauth_client_secret`)
   hangs indefinitely at `sql.connect` in this environment. Runs used the
   supported `access_token` fallback: `DATABRICKS_TOKEN` minted in-process by
   `bin/recon_env.py` from the session SP via `databricks.sdk.core.Config()`,
   client vars emptied — same identity, no guard workaround.
3. Committed `mapping_spec.json` writes `object` as a 3-part
   `catalog.schema.table`; the Databricks target adapter requires a bare
   table name (it prefixes `--target-catalog --target-schema`). `run` was
   pointed at the normalized copy `mapping_spec.json` in this directory —
   same version/objects/keys, `object: usage_rollup`.
4. `dbx_guard` clears `databricks.sdk` calls carrying literal SQL on
   allowlisted catalogs — a generic `run_sql.py` with runtime-arg statements
   is blocked; per-statement literals or the harness's own commands are the
   sanctioned path.
5. `--canonicalization` is required; no committed databricks canon file
   exists — an empty `[]` ruleset is valid for this family.
