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

## Verify rerun (a02)
- Merge-evidence recon re-run on head b01e9ee81: parity FAIL, merge_eligible=false,
  blocker_classes [data, structural]. Tier0 structural_gap unchanged (informational PK +
  grant visibility). Tier1 root_count: staging `analytics_daily_report` mirrors only
  `report.json` (1 row); head emits report + hourly_breakdown + top_users (3 rows) per the
  close-review contract — the staging seed never mirrored the two artifact keys.
- New rerun_proof bound to head sources (digest e877b95f): fresh leg = DROP TABLE +
  ensure_objects + run_analytics_daily(ds=2026-10-28) on warehouse 565cd2fd713738c4;
  evolved leg = same script rerun over landed tables, MERGEs converged, shape stable.
- Bundle job run 580350719779334 FAILED INTERNAL_ERROR at extract_analytics_events:
  boto3 NoRegionError (fixture-only AWS_ENDPOINT_URL is absent on serverless); the real
  extract cannot run on this workspace — sql_task statements were executed directly.
- Fix in converted code: array_sort comparator `sign(...)` returns DOUBLE on this
  runtime; cast to INT.

## Verify rerun 2 (a02) — head b2947fa48 (artifact keys = legacy s3 path)
- Merge-evidence recon `run --mode live --depth full --seed 0`: parity PASS, merge_eligible=false,
  blocker_classes [structural] (structural_gap + warnings: informational PK, SP grant visibility).
  Covered by committed merge_overrides mo-analytics-w1-structural -> merge_authority human_override.
  Cost: source 20 stmts/4 rows, target 8 stmts/4 rows, 9.9s.
- Fixture mode run first: failed closed as designed (never merge-eligible).
- rerun_proof regenerated for head sources (digest 3a1addcf): fresh leg DROP TABLEs + ensure_objects +
  run_analytics_daily(ds=2026-10-28); evolved leg rerun over landed tables, MERGEs converged,
  shape digest identical to prior proof (90546c64) — schema unchanged, only s3_key values re-keyed.
- Execution path: each `aitools tools query` runs its own session, so the job's TEMP VIEWs were
  materialized as catalog-qualified views ow_tp.ow_tp_analytics.{analytics_events,analytics_artifacts},
  MERGE USING refs qualified, views dropped after; guard clears only catalog-qualified writes.
  Committed job file unchanged (sql_task runs the file in one session on the real job).
- Discrepancy for wave close: this head/branch (devin/1793151987-analytics-daily) tracks PR #2295;
  PR #2304 tracks devin/1793154552-wave1-a02-analytics-daily @ 0ec64f18 — a superseded wave-1b
  conversion without the artifact rows.
