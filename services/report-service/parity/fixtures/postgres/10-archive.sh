#!/bin/sh
# Applies the migration target DDL (migration/target/postgresql, mounted at /ldm-ddl) to
# otterworks_archive, then the characterization fixture.
set -eu
for f in /ldm-ddl/*.sql; do
  psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d otterworks_archive -q -f "$f"
done
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d otterworks_archive -q -f /docker-entrypoint-initdb.d/archive-fixture.sql.in
