# commission_dw (dbt-postgres on PostgreSQL 16)

dbt port of the Oracle `COMMISSION_DW` warehouse (`db/olap/02_etl_pkg.sql`:
`DW_ETL_PKG.LOAD_COMMISSION_FACTS` and `MV_AGENT_COMMISSION_SUMMARY`). The
pinned Oracle baseline it is measured against is in `golden/`.

| Piece | Version / value |
|---|---|
| Python | 3.12 via `uv` (`.python-version`, `pyproject.toml`, `uv.lock`; `requirements.txt` is `uv export` of the lock) |
| dbt | `dbt-core==1.12.5`, `dbt-postgres==1.11.0` |
| Database | `postgres:16`, db `commission`, login `commission_dw` |
| Schemas | `commission_pay` (landed sources, Oracle `COMMISSION_PAY`), `commission_dw` (models, Oracle `COMMISSION_DW`) |

Models use `+schema` verbatim (`macros/generate_schema_name.sql`), so they land
in `commission_dw`, not `<target>_commission_dw`. `packages.yml` is empty until
a model needs `dbt_utils`.

## Run it

From the repo root:

```bash
make insurance-pg-up NS=dev        # postgres:16 on 127.0.0.1:(57432 + crc32(NS) % 1000)
make insurance-dbt-build NS=dev    # dbt deps, dbt debug, dbt build
make insurance-pg-down NS=dev      # stop, drop the volume, delete the generated password
```

`profiles.yml` reads every connection value from `COMMISSION_DW_PG_*`
environment variables; the Make target sets them. `insurance-pg-up` generates a
random password per namespace into `.local/<ns>.pgpass` (git-ignored) and
`insurance-pg-down` deletes it. If Docker Hub rate-limits, pull through the
mirror: `make insurance-pg-up NS=dev INSURANCE_PG_IMAGE=mirror.gcr.io/library/postgres:16`.

To run dbt by hand:

```bash
cd services/industry-solutions/insurance/dbt/commission_dw
export COMMISSION_DW_PG_HOST=127.0.0.1 COMMISSION_DW_PG_PORT=<port> \
  COMMISSION_DW_PG_USER=commission_dw COMMISSION_DW_PG_PASSWORD="$(cat .local/dev.pgpass)" \
  COMMISSION_DW_PG_DBNAME=commission COMMISSION_DW_PG_SCHEMA=commission_dw
DBT_PROFILES_DIR=. uv run --frozen dbt debug
```
