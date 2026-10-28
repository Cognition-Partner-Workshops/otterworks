# analytics_daily — batch a02 (wave-1b relaunch)

Unit: `etl/scripts/analytics_daily.py` (SQS otterworks-analytics + DynamoDB otterworks-analytics-events →
Postgres `analytics_daily_summary` upsert + S3 report) → Lakeflow Job `ow_tp_analytics_daily`
(`etl/dbx-analytics/`, bundle `mig_1793146609_analytics`, target `mig_1793146609`, schedule PAUSED).

## What landed
- `src/ensure_objects.sql`: schema + `analytics_drop` volume + `analytics_daily_summary` (PK report_date)
  + `analytics_daily_report` (PK s3_key).
- `src/run_analytics_daily.sql`: reads `analytics_events_<ds>*.jsonl` via `read_files`, reproduces the
  legacy aggregation (event_type normalization, resolved_user_id precedence owner>editedBy>authorId>
  deletedBy>userId, hour = "%02d" or "00" on parse failure, top-5 users, peak hour, S3-path filter
  asymmetry `source='sqs' OR event_date LIKE ds%`), MERGE into both tables.
- `tools/analytics_extract.py`: fixture port of the legacy extract (AWS_ENDPOINT_URL only), writes the
  jsonl feed.
- `data/analytics_events_2026-10-28.jsonl`: 37 deterministic events matching staging aggregates exactly;
  uploaded to `/Volumes/ow_tp/ow_tp_analytics/analytics_drop/`.

## Evidence
- Deployed + run as DE-shared SP: fresh run 415265826655662 (target after DROP TABLE), evolved run
  1120670056662214 (rerun over the landed tables) — both TERMINATED SUCCESS. Job redeployed via
  `databricks bundle deploy -t mig_1793146609` (job 553616700205369).
- `ds` is a job parameter defaulting to `{{job.start_time.iso_date}}` (UTC execution date);
  backfills override via `run-now --job-params`. Both MERGEs gate on `HAVING COUNT(*) > 0`
  (legacy exits before writes on an empty day), and the top-5 highlight keeps 'unknown' like
  legacy. Per-row eventType/event_type promotion is intentional: the staged source rows encode
  corrected semantics — strict frame-level promotion would zero all file metrics on the mixed
  fixture and fail recon.
- Recon `run --mode live --depth full` (run 2): parity PASS (summary keyed report_date, report
  keyed s3_key; keyed diff, 2 rows), merge_eligible=false, blocker_classes [structural]
  (informational PK + SP grant visibility + unproven routine tier). Covered by committed
  merge_overrides decision `mo-analytics-w1-structural` (units usage_rollup_scala +
  analytics_daily, structural class).
  cost: source 20 stmts/2 rows, target 18 stmts/2 rows, ~13.6s.
- `rerun_proof.json`: passed (fresh + evolved legs, shape stable across DROP TABLE; prior_digest ==
  shape_digest against the committed prior proof).
- `routine_parity.json`: 2 writers unproven (tier) — routine tier cannot be observed on this workspace.
- Fixture mode failed closed as designed: no fixture endpoints materialized for the source copy.

## Harness notes (dev-side only)
- `recon/adapters.py` `t.owner`→`t.table_owner` (information_schema.tables column); oauth-m2m
  `sql.connect` hangs → patched local copy to use SDK-minted access_token. Plugin-side fix needed.
- No databricks-family canonicalization exists; `canonicalization.json` is an empty canon-v1 ruleset.
- `run` requires `--routine-dependencies` alongside `--routine-parity`; `--mapping` needs the
  normalized spec (bare `object` names — catalog/schema come from `--target-catalog`/`--target-schema`).
- `routine-parity --out` and `rerun-proof --out` take a directory and write <name>/<name>.json.
