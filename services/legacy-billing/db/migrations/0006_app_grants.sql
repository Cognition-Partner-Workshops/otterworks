-- Runtime privileges for the application role (psql variable app_role, set by
-- db/migrate.sh from BILLING_APP_ROLE). Runs as the owner role.
--
-- The routines are SECURITY INVOKER, so the app role needs table privileges
-- for every row a routine reads or writes. ON CONFLICT ... DO UPDATE needs
-- both INSERT and UPDATE.

REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA billing FROM PUBLIC;
REVOKE EXECUTE ON ALL PROCEDURES IN SCHEMA billing FROM PUBLIC;

GRANT USAGE ON SCHEMA billing TO :"app_role";
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA billing TO :"app_role";
GRANT EXECUTE ON ALL PROCEDURES IN SCHEMA billing TO :"app_role";

GRANT SELECT ON ALL TABLES IN SCHEMA billing TO :"app_role";
GRANT INSERT, UPDATE ON billing.subscriptions, billing.rating_periods,
    billing.rating_results, billing.invoices TO :"app_role";
GRANT UPDATE ON billing.tenants, billing.credit_notes TO :"app_role";
GRANT INSERT ON billing.dunning_attempts, billing.notifications TO :"app_role";
GRANT INSERT, DELETE ON billing.invoice_lines TO :"app_role";

-- Objects the owner creates in later migrations: no EXECUTE for PUBLIC,
-- EXECUTE and SELECT for the app role. Write grants stay explicit per table.
ALTER DEFAULT PRIVILEGES REVOKE EXECUTE ON ROUTINES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA billing GRANT EXECUTE ON ROUTINES TO :"app_role";
ALTER DEFAULT PRIVILEGES IN SCHEMA billing GRANT SELECT ON TABLES TO :"app_role";
