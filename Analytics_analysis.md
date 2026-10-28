# Pipeline 3 analysis — analytics ETL crons + usage-rollup → Lakeflow Jobs

Run branch `mig-ow-tp-billing-20261028`, ticket UNT16-14 (plan step s-an-analyze). Target namespace `ow_tp.ow_tp_analytics` (exists). Orchestration target already decided: Lakeflow Jobs, `ow_tp_` prefix, PAUSED schedules, retries (`target-orchestration`). Load posture `snapshot`, run_mode `live`, guard_mode `block`.

## 1. Scope

**In scope (pinned):** the five `etl/scripts/` crons scheduled in `etl/crontab` (`0 2 * * * analytics_daily.py`, `30 2 * * * storage_cleanup_daily.py`, `0 3 * * 0 audit_archive_weekly.py`, `0 4 * * 0 search_reindex_weekly.py`, `0 5 * * * user_activity_daily.py`, all run via `/opt/etl/run.sh` + `etl/config.ini`) and the Scala batch rollup `UsageRollupJob` (`services/analytics-service`, K8s CronJob `0 2 * * *`, `infrastructure/helm/analytics-service/templates/cronjob.yaml`, `docs/BATCH-USAGE-ROLLUP.md`, `scripts/run-usage-rollup.sh`). Reference doc: `etl/ETL_UPGRADE_GUIDE.md` on `tech-partnerships`.

**Explicitly out of scope:** `etl/legacy-extra/` CUSTBILL chain (pipeline 2 / UNT16-9 scope); `services/legacy-billing/db/oracle/` OW_BILLING packages + tables (pipeline 1 / UNT16-4); wave-0 shared objects (`tenants`, `codes`, `customer_master` — already migrated, owned by invoicing; analytics does not read them); `market_*` tables in `V2__create_market_margin_tables.sql` (margins dashboard OTD-15, different consumer family); dunning-risk ML scoring (UNT16-20).

No Oracle/SQL objects are touched by this pipeline: every legacy read/write is SQS, DynamoDB, S3, Postgres, MeiliSearch, or an HTTP service API.

## 2. Unit inventory

| Unit | Source (routine) | Schedule | Workload | Reads | Writes | Cx | Shared | Dialect risks |
|---|---|---|---|---|---|---|---|---|
| `analytics_daily` | `etl/scripts/analytics_daily.py` (452 ln) | daily 02:00 | Python/boto3+pandas batch | SQS `otterworks-analytics` (long-poll≤10k, deletes), DynamoDB `otterworks-analytics-events` (scan `begins_with(event_date,:ds)`) | S3 `otterworks-data-lake` `analytics/daily/y/m/d/{summary,hourly_breakdown,top_users}`, `reports/analytics/daily/<ds>/report.json`; PG `otterworks_analytics.analytics_daily_summary` (upsert) | M | writer of objects `user_activity_daily` reads | pandas in-mem; hardcoded creds in config.ini; deletes SQS msgs; `except: pass` paths |
| `storage_cleanup_daily` | `etl/scripts/storage_cleanup_daily.py` (217 ln) | daily 02:30 | Python/boto3 sweep | S3 `otterworks-file-storage/files/` (paginated list), DynamoDB `otterworks-file-metadata` (scan s3_key) | S3 `otterworks-file-quarantine/quarantined/<ds>/` (copy), **DELETE on `otterworks-file-storage` (legacy write)**, `reports/storage-cleanup/<ds>/report.json` | S | file-storage bucket + file-metadata table are written by file-service (non-migrating) | destructive delete; data-consistent pairing copy→delete |
| `user_activity_daily` | `etl/scripts/user_activity_daily.py` (255 ln) | daily 05:00 | Python/boto3+psycopg2 rollup | PG `analytics_daily_summary` (30d lookback), S3 `analytics/daily/*/top_users.jsonl.gz` (30d; missing days silently skipped) | S3 `reports/user-activity/<ds>/{activity_report,user_summaries}`, `reports/user-activity/latest/activity_report.json` (admin pointer) | S | consumes `analytics_daily` outputs | silent-skip semantics must be preserved; `latest/` pointer contract |
| `audit_archive_weekly` | `etl/scripts/audit_archive_weekly.py` (224 ln) | weekly Sun 03:00 | Python/boto3 retention sweep | DynamoDB `otterworks-audit-events` (items >90d) | S3 `otterworks-audit-archive/audit-archive/year=/week=<ds>/audit_events.jsonl.gz` (GLACIER), **batch DELETE on `otterworks-audit-events` (legacy write)**, `reports/compliance/audit-archive/<ds>/report.json` | S | audit-events table written by audit-service (non-migrating) | destructive delete; 90-day retention is a compliance contract |
| `search_reindex_weekly` | `etl/scripts/search_reindex_weekly.py` (319 ln) | weekly Sun 04:00 | Python/requests+MeiliSearch | HTTP `document_service_url/api/v1/documents` (page), `file_service_url/api/v1/files` (page) | MeiliSearch `documents` + `files` indices (delete+recreate, settings patch, 500-doc bulk; `numberOfDocuments` assert else exit 1) | S | indices read by search path (non-migrating consumers) | index drop+recreate is a destructive swap on a shared service; no AWS creds — plain requests |
| `usage_rollup` | `UsageRollupJob.scala` main→`EventLoader`→`UsageRollupAggregator` | CronJob daily 02:00 (Forbid, backoffLimit 2, deadline 300s) | Scala JVM batch (pure aggregation) | NDJSON file `ROLLUP_INPUT` (default `/seed/usage-events.ndjson`); durable backstop: PG `analytics_events` (V1 flyway) — INFERRED feed path | file `ROLLUP_OUTPUT` (`/var/lib/otterworks/usage-rollup.json`, emptyDir — ephemeral) | S | none | output lands on an ephemeral volume (no durable consumer); only `generatedAt` is nondeterministic — fully deterministic fixture exists (165 events → 3 identical rollups, `scripts/generate_seed_events.py`) |

Cx = complexity (S small / M medium). All six units are single-script jobs — no routines call other routines (`calls: []`).

## 3. Dependency DAG (unit level)

```
analytics_daily ──writes──▶ analytics_daily_summary (PG) + analytics/daily/* (S3)
                                   │  read by
                                   ▼
                          user_activity_daily ──▶ reports/user-activity/* (S3)
storage_cleanup_daily    (independent leaf)
audit_archive_weekly     (independent leaf)
search_reindex_weekly    (independent leaf)
usage_rollup             (independent leaf)
```

One intra-pipeline edge (D1): `user_activity_daily` **depends_on** `analytics_daily`. The 02:00→05:00 cron stagger encodes this edge; the Lakeflow Job must preserve it (task ordering or job dependency).

## 4. Field/type dictionary (written objects)

`otterworks_analytics.analytics_daily_summary` → `ow_tp.ow_tp_analytics.analytics_daily_summary` — FACT from the upsert column list (no repo DDL exists; provisioning is external):

| Column | Source type | Target | Risk |
|---|---|---|---|
| report_date (PK) | DATE | DATE | — |
| active_users, active_documents, active_files, total_events, documents_created, documents_edited, comments_added, files_uploaded, files_shared, files_deleted | INT | BIGINT | counts — exact match required |
| bytes_uploaded | BIGINT | BIGINT | numeric overflow-safe |
| updated_at | TIMESTAMPTZ | TIMESTAMP | **nondeterministic** (written on load — exclude from parity compare) |

`otterworks_analytics.analytics_events` (V1 flyway; source store for rollup) → `analytics_events`: `id` BIGSERIAL→BIGINT, `event_id` VARCHAR(64)→STRING (UNIQUE), `event_type`/`resource_type` VARCHAR(64), `user_id`/`resource_id` VARCHAR(128), `metadata` TEXT(json)→STRING, `occurred_at` BIGINT **epoch-nanos** (unit rule `unit:epoch-ns` — not a timestamp; do not cast blindly). `analytics_daily_metrics` (V1) is the service-side materialized aggregate, kept in sync on write — noted but outside the rollup job's write set.

`usage_rollup_daily` (from `DailyUsageRollup`/`UsageRollupReport`): `date` ISO-str→DATE; `total_events, active_users, documents_created, documents_viewed, documents_edited, files_uploaded, files_downloaded, collab_sessions, storage_allocated_bytes, storage_released_bytes, net_storage_bytes` LONG→BIGINT; report wrapper `windowStart/windowEnd/dayCount/totalEvents/generatedAt` — `generatedAt` nondeterministic, exclude. `metadata["bytes"]` parses `.toLong` with try→0 — **data-risk**: malformed bytes silently zero on legacy; parity needs the same coercion.

Document-index fields (`documents` index): `id,title,content,owner_id,tags,type,created_at,updated_at`; `files` index: `id,name,owner_id,mime_type,folder_id,size,tags,type,created_at,updated_at` — FACT from the index-payload code; timestamp fields are epoch-ms — numeric, not timestamps.

DynamoDB items are schemaless — INFERRED key sets: `otterworks-analytics-events` {`event_date` (S, partition), `eventType|event_type`, `userId|ownerId|editedBy|authorId|deletedBy`, `documentId`, `fileId`, `sizeBytes`, `timestamp`}; `otterworks-file-metadata` {`s3_key` + file-service attrs}; `otterworks-audit-events` {`event_id`, `timestamp`, audit attrs}. These shape the snapshot-extract DDL, not Delta columns directly.

S3 report payloads (`report.json`, `activity_report.json`, `user_summaries.jsonl`, `summary/hourly_breakdown/top_users` gz) are file contracts — field-level dict lives in the recon row's compare projection; mark all report `generated_at/created` timestamps nondeterministic.

## 5. Dependency register (D-class crossings)

| # | Crossing | Class | Contract / decision needed | Status |
|---|---|---|---|---|
| 1 | `user_activity_daily`→`analytics_daily` outputs | D1 | `depends_on` edge; cron stagger 02:00→05:00 must become task/job ordering | done — in DAG |
| 2 | SQS `otterworks-analytics` + DynamoDB `otterworks-analytics-events` fed by app producers (non-migrating) | D3 | recommend `federate` (read-only snapshot); producers keep writing legacy | **decision** (important, unselected) |
| 3 | document-service + file-service HTTP APIs (non-migrating services) | D3 | recommend `federate` — read-only API snapshot into the job | **decision** |
| 4 | admin-service reads `reports/user-activity/latest/activity_report.json` — INFERRED (key convention; no repo code reference found) | D4 | per `target-consumer`: no repoint this run → `dual` (dual-publish during coexistence) | **decision** |
| 5 | MeiliSearch `documents`/`files` indices consumed by search path | D4 | per `target-consumer`: defer repoint; `dual` publish while parked | **decision** |
| 6 | crontab + K8s CronJob → Lakeflow Jobs | D5 | `jobs` — already selected (`target-orchestration`) | done |
| 7 | `otterworks-file-storage` objects + `otterworks-file-metadata` written by file-service; migrated unit quarantines+deletes | D6 | recommend `legacy` (legacy stays writer, federated read) + `legacy_write_authorized` for deletes | **decision + blocker** |
| 8 | `otterworks-audit-events` written by audit-service; migrated unit deletes archived items | D6 | same: `legacy` + `legacy_write_authorized` | **decision + blocker** |
| 9 | S3 report-file contracts (`report.json`, `latest/` pointer, `audit-archive` layout) handed to non-migrating consumers | D7 | `preserve` the byte-shape contract | **decision** |
| 10 | 90-day audit retention → compliance archive | D8 | `uc` — reproduce retention + grant surface in UC before consumers repoint | **decision** |
| 11 | Fixture/store access: `AWS_ENDPOINT_URL` LocalStack (allowed), MeiliSearch masterKey, service API URLs, PG DSN for `otterworks_analytics`; DynamoDB `otterworks-analytics-events`, `otterworks-audit-events`, `otterworks-file-storage/-quarantine/-audit-archive` buckets and the analytics PG DB are **not seeded** by `make seed-legacy` (only `otterworks-file-metadata`, `otterworks-data-lake/events/<ns>`, doc schemas are) | D10 | `fire` — seed/credentials request; recon for unseeded sources runs snapshot-of-live-extract or waits for seeding | **blocker** (`{kind: secret}`×N + sample-data) |
| 12 | Source family ≠ oracle: every analytics source is DynamoDB/S3/HTTP/PG/file; `dbx-recon --family oracle` (UNT16-17 title) does not cover them; capabilities list `postgres` recon driver unproven | D10 | `fire` — recon path = snapshot extract → `recon.legacy_*` tables; verify postgres driver or materialize-all | **blocker** (check: driver/fixture) |

## 6. Waves and batches (derive_waves output attached: `/tmp/waves-analytics.json` → committed under analysis evidence)

`derive_waves.py --namespace ow_tp.ow_tp_analytics --batch-max 5` (wave-0 units `tenants/codes/customer_master` stripped — already migrated):

| Wave | Batch | Units | Why |
|---|---|---|---|
| wave-analytics-1 | w1-b01 | `analytics_daily`, `audit_archive_weekly`, `search_reindex_weekly` | depth-0 leaves |
| | w1-b02 | `storage_cleanup_daily`, `usage_rollup` | depth-0 leaves |
| wave-analytics-2 | w2-b01 | `user_activity_daily` | depends on `analytics_daily` |

Width ≤ 3 per batch (under fan-out 5 cap). Legacy-write units sit in separate batches so the `legacy_write_authorized` blocker gates them cleanly.

## 7. Recon plan (size-aware rows)

Tolerance contract `tol-20261027-v1` (threshold 5,000,000 / sample 100,000 / abs 0.0 / rel 1e-9 / src-concurrency 4). All analytics sources are far below threshold → full compare, no sampling.

| Unit | Gates | Source posture | Sampling/threshold | Determinism rule | Projected legacy load | Cap check |
|---|---|---|---|---|---|---|
| `analytics_daily` | row_parity `analytics_daily_summary`; doc-parity on day-partition reports | snapshot: DynamoDB scan + PG extract → `recon.legacy_*` | full (<5M) | exclude `updated_at`; SQS delete side-effect excluded | 1 table scan + 1 day-partition scan/run | ok |
| `storage_cleanup_daily` | set-parity file list vs metadata; quarantine membership | snapshot: S3 listing + DynamoDB scan → `recon.legacy_*` | full | report timestamps excluded | 2 paginated scans | ok |
| `user_activity_daily` | row_parity + report-parity on 30-day window | snapshot: target-side vs legacy-run outputs (reads converted tables) | full | `latest/` pointer compared as file bytes | 30 small file reads | ok |
| `audit_archive_weekly` | archive-set parity + retained-set parity | snapshot: DynamoDB scan → `recon.legacy_audit_events` | full | week boundary pinned to run date | 1 scan | ok |
| `search_reindex_weekly` | doc-count parity + sample-doc field parity per index | snapshot: API page dumps → `recon.legacy_*` | sample ≤100k (tiny in practice) | index settings compared by config | 2 paginated API reads | ok |
| `usage_rollup` | byte/JSON parity vs checked-in expected output (165 events → 3 identical days) | fixture file (deterministic; no source DB) | full | compare excludes `generatedAt` | none — static fixture | ok |

## 8. Risks / findings for the plan

1. **Two units destroy legacy data** (S3 object deletes; DynamoDB batch deletes). `legacy_write_authorized` entries must exist in `.migration/authorizations.json` before their batches run — carried as plan blockers with `important: true, selected: null`. Snapshot-posture execution keeps them inert until authorized.
2. **Recon family mismatch** — sources are DynamoDB/S3/HTTP/PG, not Oracle; the `postgres` recon driver is unproven in capabilities. Plan blocker to materialize extracts or prove the driver before UNT16-17.
3. **Fixture gaps** — `otterworks-analytics-events`, `otterworks-audit-events`, `otterworks_analytics` PG, file-storage/quarantine/audit-archive buckets, the SQS queue and MeiliSearch are unseeded; `make seed-legacy` covers only `otterworks-file-metadata`, `otterworks-data-lake/events/<ns>`, doc schemas. D10 sample-data/access requests fired.
4. **usage_rollup writes to ephemeral emptyDir** — the "output" has no durable consumer; converted job should land `usage_rollup_daily` as a Delta table (schema above) — flag as INFERRED contract, confirm at plan.
5. **MeiliSearch index rebuild is a shared-service destructive swap** — converted unit must write to target-side index/table, never the legacy Meili instance.
6. `config.ini` carries hardcoded AWS creds and plaintext service URLs/keys — secrets by name only on target.
7. Silent-skip semantics (`user_activity_daily` missing-day `except: pass`; `bytes` parse try→0) are behavior, not bugs — must be preserved for parity.
