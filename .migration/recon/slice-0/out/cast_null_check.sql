SELECT 'BILLING_AUDIT_LOG.log_id' AS col, COUNT(*) - COUNT(`log_id`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.billing_audit_log
UNION ALL
SELECT 'BILLING_AUDIT_LOG.logged_at' AS col, COUNT(*) - COUNT(`logged_at`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.billing_audit_log
UNION ALL
SELECT 'CODES.code_val' AS col, COUNT(*) - COUNT(`code_val`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.codes
UNION ALL
SELECT 'CUSTOMER_MASTER.cust_seq_no' AS col, COUNT(*) - COUNT(`cust_seq_no`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master
UNION ALL
SELECT 'CUSTOMER_MASTER.phone1_type_cd' AS col, COUNT(*) - COUNT(`phone1_type_cd`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master
UNION ALL
SELECT 'CUSTOMER_MASTER.phone2_type_cd' AS col, COUNT(*) - COUNT(`phone2_type_cd`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master
UNION ALL
SELECT 'CUSTOMER_MASTER.phone3_type_cd' AS col, COUNT(*) - COUNT(`phone3_type_cd`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master
UNION ALL
SELECT 'CUSTOMER_MASTER.phone4_type_cd' AS col, COUNT(*) - COUNT(`phone4_type_cd`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master
UNION ALL
SELECT 'CUSTOMER_MASTER.status_cd' AS col, COUNT(*) - COUNT(`status_cd`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master
UNION ALL
SELECT 'CUSTOMER_MASTER.sub_status_cd' AS col, COUNT(*) - COUNT(`sub_status_cd`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master
UNION ALL
SELECT 'CUSTOMER_MASTER.cust_type_cd' AS col, COUNT(*) - COUNT(`cust_type_cd`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master
UNION ALL
SELECT 'CUSTOMER_MASTER.segment_cd' AS col, COUNT(*) - COUNT(`segment_cd`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master
UNION ALL
SELECT 'CUSTOMER_MASTER.region_cd' AS col, COUNT(*) - COUNT(`region_cd`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master
UNION ALL
SELECT 'CUSTOMER_MASTER.territory_cd' AS col, COUNT(*) - COUNT(`territory_cd`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master
UNION ALL
SELECT 'CUSTOMER_MASTER.channel_cd' AS col, COUNT(*) - COUNT(`channel_cd`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master
UNION ALL
SELECT 'CUSTOMER_MASTER.rate_class_cd' AS col, COUNT(*) - COUNT(`rate_class_cd`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master
UNION ALL
SELECT 'CUSTOMER_MASTER.cur_bal_amt' AS col, COUNT(*) - COUNT(`cur_bal_amt`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master
UNION ALL
SELECT 'CUSTOMER_MASTER.past_due_amt' AS col, COUNT(*) - COUNT(`past_due_amt`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master
UNION ALL
SELECT 'CUSTOMER_MASTER.ytd_billed_amt' AS col, COUNT(*) - COUNT(`ytd_billed_amt`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master
UNION ALL
SELECT 'CUSTOMER_MASTER.ltd_billed_amt' AS col, COUNT(*) - COUNT(`ltd_billed_amt`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master
UNION ALL
SELECT 'CUSTOMER_MASTER.ytd_paid_amt' AS col, COUNT(*) - COUNT(`ytd_paid_amt`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master
UNION ALL
SELECT 'CUSTOMER_MASTER.credit_limit_amt' AS col, COUNT(*) - COUNT(`credit_limit_amt`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master
UNION ALL
SELECT 'CUSTOMER_MASTER.conversion_batch_no' AS col, COUNT(*) - COUNT(`conversion_batch_no`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master
UNION ALL
SELECT 'CUSTOMER_MASTER.udf_amt_01' AS col, COUNT(*) - COUNT(`udf_amt_01`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master
UNION ALL
SELECT 'CUSTOMER_MASTER.udf_amt_02' AS col, COUNT(*) - COUNT(`udf_amt_02`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master
UNION ALL
SELECT 'CUSTOMER_MASTER.udf_amt_03' AS col, COUNT(*) - COUNT(`udf_amt_03`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master
UNION ALL
SELECT 'CUSTOMER_MASTER.udf_amt_04' AS col, COUNT(*) - COUNT(`udf_amt_04`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master
UNION ALL
SELECT 'CUSTOMER_MASTER.udf_amt_05' AS col, COUNT(*) - COUNT(`udf_amt_05`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master
UNION ALL
SELECT 'CUSTOMER_MASTER.udf_amt_06' AS col, COUNT(*) - COUNT(`udf_amt_06`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master
UNION ALL
SELECT 'CUSTOMER_MASTER.udf_amt_07' AS col, COUNT(*) - COUNT(`udf_amt_07`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master
UNION ALL
SELECT 'CUSTOMER_MASTER.udf_amt_08' AS col, COUNT(*) - COUNT(`udf_amt_08`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master
UNION ALL
SELECT 'CUSTOMER_MASTER.udf_amt_09' AS col, COUNT(*) - COUNT(`udf_amt_09`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master
UNION ALL
SELECT 'CUSTOMER_MASTER.udf_amt_10' AS col, COUNT(*) - COUNT(`udf_amt_10`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master
UNION ALL
SELECT 'CUSTOMER_MASTER.created_dt' AS col, COUNT(*) - COUNT(`created_dt`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master
UNION ALL
SELECT 'CUSTOMER_MASTER.updated_dt' AS col, COUNT(*) - COUNT(`updated_dt`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master
UNION ALL
SELECT 'CUSTOMER_MASTER.row_version_no' AS col, COUNT(*) - COUNT(`row_version_no`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master
UNION ALL
SELECT 'CUSTOMER_MASTER_HIST.hist_id' AS col, COUNT(*) - COUNT(`hist_id`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master_hist
UNION ALL
SELECT 'CUSTOMER_MASTER_HIST.cust_seq_no' AS col, COUNT(*) - COUNT(`cust_seq_no`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master_hist
UNION ALL
SELECT 'CUSTOMER_MASTER_HIST.phone1_type_cd' AS col, COUNT(*) - COUNT(`phone1_type_cd`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master_hist
UNION ALL
SELECT 'CUSTOMER_MASTER_HIST.phone2_type_cd' AS col, COUNT(*) - COUNT(`phone2_type_cd`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master_hist
UNION ALL
SELECT 'CUSTOMER_MASTER_HIST.phone3_type_cd' AS col, COUNT(*) - COUNT(`phone3_type_cd`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master_hist
UNION ALL
SELECT 'CUSTOMER_MASTER_HIST.phone4_type_cd' AS col, COUNT(*) - COUNT(`phone4_type_cd`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master_hist
UNION ALL
SELECT 'CUSTOMER_MASTER_HIST.status_cd' AS col, COUNT(*) - COUNT(`status_cd`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master_hist
UNION ALL
SELECT 'CUSTOMER_MASTER_HIST.sub_status_cd' AS col, COUNT(*) - COUNT(`sub_status_cd`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master_hist
UNION ALL
SELECT 'CUSTOMER_MASTER_HIST.cust_type_cd' AS col, COUNT(*) - COUNT(`cust_type_cd`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master_hist
UNION ALL
SELECT 'CUSTOMER_MASTER_HIST.segment_cd' AS col, COUNT(*) - COUNT(`segment_cd`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master_hist
UNION ALL
SELECT 'CUSTOMER_MASTER_HIST.region_cd' AS col, COUNT(*) - COUNT(`region_cd`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master_hist
UNION ALL
SELECT 'CUSTOMER_MASTER_HIST.territory_cd' AS col, COUNT(*) - COUNT(`territory_cd`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master_hist
UNION ALL
SELECT 'CUSTOMER_MASTER_HIST.channel_cd' AS col, COUNT(*) - COUNT(`channel_cd`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master_hist
UNION ALL
SELECT 'CUSTOMER_MASTER_HIST.rate_class_cd' AS col, COUNT(*) - COUNT(`rate_class_cd`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master_hist
UNION ALL
SELECT 'CUSTOMER_MASTER_HIST.cur_bal_amt' AS col, COUNT(*) - COUNT(`cur_bal_amt`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master_hist
UNION ALL
SELECT 'CUSTOMER_MASTER_HIST.past_due_amt' AS col, COUNT(*) - COUNT(`past_due_amt`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master_hist
UNION ALL
SELECT 'CUSTOMER_MASTER_HIST.ytd_billed_amt' AS col, COUNT(*) - COUNT(`ytd_billed_amt`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master_hist
UNION ALL
SELECT 'CUSTOMER_MASTER_HIST.ltd_billed_amt' AS col, COUNT(*) - COUNT(`ltd_billed_amt`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master_hist
UNION ALL
SELECT 'CUSTOMER_MASTER_HIST.ytd_paid_amt' AS col, COUNT(*) - COUNT(`ytd_paid_amt`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master_hist
UNION ALL
SELECT 'CUSTOMER_MASTER_HIST.credit_limit_amt' AS col, COUNT(*) - COUNT(`credit_limit_amt`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master_hist
UNION ALL
SELECT 'CUSTOMER_MASTER_HIST.conversion_batch_no' AS col, COUNT(*) - COUNT(`conversion_batch_no`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master_hist
UNION ALL
SELECT 'CUSTOMER_MASTER_HIST.udf_amt_01' AS col, COUNT(*) - COUNT(`udf_amt_01`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master_hist
UNION ALL
SELECT 'CUSTOMER_MASTER_HIST.udf_amt_02' AS col, COUNT(*) - COUNT(`udf_amt_02`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master_hist
UNION ALL
SELECT 'CUSTOMER_MASTER_HIST.udf_amt_03' AS col, COUNT(*) - COUNT(`udf_amt_03`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master_hist
UNION ALL
SELECT 'CUSTOMER_MASTER_HIST.udf_amt_04' AS col, COUNT(*) - COUNT(`udf_amt_04`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master_hist
UNION ALL
SELECT 'CUSTOMER_MASTER_HIST.udf_amt_05' AS col, COUNT(*) - COUNT(`udf_amt_05`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master_hist
UNION ALL
SELECT 'CUSTOMER_MASTER_HIST.udf_amt_06' AS col, COUNT(*) - COUNT(`udf_amt_06`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master_hist
UNION ALL
SELECT 'CUSTOMER_MASTER_HIST.udf_amt_07' AS col, COUNT(*) - COUNT(`udf_amt_07`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master_hist
UNION ALL
SELECT 'CUSTOMER_MASTER_HIST.udf_amt_08' AS col, COUNT(*) - COUNT(`udf_amt_08`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master_hist
UNION ALL
SELECT 'CUSTOMER_MASTER_HIST.udf_amt_09' AS col, COUNT(*) - COUNT(`udf_amt_09`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master_hist
UNION ALL
SELECT 'CUSTOMER_MASTER_HIST.udf_amt_10' AS col, COUNT(*) - COUNT(`udf_amt_10`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master_hist
UNION ALL
SELECT 'CUSTOMER_MASTER_HIST.created_dt' AS col, COUNT(*) - COUNT(`created_dt`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master_hist
UNION ALL
SELECT 'CUSTOMER_MASTER_HIST.updated_dt' AS col, COUNT(*) - COUNT(`updated_dt`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master_hist
UNION ALL
SELECT 'CUSTOMER_MASTER_HIST.row_version_no' AS col, COUNT(*) - COUNT(`row_version_no`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.customer_master_hist
UNION ALL
SELECT 'ENTITY_ATTR_VALUE.eav_id' AS col, COUNT(*) - COUNT(`eav_id`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.entity_attr_value
UNION ALL
SELECT 'INVOICE_HEADER.status_cd' AS col, COUNT(*) - COUNT(`status_cd`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.invoice_header
UNION ALL
SELECT 'INVOICE_HEADER.total_amt' AS col, COUNT(*) - COUNT(`total_amt`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.invoice_header
UNION ALL
SELECT 'INVOICE_HEADER.batch_no' AS col, COUNT(*) - COUNT(`batch_no`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.invoice_header
UNION ALL
SELECT 'INVOICE_LINE.line_no' AS col, COUNT(*) - COUNT(`line_no`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.invoice_line
UNION ALL
SELECT 'INVOICE_LINE.line_type_cd' AS col, COUNT(*) - COUNT(`line_type_cd`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.invoice_line
UNION ALL
SELECT 'INVOICE_LINE.qty' AS col, COUNT(*) - COUNT(`qty`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.invoice_line
UNION ALL
SELECT 'INVOICE_LINE.unit_price' AS col, COUNT(*) - COUNT(`unit_price`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.invoice_line
UNION ALL
SELECT 'INVOICE_LINE.amount' AS col, COUNT(*) - COUNT(`amount`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.invoice_line
UNION ALL
SELECT 'INVOICE_LINE.tax_amt' AS col, COUNT(*) - COUNT(`tax_amt`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.invoice_line
UNION ALL
SELECT 'INVOICE_LINE.batch_no' AS col, COUNT(*) - COUNT(`batch_no`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.invoice_line
UNION ALL
SELECT 'PLANS.tier_cd' AS col, COUNT(*) - COUNT(`tier_cd`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.plans
UNION ALL
SELECT 'PLANS.monthly_fee' AS col, COUNT(*) - COUNT(`monthly_fee`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.plans
UNION ALL
SELECT 'PLANS.included_units' AS col, COUNT(*) - COUNT(`included_units`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.plans
UNION ALL
SELECT 'PLANS.overage_rate' AS col, COUNT(*) - COUNT(`overage_rate`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.plans
UNION ALL
SELECT 'SUBSCRIPTIONS_HIST.hist_id' AS col, COUNT(*) - COUNT(`hist_id`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.subscriptions_hist
UNION ALL
SELECT 'SUBSCRIPTIONS_HIST.starts_on' AS col, COUNT(*) - COUNT(`starts_on`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.subscriptions_hist
UNION ALL
SELECT 'SUBSCRIPTIONS_HIST.ends_on' AS col, COUNT(*) - COUNT(`ends_on`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.subscriptions_hist
UNION ALL
SELECT 'SUBSCRIPTIONS_HIST.status_cd' AS col, COUNT(*) - COUNT(`status_cd`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.subscriptions_hist
UNION ALL
SELECT 'SUBSCRIPTIONS_HIST.suspended_on' AS col, COUNT(*) - COUNT(`suspended_on`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.subscriptions_hist
UNION ALL
SELECT 'TENANTS.status_cd' AS col, COUNT(*) - COUNT(`status_cd`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.tenants
UNION ALL
SELECT 'CREDIT_NOTES.issued_on' AS col, COUNT(*) - COUNT(`issued_on`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.credit_notes
UNION ALL
SELECT 'CREDIT_NOTES.amount' AS col, COUNT(*) - COUNT(`amount`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.credit_notes
UNION ALL
SELECT 'CREDIT_NOTES.remaining_amount' AS col, COUNT(*) - COUNT(`remaining_amount`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.credit_notes
UNION ALL
SELECT 'NOTIFICATIONS.kind_cd' AS col, COUNT(*) - COUNT(`kind_cd`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.notifications
UNION ALL
SELECT 'NOTIFICATIONS.sent_at' AS col, COUNT(*) - COUNT(`sent_at`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.notifications
UNION ALL
SELECT 'RATING_PERIODS.period_start' AS col, COUNT(*) - COUNT(`period_start`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.rating_periods
UNION ALL
SELECT 'RATING_PERIODS.period_end' AS col, COUNT(*) - COUNT(`period_end`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.rating_periods
UNION ALL
SELECT 'SUBSCRIPTIONS.starts_on' AS col, COUNT(*) - COUNT(`starts_on`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.subscriptions
UNION ALL
SELECT 'SUBSCRIPTIONS.ends_on' AS col, COUNT(*) - COUNT(`ends_on`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.subscriptions
UNION ALL
SELECT 'SUBSCRIPTIONS.status_cd' AS col, COUNT(*) - COUNT(`status_cd`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.subscriptions
UNION ALL
SELECT 'SUBSCRIPTIONS.suspended_on' AS col, COUNT(*) - COUNT(`suspended_on`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.subscriptions
UNION ALL
SELECT 'USAGE_EVENTS.occurred_at' AS col, COUNT(*) - COUNT(`occurred_at`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.usage_events
UNION ALL
SELECT 'USAGE_EVENTS.units' AS col, COUNT(*) - COUNT(`units`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.usage_events
UNION ALL
SELECT 'USAGE_EVENTS.kind_cd' AS col, COUNT(*) - COUNT(`kind_cd`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.usage_events
UNION ALL
SELECT 'INVOICES.issued_at' AS col, COUNT(*) - COUNT(`issued_at`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.invoices
UNION ALL
SELECT 'INVOICES.subtotal' AS col, COUNT(*) - COUNT(`subtotal`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.invoices
UNION ALL
SELECT 'INVOICES.tax' AS col, COUNT(*) - COUNT(`tax`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.invoices
UNION ALL
SELECT 'INVOICES.total' AS col, COUNT(*) - COUNT(`total`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.invoices
UNION ALL
SELECT 'INVOICES.status_cd' AS col, COUNT(*) - COUNT(`status_cd`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.invoices
UNION ALL
SELECT 'RATING_RESULTS.used_units' AS col, COUNT(*) - COUNT(`used_units`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.rating_results
UNION ALL
SELECT 'RATING_RESULTS.quota_units' AS col, COUNT(*) - COUNT(`quota_units`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.rating_results
UNION ALL
SELECT 'RATING_RESULTS.rollover_units' AS col, COUNT(*) - COUNT(`rollover_units`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.rating_results
UNION ALL
SELECT 'RATING_RESULTS.billable_units' AS col, COUNT(*) - COUNT(`billable_units`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.rating_results
UNION ALL
SELECT 'RATING_RESULTS.overage_amount' AS col, COUNT(*) - COUNT(`overage_amount`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.rating_results
UNION ALL
SELECT 'RATING_RESULTS.created_at' AS col, COUNT(*) - COUNT(`created_at`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.rating_results
UNION ALL
SELECT 'DUNNING_ATTEMPTS.attempt_no' AS col, COUNT(*) - COUNT(`attempt_no`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.dunning_attempts
UNION ALL
SELECT 'DUNNING_ATTEMPTS.scheduled_for' AS col, COUNT(*) - COUNT(`scheduled_for`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.dunning_attempts
UNION ALL
SELECT 'DUNNING_ATTEMPTS.status_cd' AS col, COUNT(*) - COUNT(`status_cd`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.dunning_attempts
UNION ALL
SELECT 'INVOICE_LINES.line_no' AS col, COUNT(*) - COUNT(`line_no`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.invoice_lines
UNION ALL
SELECT 'INVOICE_LINES.amount' AS col, COUNT(*) - COUNT(`amount`) AS null_rows FROM ow_tp.mig_unt19_20261030_src.invoice_lines
ORDER BY col;
