# Pipeline analysis: analytics

Boundary: `etl/` minus `etl/legacy-extra/` (custbill owns it) plus the analytics-service
Scala rollup (`services/analytics-service/src/main/scala/com/otterworks/analytics/batch/`).
`MarketSeeder` is excluded — a boot seeder, not a scheduled job. The `etl/` crontab has
exactly 5 entries; all 5 scheduled crons plus the CronJob are covered below. Coverage:
6/6 scheduled units, nothing skipped.

## Unit inventory

| unit | kind | schedule | reads | writes | target |
|---|---|---|---|---|---|
| `analytics_daily` | python cron | daily 02:00 UTC | SQS `otterworks-analytics`, DynamoDB `otterworks-analytics-events` | Postgres `analytics_daily_summary` upsert; S3 `otterworks-data-lake` summary + partitions | Lakeflow Job → `ow_tp.ow_tp_analytics.analytics_daily_summary` + `analytics_daily_report` |
| `audit_archive_weekly` | python cron | Sun 03:00 UTC | DynamoDB `otterworks-audit-events` | S3 GLACIER `otterworks-audit-archive` jsonl.gz + deletes + compliance report | Lakeflow Job → `ow_tp.ow_tp_analytics.audit_archive` + `audit_archive_report` |
| `search_reindex_weekly` | python cron | Sun 04:00 UTC | document-service + file-service REST, MeiliSearch | delete+recreate `documents`/`files` indices | Lakeflow Job → `ow_tp.ow_tp_analytics.search_index_docs` + `search_reindex_report` |
| `storage_cleanup_daily` | python cron | daily 02:30 UTC | S3 `otterworks-file-storage/files/`, DynamoDB `otterworks-file-metadata` | quarantine moves + savings report | Lakeflow Job → `ow_tp.ow_tp_analytics.storage_quarantine_actions` + `storage_cleanup_report` |
| `user_activity_daily` | python cron | daily 05:00 UTC | Postgres `otterworks_analytics`, S3 per-user files | S3 activity reports for admin-service | Lakeflow Job → `ow_tp.ow_tp_analytics.user_activity_report` |
| `usage_rollup_scala` | Scala K8s CronJob | nightly | `seed/usage-events.ndjson` (ROLLUP_INPUT) | `rollup-output.json` per-day rollup | Lakeflow Job → `ow_tp.ow_tp_analytics.usage_rollup` |

All six become Lakeflow Jobs with retries on serverless warehouse `565cd2fd713738c4`,
catalog `ow_tp`, schema `ow_tp_analytics`. Legacy snapshot outputs materialize to
`ow_tp.ow_tp_analytics_src` (same catalog, prefixed schema).

## Dependency crossings

- No Oracle dependency. No sibling write-target collision: invoicing writes Lakebase
  `ow-tp-billing` + `ow_tp.ow_tp_billing*`; custbill `ow_tp.ow_tp_custbill*`;
  analytics `ow_tp.ow_tp_analytics[_src]`. Disjoint.
- Shared fixture reads only: LocalStack (`AWS_ENDPOINT_URL`), Postgres fixture
  `otterworks_analytics`, MeiliSearch. Reads don't collide.
- `etl/config.ini` holds plaintext AWS keys — fake fixture creds; children must use
  `AWS_ENDPOINT_URL` + fixture keys, never real AWS.

## Parity mechanism (the one decision)

The estate rule says "dbx-recon --family oracle", but analytics has no Oracle objects.
Proposal: materialize each unit's legacy output once into `ow_tp.ow_tp_analytics_src`
(snapshot posture), then `dbx-recon --family databricks` catalog-to-catalog compare
against `ow_tp.ow_tp_analytics` on warehouse `565cd2fd713738c4`. Stays inside the
allowlist, uses a live-tested adapter, keeps recon as sole parity authority. If parent
prefers family postgres for the Postgres-sourced units, wave manifests can carry mixed
`source.family` — but one mechanism is simpler.

## Wave grouping

- **wave-analytics-1** (width 2, pilot): `usage_rollup_scala` (Scala batch pattern) +
  `analytics_daily` (python-cron pattern, most complex). Two pattern classes, one unit each.
- **wave-analytics-2** (width 4): remaining four python crons, one batch each.

derive_waves --check: both manifests consistent with the derived dependency order
(no inter-unit write/read edges — units are independent).
