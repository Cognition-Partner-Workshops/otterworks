# OtterWorks ETL on Airflow

Airflow 2.8 (Python 3.11, LocalExecutor) runtime for the cron-to-Airflow migration described in
[`../ETL_UPGRADE_GUIDE.md`](../ETL_UPGRADE_GUIDE.md). The legacy cron scripts in `etl/` keep running
until their DAGs are ported; this directory only provides the image, local stack and chart.

| Path | Purpose |
| --- | --- |
| `Dockerfile` | Multi-stage image on `apache/airflow:2.8.4-python3.11`; providers pinned by the Airflow constraints file; non-root `airflow`; `HEALTHCHECK` on `/health` |
| `requirements.txt` | Amazon, Postgres and HTTP providers (versions resolved by constraints) |
| `otterworks_etl/` | Shared ETL package, built as a wheel and installed into the image |
| `dags/` | DAGs baked into the image; `otterworks_platform_check` imports every provider hook |
| `scripts/check-stack.sh` | Gate: webserver + scheduler healthy, expected DAG parsed, zero import errors |

## Local stack

```bash
make airflow-up     # infra (postgres, localstack, meilisearch) + Airflow, waits for healthy, runs the gate
make airflow-check  # re-run the gate
make airflow-down   # stop Airflow (keeps its metadata volume; infra stays up)
```

UI: http://localhost:8280 (`airflow` / `airflow`, override with `AIRFLOW_ADMIN_USER` /
`AIRFLOW_ADMIN_PASSWORD`). Metadata lives in its own `airflow-postgres` container and `airflow`
database, never in the application `otterworks` database. Airflow joins `otterworks-network`, so
DAGs reach `postgres`, `localstack` and `meilisearch` by service name.

## Kubernetes

`infrastructure/helm/etl-airflow` is validated in CI with `helm lint` and
`helm template | kubeconform`. It is not deployed by this change; services are `ClusterIP` only.
