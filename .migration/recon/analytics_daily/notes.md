# analytics_daily — batch a02 (relaunch)

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
- Deployed + run as DE-shared SP: fresh run 895970208464476 (target after DROP TABLE), evolved run
  21125935139472 (rerun over the landed tables) — both TERMINATED SUCCESS. Job redeployed via
  `databricks bundle deploy -t mig_1793146609` (unchanged resources; job 553616700205369).
- Recon `run --mode live --depth full`: parity PASS (summary keyed report_date, report keyed s3_key;
  keyed diff, 2 rows), merge_eligible=false, blocker_classes [structural] (informational PK + SP grant
  visibility). cost: source 20 stmts/2 rows, target 18 stmts/2 rows, 12.868s.
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
