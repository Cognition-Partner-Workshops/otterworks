# Shared external-job runtime

`python -m lakehouse.runtime.external_settings --job JOB --business-date YYYYMMDD`
dispatches only the five legacy external job names, using argv rather than a shell.
User activity additionally requires `--source PATH` for its existing staged snapshot;
analytics requires `--ready PATH`. Existing domain module CLIs remain supported.

Settings default to `runtime/external.ini`. `ETL_CONFIG_PATH` accepts an existing
legacy-format INI path. Secrets never belong in that file. Analytics requires only
`ETL_DB_PASSWORD`; search requires only `ETL_MEILISEARCH_API_KEY`. The remaining
jobs require neither: activity reporting reads staged files, not live PostgreSQL/S3.
Nonblank injected environment values remain supported. Otherwise Secrets Manager
uses `otterworks/etl/<job-name-without-.py>`; `ETL_SECRET_ID` explicitly selects a
different secret and forces JSON validation. Each required field must be a nonblank
string. Provision per-job IAM and secret JSON before enabling schedules.

All S3-using entry points require `ETL_S3_BUCKET_OWNER`, exactly twelve ASCII digits.
Archive also accepts its existing `AUDIT_ARCHIVE_OWNER` / `--owner` override, with
the same validation. Every S3 request includes ExpectedBucketOwner, including
cleanup inventory listing and copy source ownership.

## Analytics

`lakehouse_analytics_daily` is paused, runs at `0 2 * * *` UTC, and maps logical
date to the previous BUSINESS_DATE. Its readiness sensor waits for:

```
.data/<NS>/readiness/analytics/<BUSINESS_DATE>.json
{"business_date":"20261109","status":"ready"}
```

The upstream operator/producer must attest source readiness; the runtime does not
manufacture that marker. A stale/malformed marker fails before settings or service
access. No live service is contacted by tests or parity fixtures.

Analytics retains legacy pandas aggregation, stable top-user ties, source order,
the bounded SQS receive behavior, and no deduplication between SQS and DynamoDB.
The five outputs are summary, hourly breakdown, top users, report, and the daily
PostgreSQL aggregate. Gzip headers and processing-time database `updated_at` are
not logical parity values. Report generated_at is deterministic business midnight.

The new safety contract is A-415: capture inputs in an atomic, fsynced extraction
journal before writing; overwrite deterministic S3 keys; upsert the database row;
only then acknowledge valid SQS messages. Database and acknowledgement failures
fail the task. A written-state checkpoint permits acknowledgement-only retry;
completed reruns are no-ops. New queue messages do not alter a captured extraction.
Malformed JSON messages are left unacknowledged, as in legacy.

Workers **must share durable namespace storage**, retain
`.data/<NS>/transactions/analytics/<BUSINESS_DATE>.json`, and not delete journals
to replay completed dates. Configuration and business-date source snapshots must
remain fixed during retries. There is no distributed S3/PostgreSQL transaction;
partial artifacts can be visible until retry succeeds. SQS remains at-least-once.

## Offline parity

The oracle imports the unchanged legacy script with actual pandas and injected
SQS, DynamoDB, S3 and PostgreSQL protocol fakes. Both engines receive independent
copies of the same persisted fixture; the oracle clock is pinned to BUSINESS_DATE.
Seven scenarios cover empty/malformed queues, pagination, cross-source duplicates,
field fallbacks, missing/mixed event fields, offset hours, decimal data and top-100
stable ties. PostgreSQL failures and deferred acknowledgement are deliberate safety
deviations tested separately, not hidden by parity normalization.

```
NS=sfx-d1110-after lakehouse/.venv/bin/python -m lakehouse.parity.analytics \
  --business-date 20261109 --fixture lakehouse/.data/sfx-d1110-after/fixtures/analytics/20261109.json --generate
NS=sfx-d1110-after LEGACY_NS=sfx-d1110-before lakehouse/.venv/bin/python -m lakehouse.parity run \
  --business-date 20261109 --spec platform.analytics_summary platform.analytics_hourly \
  platform.analytics_top_users platform.analytics_report platform.analytics_postgres
```

`lakehouse_analytics_fixture` exposes the same offline fixture → parity chain as a
paused manual DAG. It does not generate the production readiness attestation.
