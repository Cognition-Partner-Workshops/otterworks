-- SELECT-only principal for the local legacy billing PostgreSQL fixture.
-- Run by legacy_billing_source.sh as the schema owner (billing); the password arrives in RO_PW.
\set pw `printf '%s' "$RO_PW"`
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'billing_ro') THEN
    CREATE ROLE billing_ro LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
  END IF;
END $$;
ALTER ROLE billing_ro PASSWORD :'pw';
GRANT USAGE ON SCHEMA billing TO billing_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA billing TO billing_ro;
-- routines are PUBLIC EXECUTE by default; the owner (billing) keeps EXECUTE, nobody else does
REVOKE EXECUTE ON ALL ROUTINES IN SCHEMA billing FROM PUBLIC;
-- database-wide defaults (not IN SCHEMA) so they survive the procs harness dropping and recreating billing
ALTER DEFAULT PRIVILEGES FOR ROLE billing GRANT USAGE ON SCHEMAS TO billing_ro;
ALTER DEFAULT PRIVILEGES FOR ROLE billing GRANT SELECT ON TABLES TO billing_ro;
ALTER DEFAULT PRIVILEGES FOR ROLE billing REVOKE EXECUTE ON ROUTINES FROM PUBLIC;
