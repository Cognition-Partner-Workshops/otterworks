#!/bin/sh
# Creates the OW_BILLING owner role and schemas in the takeout target.
# Runs once, as the container superuser, from docker-entrypoint-initdb.d.
# The app role is deliberately not a superuser (Oracle's ow_billing was a
# plain schema owner too).
set -eu
psql -v ON_ERROR_STOP=1 -v app_pw="${BILLING_PG_APP_PASSWORD:-ow_billing}" \
     --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
CREATE ROLE ow_billing LOGIN PASSWORD :'app_pw';
GRANT CONNECT, TEMPORARY ON DATABASE :"DBNAME" TO ow_billing;
CREATE SCHEMA ow_billing     AUTHORIZATION ow_billing;
CREATE SCHEMA pkg_ow_util    AUTHORIZATION ow_billing;
CREATE SCHEMA pkg_plans      AUTHORIZATION ow_billing;
CREATE SCHEMA pkg_rating     AUTHORIZATION ow_billing;
CREATE SCHEMA pkg_invoicing  AUTHORIZATION ow_billing;
CREATE SCHEMA pkg_dunning    AUTHORIZATION ow_billing;
CREATE SCHEMA pkg_jobs       AUTHORIZATION ow_billing;
ALTER ROLE ow_billing SET search_path = ow_billing, public;
ALTER DATABASE :"DBNAME" SET timezone = 'UTC';
SQL
