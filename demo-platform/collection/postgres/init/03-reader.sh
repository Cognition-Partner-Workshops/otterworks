#!/bin/bash
# Creates the read-only role used by Grafana and the PostgreSQL MCP server.
# The password comes from the container environment via \getenv; it never appears in argv.
set -euo pipefail
: "${COLLECTION_PG_READER_PASSWORD:?}"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
\getenv reader_pw COLLECTION_PG_READER_PASSWORD
CREATE ROLE collection_reader LOGIN PASSWORD :'reader_pw'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 10;
ALTER ROLE collection_reader SET default_transaction_read_only = on;
ALTER ROLE collection_reader SET statement_timeout = '15s';
ALTER ROLE collection_reader SET idle_in_transaction_session_timeout = '60s';
ALTER ROLE collection_reader SET search_path = collection;
GRANT CONNECT ON DATABASE collection TO collection_reader;
GRANT USAGE ON SCHEMA collection TO collection_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA collection TO collection_reader;
SQL
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<'SQL'
REVOKE CONNECT ON DATABASE postgres FROM PUBLIC;
REVOKE CONNECT ON DATABASE template1 FROM PUBLIC;
SQL
