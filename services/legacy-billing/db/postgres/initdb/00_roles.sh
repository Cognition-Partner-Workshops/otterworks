#!/bin/sh
# Creates the OW_BILLING owner role and schemas in the takeout target.
# Runs once, as the container superuser, from docker-entrypoint-initdb.d.
# The app role is deliberately not a superuser (Oracle's ow_billing was a
# plain schema owner too).
set -eu
# ow_billing_audit is the insert-only role pkg_ow_util.log_msg writes through
# on its own dblink connection, so audit rows survive a rollback of the
# caller like Oracle's AUTONOMOUS_TRANSACTION. dblink only lets a
# non-superuser connect with a password, so loopback TCP for that role must
# ask for one (the image trusts 127.0.0.1 otherwise).
sed -i '1i host all ow_billing_audit 127.0.0.1/32 scram-sha-256' "$PGDATA/pg_hba.conf"
psql -v ON_ERROR_STOP=1 -v app_pw="${BILLING_PG_APP_PASSWORD:-ow_billing}" \
     -v audit_pw="${BILLING_PG_AUDIT_PASSWORD:-ow_billing_audit}" \
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

CREATE ROLE ow_billing_audit LOGIN PASSWORD :'audit_pw';
GRANT CONNECT ON DATABASE :"DBNAME" TO ow_billing_audit;
ALTER ROLE ow_billing_audit SET search_path = ow_billing, public;
CREATE SCHEMA ow_billing_dblink;
CREATE EXTENSION dblink SCHEMA ow_billing_dblink;
REVOKE ALL ON SCHEMA ow_billing_dblink FROM PUBLIC;
GRANT USAGE ON SCHEMA ow_billing_dblink TO ow_billing;
SELECT format('CREATE SERVER ow_billing_audit_loopback FOREIGN DATA WRAPPER dblink_fdw'
              ' OPTIONS (host %L, port %L, dbname %L)', '127.0.0.1', '5432', :'DBNAME') \gexec
GRANT USAGE ON FOREIGN SERVER ow_billing_audit_loopback TO ow_billing;
CREATE USER MAPPING FOR ow_billing SERVER ow_billing_audit_loopback
    OPTIONS (user 'ow_billing_audit', password :'audit_pw');
ALTER DATABASE :"DBNAME" SET timezone = 'UTC';
SQL
