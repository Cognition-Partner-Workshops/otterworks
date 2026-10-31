SELECT 'BILLING_AUDIT_LOG' AS table_name, COUNT(*) AS landed_rows FROM ow_tp.mig_unt19_20261030_src.billing_audit_log
UNION ALL
SELECT 'CODES' AS table_name, COUNT(*) AS landed_rows FROM ow_tp.mig_unt19_20261030_src.codes
UNION ALL
SELECT 'CUSTOMER_MASTER' AS table_name, COUNT(*) AS landed_rows FROM ow_tp.mig_unt19_20261030_src.customer_master
UNION ALL
SELECT 'CUSTOMER_MASTER_HIST' AS table_name, COUNT(*) AS landed_rows FROM ow_tp.mig_unt19_20261030_src.customer_master_hist
UNION ALL
SELECT 'ENTITY_ATTR_VALUE' AS table_name, COUNT(*) AS landed_rows FROM ow_tp.mig_unt19_20261030_src.entity_attr_value
UNION ALL
SELECT 'INVOICE_HEADER' AS table_name, COUNT(*) AS landed_rows FROM ow_tp.mig_unt19_20261030_src.invoice_header
UNION ALL
SELECT 'INVOICE_LINE' AS table_name, COUNT(*) AS landed_rows FROM ow_tp.mig_unt19_20261030_src.invoice_line
UNION ALL
SELECT 'PLANS' AS table_name, COUNT(*) AS landed_rows FROM ow_tp.mig_unt19_20261030_src.plans
UNION ALL
SELECT 'SUBSCRIPTIONS_HIST' AS table_name, COUNT(*) AS landed_rows FROM ow_tp.mig_unt19_20261030_src.subscriptions_hist
UNION ALL
SELECT 'TENANTS' AS table_name, COUNT(*) AS landed_rows FROM ow_tp.mig_unt19_20261030_src.tenants
UNION ALL
SELECT 'CREDIT_NOTES' AS table_name, COUNT(*) AS landed_rows FROM ow_tp.mig_unt19_20261030_src.credit_notes
UNION ALL
SELECT 'NOTIFICATIONS' AS table_name, COUNT(*) AS landed_rows FROM ow_tp.mig_unt19_20261030_src.notifications
UNION ALL
SELECT 'RATING_PERIODS' AS table_name, COUNT(*) AS landed_rows FROM ow_tp.mig_unt19_20261030_src.rating_periods
UNION ALL
SELECT 'SUBSCRIPTIONS' AS table_name, COUNT(*) AS landed_rows FROM ow_tp.mig_unt19_20261030_src.subscriptions
UNION ALL
SELECT 'USAGE_EVENTS' AS table_name, COUNT(*) AS landed_rows FROM ow_tp.mig_unt19_20261030_src.usage_events
UNION ALL
SELECT 'INVOICES' AS table_name, COUNT(*) AS landed_rows FROM ow_tp.mig_unt19_20261030_src.invoices
UNION ALL
SELECT 'RATING_RESULTS' AS table_name, COUNT(*) AS landed_rows FROM ow_tp.mig_unt19_20261030_src.rating_results
UNION ALL
SELECT 'DUNNING_ATTEMPTS' AS table_name, COUNT(*) AS landed_rows FROM ow_tp.mig_unt19_20261030_src.dunning_attempts
UNION ALL
SELECT 'INVOICE_LINES' AS table_name, COUNT(*) AS landed_rows FROM ow_tp.mig_unt19_20261030_src.invoice_lines
ORDER BY table_name;
