# storage_cleanup_daily recon notes (batch a03, wave-analytics-2)

## Outcome

`mode=live depth=full seed=0`: parity **PASS** — tier1 counts clean
(orphan_files 8/8 -> storage_quarantine_actions keyed s3_key;
cleanup_report 15/15 -> storage_cleanup_report keyed metric), tier0/tier3
keyed diffs clean. `merge_eligible=false` — class `structural`:

- `grant_missing`/`grant_extra`: the session SP (d9d1c4ec-…) is a grantee on
  the staged source tables but the owner on the target tables, and the
  migration-side SP grants on the ow_tp targets have no source-side
  counterpart — catalog-inherited platform grants outside worker scope.
  Platform-inherent; identical to usage_rollup_scala / analytics_daily in
  wave 1.

The committed wave-analytics-2 manifest carries **no** `merge_overrides`
entry — `merge_authority` stays `harness`. Wave 1 covered this same blocker
class with `mo-analytics-w1-structural`; wave 2 needs its own override
entry or every a0x unit reports FAIL on structural even when rows match.

## Fixture

Fixture-first fails closed: `allowed_targets.json` `fixture_endpoints`
lists only `AWS_ENDPOINT_URL`; no Databricks fixture endpoint exists for
family `databricks` (source reads as the session identity). The live run
above is the merge evidence. No fixture run counted against the 3-run cap.

## Evidence chain

- Deploy: `databricks bundle deploy -t mig_1793146609` from
  `etl/dbx-storage-cleanup` (bundle `mig_1793146609_storage_cleanup`, job
  `ow_tp_analytics_storage_cleanup`, PAUSED schedule `0 15 3 * * ?` UTC,
  `max_retries: 2` per task, `ds` parameter `{{job.start_time.iso_date}}`).
- Input drop: committed `data/files_listing_2026-10-28.jsonl` +
  `data/metadata_keys_2026-10-28.jsonl` uploaded to UC volume
  `ow_tp.ow_tp_analytics.storage_drop` — the converted S3 listing +
  DynamoDB metadata-key snapshots. 33 listed objects / 692910 B; 8 orphans
  matching staged `orphan_files` sizes/key set exactly; the 25 referenced
  files are deterministic (staging constrains only the aggregates).
- Fresh leg: bundle run `173981612121368` on empty target —
  ensure_objects created schema+volume+tables, storage_cleanup_run merged
  8 ledger + 15 metric rows.
- Evolved leg: bundle run `824313334198383` over the landed tables in
  committed DDL shape — MERGE converged; `rerun_proof.json` fresh pass /
  evolved pass.
- `routine_parity.json`: 0 proven, 2 unproven (no committed run records),
  0 failed.
- `generated_at`/`quarantined_at`/`report_date`/`quarantine_key` embed the
  run date (`ds` = 2026-10-28 today, matching staging); `generated_at` is
  run-volatile by construction. Float metric_values cast through DOUBLE so
  `0.0000`-scale zeros print as `0.0`, matching legacy `str(round(x,4))`.

## Harness workarounds needed (flag for plugin fix)

1. `recon/adapters.py` `_databricks_connect`: `credentials_provider=
   Config().authenticate` is broken with sql-connector 4.8.0 / sdk
   0.157.0 — the connector calls `provider()` expecting a header
   *factory* and `authenticate()` returns a dict, so every request fails
   `'dict' object is not callable`. Patched the local plugin-cache copy
   with `lambda: _databricks_sdk_config().authenticate` (same SP
   identity; same shim a01's recon_env.py applies in-launcher).
2. `_uc_schema_facts` `t.owner` -> `table_owner` patch (from wave 1) is
   still present in this plugin-cache copy.
3. Ambient `DATABRICKS_HTTP_PATH` points at retired warehouse
   `890be8990bf134aa`; every recon subcommand needs
   `--target-http-path /sql/1.0/warehouses/565cd2fd713738c4`.
4. Committed `mapping_spec.json` writes `object` as a 3-part
   `catalog.schema.table`; the Databricks target adapter requires a bare
   table name — `run` used the normalized copy `mapping_spec.json` in
   this directory (same version/objects/keys).
5. `dbx_guard` clears literal `cur.execute("...")` statements in scripts
   under the unit recon dir; loop-built SQL in /tmp scripts is
   unresolvable and blocked.
6. `--canonicalization` is required; no committed databricks canon file
   exists — an empty `[]` ruleset is valid for this family.
