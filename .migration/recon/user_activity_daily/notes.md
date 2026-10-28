# user_activity_daily recon notes (batch a04, wave-analytics-2)

## Outcome

`mode=live depth=full`: parity PASS (29 rows both sides, keyed_diffs clean,
counts clean). `merge_eligible=false` — class `structural`:

- `grant_extra` x2: platform-side grants on
  ow_tp.ow_tp_analytics.user_activity_report (2e90bc1d-…, bc8a2ef7-…) have no
  source-side counterpart — catalog-inherited platform grants outside worker
  scope. Same shape as the wave-1 siblings (usage_rollup_scala, analytics_daily).
- `grant_missing`: the session SP (d9d1c4ec-…) appears as a grantee on the
  source staging table (all_privileges, select); on the target it is the
  table owner, so information_schema carries no grant row. Platform-inherent.

Unlike wave 1, the committed `.migration/waves/wave-analytics-2.json` carries
NO `merge_overrides` entry covering this unit -> merge_authority stays
`harness`; the override decision is the wave close's, not the worker's.

## Conversion surface

Legacy `etl/scripts/user_activity_daily.py` reads Postgres
`analytics_daily_summary` (30-day BETWEEN) plus per-day S3
`analytics/daily/year=<y>/month=<m>/day=<d>/top_users.jsonl.gz` (day_offset
0..29 -> file days in [ds-29, ds]) and rewrites the dated user-activity
report wholesale. Under the plan's `parity-mechanism` decision the inputs are
mirrored in `ow_tp.ow_tp_analytics_src`: `analytics_daily_summary` (Postgres
summary, feeds only report trends — outside the declared parity surface) and
`analytics_daily_report` rows carrying each top_users artifact's decompressed
JSONL in `report_json` keyed by the legacy s3 path (decision
`analytics-daily-artifacts=mirror`).

The declared parity surface `ow_tp_analytics_src.user_activity_report` covers
only the flattened per-user metric rows — so `run_user_activity.sql`
recomputes total_actions / active_days / actions_by_type.<type> from the
mirrored artifacts and merges `(report_date, user_id, metric)` rows; the
report-level `trends` and `daily_summaries` lists are not staged and are not
reproduced. `WHEN NOT MATCHED BY SOURCE AND tgt.report_date=:ds THEN DELETE`
matches legacy's wholesale rewrite of the dated report; other dates are
untouched. Missing days and unparseable keys skip silently, like legacy's
bare except; `user_id`/`total`/`actions` fall back to 'unknown'/0/{}.

## Fixture

Fixture-first fails closed as designed: `fixture_endpoints` lists only
`AWS_ENDPOINT_URL`; no Databricks fixture endpoint exists for family
`databricks` (source reads as the session identity). Fixture-run blockers
carried the expected `evidence`/`rerun_policy` classes (no attached
rerun_proof/routine_parity); the live run is the merge evidence.

## Evidence chain

- Deploy: `databricks bundle deploy -t mig_1793146609` from
  `etl/dbx-user-activity` (bundle `mig_1793146609_user_activity`, job
  `ow_tp_analytics_user_activity`, PAUSED quartz `0 0 5 * * ?` UTC,
  per-task retries: max_retries 2 / min_retry_interval 30s).
- Fresh leg: bundle run 255489704773403 on empty target (reset via
  `bin/reset_target.py`) — ensure_objects created schema+table,
  run_user_activity merged the ds=2026-10-28 metric rows.
- Evolved leg: bundle run 130087694869085 over the landed table in committed
  DDL shape — MERGE converged; `rerun_proof.json` fresh pass / evolved pass.
- `routine_parity.json`: 0 proven, 2 unproven (no committed run records),
  0 failed.

## Harness workarounds needed (flag for plugin fix)

1. `recon/adapters.py` `_databricks_connect`: with
   databricks-sql-connector 4.8.0, `credentials_provider` must be a callable
   returning the header factory, but the harness passes
   `Config().authenticate` itself — which returns a dict, so every
   sql.connect raises `'dict' object is not callable`. Patched in a local
   copy (`/home/ubuntu/harness-recon`): `credentials_provider=lambda:
   _databricks_sdk_config().authenticate`. The plugin cache is untouched;
   verifier hits the same wall until the plugin is fixed. (a01's
   t.owner->t.table_owner patch is already in the 0.6.1 cache.)
2. Committed `mapping_spec.json` writes `object` as a 3-part
   `catalog.schema.table`; the Databricks target adapter requires a bare
   table name (it prefixes `--target-catalog --target-schema`). `run` was
   pointed at the normalized copy `mapping_spec.json` in this directory —
   same version/objects/keys, `object: user_activity_report`.
3. `--canonicalization` is required; no committed databricks canon file
   exists — an empty `[]` ruleset is valid for this family.
