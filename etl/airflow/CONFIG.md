# ETL configuration: `config.ini` to Airflow Connections and Variables

The DAGs never read `etl/config.ini`. Credentials and endpoints are Airflow **Connections**;
bucket names, prefixes, table and queue names and tunables are flat Airflow **Variables**,
named `<area>_<setting>` (shared buckets have no area prefix). Locally both come from
environment variables (`AIRFLOW_CONN_<ID>` / `AIRFLOW_VAR_<KEY>`, upper-cased) in the
untracked `etl/airflow/.env`, which `make airflow-up` creates from the committed
[`.env.example`](.env.example). Env-backed values are not stored in the metadata DB and do not
show in the UI lists; `airflow connections get <id>` / `airflow variables get <key>` resolve them.

## Local setup

```bash
make airflow-up             # creates etl/airflow/.env from .env.example if missing, then starts the stack
make airflow-config-check   # resolves every Connection/Variable in the scheduler and calls LocalStack, Postgres, MeiliSearch
```

Edit `etl/airflow/.env` (never `.env.example`) to point a local run elsewhere, then
`make airflow-up` again to recreate the containers. `etl/airflow/scripts/check_config.py static`
keeps this file, `.env.example` and the legacy scripts in step (run in CI).

## Reading values in a DAG

| Kind | How | Example |
| --- | --- | --- |
| Connection | provider hook with the conn id | `S3Hook(aws_conn_id="aws_default")`, `PostgresHook(postgres_conn_id="otterworks_postgres")`, `HttpHook(method="GET", http_conn_id="otterworks_meilisearch")` |
| String Variable | `Variable.get(key)` | `Variable.get("data_lake_bucket")` |
| Number / boolean Variable (JSON literal) | `Variable.get(key, deserialize_json=True)` | `Variable.get("audit_archive_delete_enabled", deserialize_json=True)` is `False` |

Read Variables inside tasks (or with Jinja `{{ var.value.<key> }}` / `{{ var.json.<key> }}`), not at
DAG parse time.

## Connections

| Conn id | Type | Replaces | Local value (dev only) | Notes |
| --- | --- | --- | --- | --- |
| `aws_default` | `aws` | `[aws] access_key`, `secret_key`, `region` and every inline `boto3` client | login/password `test`/`test`; extra `region_name=us-east-1`, `endpoint_url=http://localstack:4566` | Used by `S3Hook`, `SqsHook`, `DynamoDBHook`. Outside local, no keys: IRSA/instance role, or a secrets backend; drop `endpoint_url`. |
| `otterworks_postgres` | `postgres` | `[database] host`, `port`, `database`, `user`, `password` | `postgres:5432`, schema `otterworks`, `otterworks`/`otterworks_dev` (from `docker-compose.infra.yml`) | `PostgresHook`. Used by analytics (upsert `analytics_daily_summary`) and user activity (read it). |
| `otterworks_meilisearch` | `http` | `[services] meilisearch_url`, `meilisearch_api_key` | `http://meilisearch:7700`, empty password | The API key is the connection **password**; when set, send `Authorization: Bearer <password>` as the legacy script does. Local MeiliSearch runs without a master key. |
| `otterworks_document_service` | `http` | `[services] document_service_url` | `http://document-service:8083` (from `docker-compose.yml`) | Paged `GET /api/v1/documents?page=&size=`. Not part of the infra stack; start it with the app Compose or point the conn at a stub. |
| `otterworks_file_service` | `http` | `[services] file_service_url` | `http://file-service:8082` (from `docker-compose.yml`) | Paged `GET /api/v1/files?page=&page_size=`. Same note as above. |

## Variables

### Shared buckets (`[s3]` section)

| Variable | Replaces | Local value | Used by |
| --- | --- | --- | --- |
| `data_lake_bucket` | `[s3] data_lake_bucket` | `otterworks-data-lake` | analytics (partitions, report), storage cleanup (report), user activity (reads partitions, writes reports) |
| `file_storage_bucket` | `[s3] file_storage_bucket` | `otterworks-file-storage` | storage cleanup (listed and cleaned) |
| `quarantine_bucket` | `[s3] quarantine_bucket` | `otterworks-file-quarantine` | storage cleanup (orphans copied here) |
| `archive_bucket` | `[s3] archive_bucket` | `otterworks-audit-archive` | audit archive (archive and compliance report) |

### `otterworks_analytics_etl` (`analytics_daily.py`)

| Variable | Replaces | Local value |
| --- | --- | --- |
| `analytics_prefix` | `[s3] analytics_prefix`; also the `analytics/daily` literal in `user_activity_daily.py` | `analytics/daily` |
| `analytics_report_prefix` | literal `reports/analytics/daily` (report key) | `reports/analytics/daily` |
| `analytics_report_top_users` | literal `5` (`most_active_users` length) | `5` |
| `analytics_sqs_queue_name` | hardcoded `sqs_queue_url` (real-AWS URL with an account id) | `otterworks-analytics` |
| `analytics_sqs_max_messages` | `max_messages = 10000` | `10000` |
| `analytics_sqs_batch_size` | `batch_size = 10` (`MaxNumberOfMessages`) | `10` |
| `analytics_sqs_wait_time_seconds` | `WaitTimeSeconds=5` | `5` |
| `analytics_sqs_max_consecutive_errors` | literal `3` (give up after N receive failures) | `3` |
| `analytics_dynamodb_table` | `dynamodb_table_name = "otterworks-analytics-events"` | `otterworks-analytics-events` |

The queue is configured by name; the DAG resolves its URL through `SqsHook` (`get_queue_url`), so
no account id or region is baked into config.

### `otterworks_audit_archive` (`audit_archive_weekly.py`)

| Variable | Replaces | Local value |
| --- | --- | --- |
| `audit_archive_dynamodb_table` | `dynamodb_table_name = "otterworks-audit-events"` | `otterworks-audit-events` |
| `audit_archive_retention_days` | `retention_days = 90` | `90` |
| `audit_archive_s3_prefix` | `s3_prefix = "audit-archive"` | `audit-archive` |
| `audit_archive_storage_class` | `StorageClass="GLACIER"` (also reported as `archive_storage_class`) | `GLACIER` |
| `audit_archive_report_prefix` | literal `reports/compliance/audit-archive` | `reports/compliance/audit-archive` |
| `audit_archive_delete_batch_size` | `dynamodb_batch_size = 25` | `25` |
| `audit_archive_delete_enabled` | *new* (legacy always deletes archived events from DynamoDB) | `false` |

`audit_archive_delete_enabled` (decided default `false`): while false the DAG archives and reports
but leaves the source items in DynamoDB. Set it to `true` to restore the legacy delete pass; parity
runs against the legacy goldens need `true`.

### `otterworks_search_reindex` (`search_reindex_weekly.py`)

| Variable | Replaces | Local value |
| --- | --- | --- |
| `search_reindex_documents_index` | `documents_index = "documents"` | `documents` |
| `search_reindex_files_index` | `files_index = "files"` | `files` |
| `search_reindex_api_page_size` | `api_page_size = 100` | `100` |
| `search_reindex_bulk_batch_size` | `bulk_batch_size = 500` | `500` |
| `search_reindex_task_timeout_seconds` | literal `60` (delete/create/settings task polling) | `60` |
| `search_reindex_bulk_task_timeout_seconds` | literal `120` (document batch task polling) | `120` |

### `otterworks_storage_cleanup` (`storage_cleanup_daily.py`)

| Variable | Replaces | Local value |
| --- | --- | --- |
| `storage_cleanup_files_prefix` | `files_prefix = "files/"` | `files/` |
| `storage_cleanup_metadata_table` | `dynamodb_table_name = "otterworks-file-metadata"` | `otterworks-file-metadata` |
| `storage_cleanup_quarantine_prefix` | `quarantine_prefix = "quarantined"` | `quarantined` |
| `storage_cleanup_report_prefix` | literal `reports/storage-cleanup` | `reports/storage-cleanup` |
| `storage_cleanup_price_per_gb_month_usd` | literal `0.023` (`estimated_monthly_savings_usd`) | `0.023` |
| `storage_cleanup_normalize_keys` | *new* (legacy compares `s3_key` to object keys as exact strings) | `false` |

`storage_cleanup_normalize_keys` (decided default `false`): false keeps the legacy exact-string
match, so a metadata `s3_key` with a leading `/`, an `s3://bucket/` URI or different case does not
protect its object (the `reference_mismatches` golden). True lets the DAG normalize `s3_key` before
matching; that is an accepted difference from the goldens, opt-in only.

### `otterworks_user_activity_report` (`user_activity_daily.py`)

| Variable | Replaces | Local value |
| --- | --- | --- |
| `user_activity_lookback_days` | `lookback_days = 30` | `30` |
| `user_activity_report_prefix` | `s3_reports_prefix = "reports/user-activity"` | `reports/user-activity` |
| `user_activity_max_user_summaries` | literal `500` (`user_summaries` cap) | `500` |
| `user_activity_top_users` | literal `20` (`top_users` length) | `20` |

The per-day partitions it reads are under `analytics_prefix` (legacy hardcodes `analytics/daily`,
the same value).

## Stays in code

Output contracts the parity goldens pin, not tunables: object names inside a prefix
(`summary.json.gz`, `hourly_breakdown.json.gz`, `top_users.jsonl.gz`, `audit_events.jsonl.gz`,
`report.json`, `activity_report.json`, `user_summaries.jsonl`, `latest/`), the partition layouts
(`year=/month=/day=`, `year=/week=`), report field names, the DynamoDB scan filters and projections,
the MeiliSearch index settings (searchable/filterable attributes) and the service API paths and
paging parameter names.

## Where the local values come from

No value is copied from `etl/config.ini`. Credentials and hosts come from
`docker-compose.infra.yml` (Postgres `otterworks`/`otterworks_dev`, LocalStack `test`/`test`,
`us-east-1`) and `docker-compose.yml` (service ports); bucket, table and queue names from
`scripts/localstack-init.sh` and the golden harness (`etl/tests/golden/harness/settings.py`), which
creates `otterworks-analytics`, `otterworks-analytics-events`, `otterworks-file-storage` and
`otterworks-file-quarantine` that `localstack-init.sh` does not. Some of these non-secret names
equal the ones in `config.ini` because both describe the same resources; `check_config.py static`
fails if any credential, database host/name/user or API key from `config.ini` appears in this
directory.
