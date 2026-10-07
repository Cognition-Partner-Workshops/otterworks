# Legacy ETL golden harness

Characterization snapshots of the five cron scripts in `etl/scripts/`, recorded
against local infrastructure only (LocalStack 3.8, Postgres 15, MeiliSearch
from `docker-compose.infra.yml`). The scripts are run **unchanged**; every
adaptation lives in the shim, so the goldens are the true legacy behavior that
the Airflow port must reproduce.

```bash
make infra-up                                        # or: docker compose -f docker-compose.infra.yml up -d --wait postgres localstack meilisearch
make etl-golden SCRIPT=analytics_daily MODE=check    # diff against the committed golden (default mode)
make etl-golden SCRIPT=analytics_daily MODE=record   # (re)record goldens, review with git diff
make etl-golden SCRIPT=all MODE=repeat               # run each scenario twice, require byte-identical snapshots
make etl-golden SCRIPT=all SCENARIO=smoke            # one scenario name across scripts
make etl-golden-test                                 # harness unit tests, no infra needed
```

Requires Docker and `uv` (the harness runs on Python 3.11; the legacy scripts
run in a Python 3.9 container with the pins from `etl/requirements.txt`).
**Reset wipes the contents of every bucket, table, queue and index in the local
stack** before each run.

## How a run works

1. **Infra and harness-only resources** (`harness/infra.py`): waits for the
   services, then creates what `scripts/localstack-init.sh` does not: SQS
   `otterworks-analytics`, DynamoDB `otterworks-analytics-events`
   (`event_id` hash key), buckets `otterworks-file-storage` /
   `otterworks-file-quarantine`, the dedicated Postgres database
   `otterworks_etl_golden` and `analytics_daily_summary`
   (`harness/sql/analytics_daily_summary.sql`, derived from the upsert in
   `analytics_daily.py`). The shared init scripts are not touched.
2. **Reset and seed** from `<script>/<scenario>/scenario.json` (schema in
   `harness/scenario.py`): SQS messages, DynamoDB items, S3 objects, Postgres
   rows and, for `search_reindex_weekly`, the document-service / file-service
   pages served by an in-process stub (`harness/stub_http.py`).
3. **Legacy runner** (`harness/runner.py`, `legacy/Dockerfile`): `docker run`
   of `/opt/etl/run.sh <script>.py`, the crontab command, with `run.sh`,
   `scripts/`, a generated `config.ini` (`harness/config_ini.py`, dev
   credentials and local endpoints only; the committed `etl/config.ini` is
   never used) and `legacy/sitecustomize.py` bind-mounted read-only under
   `/opt/etl`.
4. **Shim** (`legacy/sitecustomize.py`), picked up through run.sh's
   `PYTHONPATH=/opt/etl`:
   - injects the LocalStack endpoint into every boto3 client/resource
     (boto3 1.26 predates `AWS_ENDPOINT_URL`);
   - rewrites real-AWS SQS queue URLs, such as the one hardcoded in
     `analytics_daily.py`, to LocalStack;
   - freezes wall-clock time at the scenario's `frozen_time` with freezegun
     (`time.monotonic` stays real so polling loops still time out);
   - exits 97 if it cannot install, and the harness refuses any run whose log
     lacks the shim banner.
5. **Snapshot** (`harness/snapshot.py`) of every output surface, then
   **normalize** (`harness/normalize.py`) and compare/store.

## Golden files

`<script>/<scenario>/golden/`, one canonical JSON file per surface (sorted
keys, 2-space indent):

| file | content |
|---|---|
| `result.json` | process exit code |
| `s3.json` | every object of every bucket: body (gzip detected and decompressed; parsed JSON, JSON Lines as a list, text, or base64), `content_type`, `content_encoding`, `storage_class`, `metadata` |
| `dynamodb.json` | every table: key schema and all items in AttributeValue form, sorted by key |
| `sqs.json` | visible and in-flight message counts per queue |
| `postgres.json` | every table of `otterworks_etl_golden`: column names/types and rows ordered by primary key |
| `meilisearch.json` | every index: primary key, settings, stats and all documents sorted by primary key |

Container output goes to `.runs/<script>/<scenario>/run-N.log` (gitignored),
not into the golden.

## Normalizer

Only these values are replaced by `<normalized:NAME>`; everything else is
compared byte for byte:

- in S3 JSON / JSON Lines bodies, any `generated_at` that parses as ISO-8601,
  and any `duration_seconds` / `duration_ms` that is a number;
- the Postgres `analytics_daily_summary.updated_at` column (set by `NOW()` on
  the database clock), when it parses as ISO-8601.

A value of the wrong shape is left as is so it shows up as a diff.

## Adding a scenario

Create `<script>/<scenario>/scenario.json`, run
`make etl-golden SCRIPT=<script> SCENARIO=<scenario> MODE=record`, check
`MODE=repeat` passes, and review the golden files in the PR.
