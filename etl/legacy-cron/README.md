# legacy-etl-cron

Runs the committed `etl/crontab` exactly as written, through the unchanged `etl/run.sh`,
next to the Airflow stack (`docker-compose.airflow.yml`, Compose profile `legacy-cron`) so
the cron jobs and their Airflow DAGs can coexist during the migration and each job can be
cut over, or rolled back, on its own.

| | |
|---|---|
| Runtime | `python:3.9-slim`, the legacy pins from `etl/requirements.txt` (same constraints as the golden harness), non-root, read-only rootfs |
| Scheduler | [supercronic](https://github.com/aptible/supercronic) v0.2.33 (checksum-pinned) reading `/opt/etl/crontab` |
| Mounted read-only | `etl/crontab`, `etl/run.sh`, `etl/scripts/`, the golden shim `etl/tests/golden/legacy/sitecustomize.py` at `/opt/etl/sitecustomize.py`, `etl/tests/golden/harness/` |
| `/opt/etl/config.ini` | rendered at start by `harness/config_ini.render` into a tmpfs: local endpoints and dev credentials only. The repository has no `config.ini` (`etl/config.ini` was removed) |
| AWS | the shim points every boto3 client at LocalStack (`GOLDEN_AWS_ENDPOINT_URL`) and rewrites real SQS URLs; the clock is **not** frozen |
| Logs | every `/var/log/etl/*.log` the crontab appends to is a symlink to `/dev/stdout`; supercronic tags each line with the job, so `docker compose logs` is the log |
| Network | `otterworks-network`, the same network as `docker-compose.infra.yml` and the Airflow services |

## Use

```bash
make legacy-cron-up                                # infra + harness resources + build + start (healthy)
make legacy-cron-run SCRIPT=storage_cleanup_daily  # run that script's crontab line now
make legacy-cron-smoke                             # fires on schedule, cutover, rollback
make legacy-cron-test                              # ruff + pytest for legacy_cron.py
make legacy-cron-down
```

`search_reindex_weekly` reads documents from `document-service`, so it only succeeds when
the application stack (`docker-compose.yml`) is up on the same network.

## Cutover and rollback

Only the lines present in `etl/crontab` are scheduled. To cut a job over to Airflow, delete
its line in the PR that enables the DAG and run `make legacy-cron-reload`; to roll back,
restore the line and reload. `legacy_cron.py run <script>.py` exits 3 for a script that no
longer has a line, so nothing can run it by accident. `LEGACY_ETL_CRONTAB=<path>` mounts a
different crontab without touching `etl/crontab` (the smoke test uses this).
