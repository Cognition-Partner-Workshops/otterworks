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
   credentials and local endpoints only; the repository has no `config.ini`,
   `etl/config.ini` was removed) and `legacy/sitecustomize.py` bind-mounted read-only under
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
not into the golden. Each run also leaves its normalized snapshot in
`.runs/<script>/<scenario>/snapshot-N/`, and a failing `check` or `repeat`
writes the diff it printed to `.runs/<script>/<scenario>/diff.txt`. CI
(`.github/workflows/etl-golden.yml`) uploads the run logs on every run and the
snapshots and diffs when a step fails.

## Normalizer

Only these values are replaced by `<normalized:NAME>`; everything else is
compared byte for byte:

- in S3 JSON / JSON Lines bodies, any `generated_at` that parses as ISO-8601,
  and any `duration_seconds` / `duration_ms` that is a number;
- the Postgres `analytics_daily_summary.updated_at` column (set by `NOW()` on
  the database clock), when it parses as ISO-8601.

A value of the wrong shape is left as is so it shows up as a diff.

## DAG parity

`make etl-parity SCRIPT=<script>` runs the same committed scenarios through an
Airflow DAG instead of the legacy script and diffs them with the goldens
(`harness/parity.py`):

```bash
make etl-parity SCRIPT=audit_archive_weekly                                    # every scenario, the DAG from parity/dags.yaml
make etl-parity SCRIPT=audit_archive_weekly SCENARIO=smoke                     # one scenario
make etl-parity SCRIPT=audit_archive_weekly DAG=parity_wrong__audit_archive_weekly EXPECT=failed
make etl-parity SCRIPT=storage_cleanup_daily VARIANT=reference_mismatches_normalize_keys
make etl-parity SCRIPT=all                                                     # every script in parity/dags.yaml, one after another
```

1. **Same seed, snapshot and normalizer**: each scenario goes through
   `cli.run_scenario` exactly like a golden run (reset, seed, HTTP stub,
   generated `config.ini`); only the step that runs the code differs.
2. **`airflow dags test <dag_id> <frozen_time>`** runs in a throwaway
   container of the Airflow image (`otterworks/etl-airflow:local`, built from
   `etl/airflow` by the make target) with its own SQLite metadata DB
   (`harness/airflow_container.py`). It joins the harness's Docker network;
   every Connection in `etl/airflow/.env.example` is pointed at the same
   LocalStack, Postgres (`otterworks_etl_golden`) and MeiliSearch, and the
   document/file-service Connections at the scenario's HTTP stub. Variables
   are the committed defaults from `.env.example` plus the scenario's
   overrides, as `AIRFLOW_VAR_*` env on that `docker exec ... airflow dags
   test` only (env Variables take precedence over `airflow variables set`, so
   a `set` would silently do nothing). The container's secrets backend
   (`parity/parity_secrets.py`) logs every Variable the DAG reads, and each
   override adds a check `Airflow Variable <key> as read by the DAG`: failed
   unless the DAG read it, with the override value. `--conf {"run_date": <frozen date>}` pins the legacy run date. The
   DAG run's state (success/failed) becomes `result.json` `exit_code` 0/1,
   which is what the legacy goldens hold (0 or 1).
3. **Report** (`harness/differences.py`): golden and DAG snapshots are split
   into one check per compared thing (exit code, each bucket and S3 object,
   DynamoDB key schema and each item by primary key, each SQS queue, each
   Postgres table's columns and rows, each MeiliSearch index's settings/stats
   and each document). Each row of
   `.runs/parity/<dag_id>/<script>/<all|scenario|variant>/report.md` says what was compared, the
   golden (before) and DAG (after) value, and the result: `identical`,
   `accepted difference: <reason>` or `failed`. `report.json` has the full
   values. The run passes only with no failed row.

### Accepted differences and flag-on variants

`<script>/accepted_differences.yaml` is the reviewed list of differences a DAG
may have. An entry names a check and its exact `before` (golden) and `after`
(DAG) values, or `before_absent` / `after_absent`, plus the reason. A check
that differs and is not listed fails; a listed difference that does not occur
or occurs with other values fails too. Nothing is rounded up.

- `accepted` applies to runs with every Variable at its default. Both decided
  flags (`audit_archive_delete_enabled`, `storage_cleanup_normalize_keys`)
  default to `false`, which matches the legacy goldens, so it is empty for
  every script (`tests/test_parity.py` enforces it).
- `variants` are flag-on runs: a committed scenario's seed with per-scenario
  Variable overrides and the reviewed expected differences.
  `audit_archive_weekly/smoke_delete_enabled` (the corrected delete by `id`)
  and `storage_cleanup_daily/reference_mismatches_normalize_keys` (leading
  slash and `s3://bucket/` keys protect their objects; case is not folded).
  Their `before` values are checked against the committed goldens.

### Which DAG

`parity/dags.yaml` maps each script to the DAG under parity; CI's
`etl-parity` matrix is its `scripts` keys. Until a script's Phase 2 port
lands, its entry is the pass-through toy DAG in `parity/dags/`
(`parity_passthrough__<script>`), which runs the unchanged legacy script with
its legacy pins: a `DockerOperator` in the Airflow container starts the
pinned Python 3.9 legacy image with the golden shim, using the mounts,
environment and `run.sh` command from `harness/runner.py`, on the same
network. The parity container mounts the Docker socket and installs
`apache-airflow-providers-docker` (`parity/requirements-airflow.txt`) against
the image's Airflow constraints for this. The pass-through ignores Variables,
so `variants: false`; run against it, a flag-on variant fails (its listed
differences do not occur). A port replaces the entry with its own `dag_id`,
`dag_folder: image` and `variants: true`.

`parity_wrong__audit_archive_weekly` is the negative control: the
pass-through plus one stray S3 object written through the Amazon provider
hook. CI runs it with `EXPECT=failed`, which passes only when a check fails
without a harness error.

## Adding a scenario

Create `<script>/<scenario>/scenario.json`, run
`make etl-golden SCRIPT=<script> SCENARIO=<scenario> MODE=record`, check
`MODE=repeat` passes, and review the golden files in the PR.
