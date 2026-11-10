# Warehouse tools

Requires Python 3.10 or later and Docker Compose v2.

```sh
python3 -m venv warehouse/.venv
warehouse/.venv/bin/pip install -r warehouse/requirements.txt
docker pull mirror.gcr.io/library/postgres:16
docker tag mirror.gcr.io/library/postgres:16 postgres:16
export NS=sfx-d1110-before
export TD_PG_PORT=$(python3 -c 'import os,zlib; print(54500+zlib.crc32(os.environ["NS"].encode())%1000)')
warehouse/teradata/bin/compose up -d --wait --pull never
warehouse/.venv/bin/pytest -q warehouse/teradata/tests
warehouse/teradata/bin/bteq run path/to/script.bteq --var BUSINESS_DATE=20261109
warehouse/teradata/bin/bteq < path/to/script.bteq
warehouse/teradata/bin/compose down -v
```

`NS` is required for Compose. The host port defaults to 54500 plus the namespace's
CRC32 modulo 1000. Export that port for the runner and tests as above. PostgreSQL
is bound only to the loopback interface and uses local trust authentication.

Connections use `TD_PG_DSN` or `TD_PG_HOST`, `TD_PG_PORT`, `TD_PG_DB`,
`TD_PG_USER`, `TD_PG_PASSWORD`. Defaults are localhost, 5432, teradata, postgres,
and an empty password. Explicit individual variables override DSN fields.
Script `${VAR}` references expand from the environment or repeatable `--var K=V`.
Pass credentials through environment variables, not script literals.

`warehouse/teradata/bteq` contains the interpreter, SQL translation, and connection
bootstrap. Metadata lives in `sfx_td`; database names map to PostgreSQL schemas.
The `tests` directory exercises SQL semantics against PostgreSQL 16 and script
parsing. Database tests skip when no server is reachable only if no `TD_PG_*`
variables were provided. An explicitly configured unreachable server fails tests.
Export destinations must have an existing parent directory.
