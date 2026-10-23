-- One-time role setup for the billing database, run before db/migrate.sh.
--
-- Run it as the platform admin that owns the target database and has
-- CREATEROLE (on RDS: the master user, which has rds_superuser; locally any
-- CREATEROLE role). It needs no superuser. Passwords are not set here; set
-- them afterwards with \password <role>, or use IAM database authentication.
--
--   psql -X -v ON_ERROR_STOP=1 -d <database> \
--        -v owner_role=billing_owner -v app_role=billing_app \
--        -f services/legacy-billing/db/bootstrap/roles.sql
--
-- Role names are cluster-wide on a shared instance, so give each database its
-- own pair (e.g. billing_owner_<id> / billing_app_<id>).

\set dbname :DBNAME

-- Owns the billing schema and every object in it; db/migrate.sh connects as
-- this role. No superuser, no CREATEDB, no CREATEROLE.
CREATE ROLE :"owner_role" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;

-- Runtime role for app/app.py: EXECUTE on the routines and the table grants
-- the SECURITY INVOKER routines need (see migrations/0006_app_grants.sql).
-- Owns nothing.
CREATE ROLE :"app_role" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;

-- CREATE on the database lets the owner run CREATE SCHEMA billing (and the
-- runner's billing_migrations schema).
GRANT CONNECT, CREATE ON DATABASE :"dbname" TO :"owner_role";
GRANT CONNECT ON DATABASE :"dbname" TO :"app_role";

-- Pin search_path and TimeZone per role in this database. The routines cast
-- timestamptz to date, so results depend on the session TimeZone.
ALTER ROLE :"owner_role" IN DATABASE :"dbname" SET search_path = billing;
ALTER ROLE :"owner_role" IN DATABASE :"dbname" SET "TimeZone" = 'UTC';
ALTER ROLE :"app_role" IN DATABASE :"dbname" SET search_path = billing;
ALTER ROLE :"app_role" IN DATABASE :"dbname" SET "TimeZone" = 'UTC';
