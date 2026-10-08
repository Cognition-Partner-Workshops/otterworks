-- Exercise the OW_BILLING packages once for the `mmprt` mini namespace so the
-- trigger-maintained history tables and the autonomous audit log are non-empty
-- before the mongo-migration plugin-validation run reads the fixture.
--
-- Package entrypoints only (no direct DML on estate tables):
--   pkg_plans.sp_change_plan        -> closes the open subscription (TRG_SUBSCRIPTIONS_HIST fires)
--   pkg_rating.sp_finalize_rating   -> RATING_PERIODS / RATING_RESULTS
--   pkg_invoicing.sp_issue_invoice  -> INVOICES / INVOICE_LINES
--   pkg_dunning.sp_schedule_dunning + sp_suspend_overdue -> the JOB_NIGHTLY_DUNNING body
-- Every call logs through pkg_ow_util.log_msg into BILLING_AUDIT_LOG.
--
-- Run (no sqlplus on the host; use the container's internal port):
--   docker exec -i otterworks-oracle-billing-oracle-billing-1 \
--     bash -c "sqlplus -s ow_billing/ow_billing@localhost:1521/FREEPDB1" \
--     < testdata/legacy/mmp_rt_exercise.sql
WHENEVER SQLERROR EXIT FAILURE ROLLBACK
SET SERVEROUTPUT ON SIZE UNLIMITED
SET PAGESIZE 200 LINESIZE 160 FEEDBACK OFF

DECLARE
    c_period_start CONSTANT DATE := DATE '2026-02-01';
    c_period_end   CONSTANT DATE := DATE '2026-02-28';
    c_effective_on CONSTANT DATE := DATE '2026-03-01';
    c_starter      CONSTANT VARCHAR2(36) := '10000000-0000-0000-0000-000000000001';
    c_growth       CONSTANT VARCHAR2(36) := '10000000-0000-0000-0000-000000000002';
    c_scale        CONSTANT VARCHAR2(36) := '10000000-0000-0000-0000-000000000003';
    v_new_plan     VARCHAR2(36);
    v_tenants      PLS_INTEGER := 0;
BEGIN
    FOR t IN (SELECT t.id, t.name, s.plan_id
                FROM tenants t
                JOIN subscriptions s ON s.tenant_id = t.id AND s.ends_on IS NULL
               WHERE t.name LIKE 'mmprt::%'
               ORDER BY t.name) LOOP
        v_tenants := v_tenants + 1;
        -- Move every tenant one tier (SCALE drops back to GROWTH).
        v_new_plan := CASE t.plan_id WHEN c_starter THEN c_growth
                                     WHEN c_growth  THEN c_scale
                                     ELSE c_growth END;
        pkg_plans.sp_change_plan(t.id, v_new_plan, c_effective_on);
        pkg_rating.sp_finalize_rating(t.id, c_period_start, c_period_end);
        pkg_invoicing.sp_issue_invoice(t.id, c_period_start, c_period_end);
        DBMS_OUTPUT.PUT_LINE('exercised ' || t.name || ' -> plan ' || v_new_plan);
    END LOOP;
    IF v_tenants = 0 THEN
        RAISE_APPLICATION_ERROR(-20900, 'no mmprt:: tenants found; run mmp_rt_mini_seed.py first');
    END IF;

    -- Nightly batch body (schema/04_jobs.sql JOB_NIGHTLY_DUNNING), run once by hand.
    pkg_dunning.sp_schedule_dunning(TRUNC(SYSDATE));
    pkg_dunning.sp_suspend_overdue(TRUNC(SYSDATE));
    COMMIT;
    DBMS_OUTPUT.PUT_LINE('exercised ' || v_tenants || ' mmprt tenants; nightly dunning body run once');
END;
/

COLUMN table_name FORMAT A24
SELECT 'SUBSCRIPTIONS_HIST'   AS table_name, COUNT(*) AS cnt FROM subscriptions_hist
UNION ALL SELECT 'CUSTOMER_MASTER_HIST', COUNT(*) FROM customer_master_hist
UNION ALL SELECT 'BILLING_AUDIT_LOG',    COUNT(*) FROM billing_audit_log
UNION ALL SELECT 'TENANTS',              COUNT(*) FROM tenants
UNION ALL SELECT 'PLANS',                COUNT(*) FROM plans
UNION ALL SELECT 'SUBSCRIPTIONS',        COUNT(*) FROM subscriptions
UNION ALL SELECT 'USAGE_EVENTS',         COUNT(*) FROM usage_events
UNION ALL SELECT 'RATING_PERIODS',       COUNT(*) FROM rating_periods
UNION ALL SELECT 'RATING_RESULTS',       COUNT(*) FROM rating_results
UNION ALL SELECT 'INVOICES',             COUNT(*) FROM invoices
UNION ALL SELECT 'INVOICE_LINES',        COUNT(*) FROM invoice_lines
UNION ALL SELECT 'CREDIT_NOTES',         COUNT(*) FROM credit_notes
UNION ALL SELECT 'DUNNING_ATTEMPTS',     COUNT(*) FROM dunning_attempts
UNION ALL SELECT 'NOTIFICATIONS',        COUNT(*) FROM notifications
UNION ALL SELECT 'CODES',                COUNT(*) FROM codes
UNION ALL SELECT 'CUSTOMER_MASTER',      COUNT(*) FROM customer_master
UNION ALL SELECT 'ENTITY_ATTR_VALUE',    COUNT(*) FROM entity_attr_value
UNION ALL SELECT 'INVOICE_HEADER',       COUNT(*) FROM invoice_header
UNION ALL SELECT 'INVOICE_LINE',         COUNT(*) FROM invoice_line
UNION ALL SELECT 'FIXTURE_META',         COUNT(*) FROM fixture_meta;
EXIT
