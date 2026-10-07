# Reconciliation: legacy-billing-oracle-to-postgres (ns=demo)

Generated 2026-10-07T13:52:49Z, run mode `live`. Expected values are read live from Oracle `OW_BILLING` (FREEPDB1) or the seed manifest; actual values are recomputed from the PostgreSQL 15 target `ow_tp_billing.ow_billing`.

**Result: 167/167 checks pass.**

| Table | Check | Oracle (expected) | Postgres (actual) | Result | Detail |
|---|---|---|---|---|---|
| `codes` | columns | 3 | 3 | pass | same column names on both sides |
| `codes` | row_count | 32 | 32 | pass |  |
| `codes` | key_coverage(code_type, code_val) | 32 | 32 | pass | missing=0 extra=0 |
| `codes` | row_checksum(all columns) | 94a8fd1b348545452b6661a80dbf1c3b | 94a8fd1b348545452b6661a80dbf1c3b | pass | order-independent md5 over every column of every row |
| `tenants` | columns | 4 | 4 | pass | same column names on both sides |
| `tenants` | row_count | 70 | 70 | pass |  |
| `tenants` | key_coverage(id) | 70 | 70 | pass | missing=0 extra=0 |
| `tenants` | row_checksum(all columns) | fe2e277cda859075735fd283df0c0750 | fe2e277cda859075735fd283df0c0750 | pass | order-independent md5 over every column of every row |
| `plans` | columns | 7 | 7 | pass | same column names on both sides |
| `plans` | row_count | 3 | 3 | pass |  |
| `plans` | sum(monthly_fee) | 697 | 697 | pass |  |
| `plans` | sum(overage_rate) | 0.11 | 0.11 | pass |  |
| `plans` | key_coverage(id) | 3 | 3 | pass | missing=0 extra=0 |
| `plans` | row_checksum(all columns) | 254b37df2fc03818e980ab9976d98f12 | 254b37df2fc03818e980ab9976d98f12 | pass | order-independent md5 over every column of every row |
| `subscriptions` | columns | 7 | 7 | pass | same column names on both sides |
| `subscriptions` | row_count | 70 | 70 | pass |  |
| `subscriptions` | key_coverage(id) | 70 | 70 | pass | missing=0 extra=0 |
| `subscriptions` | row_checksum(all columns) | 55e44e6e5e5d37600762064af9991b61 | 55e44e6e5e5d37600762064af9991b61 | pass | order-independent md5 over every column of every row |
| `usage_events` | columns | 5 | 5 | pass | same column names on both sides |
| `usage_events` | row_count | 817 | 817 | pass |  |
| `usage_events` | key_coverage(id) | 817 | 817 | pass | missing=0 extra=0 |
| `usage_events` | row_checksum(all columns) | bddeb68d3146be6f2adf06de193d231a | bddeb68d3146be6f2adf06de193d231a | pass | order-independent md5 over every column of every row |
| `rating_periods` | columns | 4 | 4 | pass | same column names on both sides |
| `rating_periods` | row_count | 3 | 3 | pass |  |
| `rating_periods` | key_coverage(id) | 3 | 3 | pass | missing=0 extra=0 |
| `rating_periods` | row_checksum(all columns) | 32b590aa74a6e006ebff022e4cd6125c | 32b590aa74a6e006ebff022e4cd6125c | pass | order-independent md5 over every column of every row |
| `rating_results` | columns | 9 | 9 | pass | same column names on both sides |
| `rating_results` | row_count | 3 | 3 | pass |  |
| `rating_results` | sum(overage_amount) | 0 | 0 | pass |  |
| `rating_results` | key_coverage(id) | 3 | 3 | pass | missing=0 extra=0 |
| `rating_results` | row_checksum(all columns) | f71df407c308b436fa761cbd82fe2b8f | f71df407c308b436fa761cbd82fe2b8f | pass | order-independent md5 over every column of every row |
| `invoices` | columns | 8 | 8 | pass | same column names on both sides |
| `invoices` | row_count | 4 | 4 | pass |  |
| `invoices` | sum(subtotal) | 496 | 496 | pass |  |
| `invoices` | sum(tax) | 40.91 | 40.91 | pass |  |
| `invoices` | sum(total) | 536.91 | 536.91 | pass |  |
| `invoices` | key_coverage(id) | 4 | 4 | pass | missing=0 extra=0 |
| `invoices` | row_checksum(all columns) | ab8a9983f4772297abbe6e88e9726820 | ab8a9983f4772297abbe6e88e9726820 | pass | order-independent md5 over every column of every row |
| `invoice_lines` | columns | 6 | 6 | pass | same column names on both sides |
| `invoice_lines` | row_count | 4 | 4 | pass |  |
| `invoice_lines` | sum(amount) | 322.58 | 322.58 | pass |  |
| `invoice_lines` | key_coverage(id) | 4 | 4 | pass | missing=0 extra=0 |
| `invoice_lines` | row_checksum(all columns) | 1bf2c82721c9b8744f6e20db0a22ec2b | 1bf2c82721c9b8744f6e20db0a22ec2b | pass | order-independent md5 over every column of every row |
| `credit_notes` | columns | 5 | 5 | pass | same column names on both sides |
| `credit_notes` | row_count | 5 | 5 | pass |  |
| `credit_notes` | sum(amount) | 145 | 145 | pass |  |
| `credit_notes` | sum(remaining_amount) | 145 | 145 | pass |  |
| `credit_notes` | key_coverage(id) | 5 | 5 | pass | missing=0 extra=0 |
| `credit_notes` | row_checksum(all columns) | d119e52221ba300353a601f8f0dbaba1 | d119e52221ba300353a601f8f0dbaba1 | pass | order-independent md5 over every column of every row |
| `dunning_attempts` | columns | 6 | 6 | pass | same column names on both sides |
| `dunning_attempts` | row_count | 1 | 1 | pass |  |
| `dunning_attempts` | key_coverage(id) | 1 | 1 | pass | missing=0 extra=0 |
| `dunning_attempts` | row_checksum(all columns) | 6c197afb3d4529093b4cc18ddb3d4763 | 6c197afb3d4529093b4cc18ddb3d4763 | pass | order-independent md5 over every column of every row |
| `notifications` | columns | 4 | 4 | pass | same column names on both sides |
| `notifications` | row_count | 1 | 1 | pass |  |
| `notifications` | key_coverage(id) | 1 | 1 | pass | missing=0 extra=0 |
| `notifications` | row_checksum(all columns) | f0936e34843640b37d792fe9034e96ce | f0936e34843640b37d792fe9034e96ce | pass | order-independent md5 over every column of every row |
| `billing_audit_log` | columns | 4 | 4 | pass | same column names on both sides |
| `billing_audit_log` | row_count | 0 | 0 | pass |  |
| `billing_audit_log` | key_coverage(log_id) | 0 | 0 | pass | missing=0 extra=0 |
| `billing_audit_log` | row_checksum(all columns) | 00000000000000000000000000000000 | 00000000000000000000000000000000 | pass | order-independent md5 over every column of every row |
| `subscriptions_hist` | columns | 10 | 10 | pass | same column names on both sides |
| `subscriptions_hist` | row_count | 0 | 0 | pass |  |
| `subscriptions_hist` | key_coverage(hist_id) | 0 | 0 | pass | missing=0 extra=0 |
| `subscriptions_hist` | row_checksum(all columns) | 00000000000000000000000000000000 | 00000000000000000000000000000000 | pass | order-independent md5 over every column of every row |
| `fixture_meta` | columns | 3 | 3 | pass | same column names on both sides |
| `fixture_meta` | row_count | 2 | 2 | pass |  |
| `fixture_meta` | key_coverage(marker) | 2 | 2 | pass | missing=0 extra=0 |
| `fixture_meta` | row_checksum(all columns) | 5e3bec4d69243ec7399f245b09a8fbf3 | 5e3bec4d69243ec7399f245b09a8fbf3 | pass | order-independent md5 over every column of every row |
| `customer_master` | columns | 155 | 155 | pass | same column names on both sides |
| `customer_master` | row_count | 25001 | 25001 | pass |  |
| `customer_master` | sum(cur_bal_amt) | 39799599.31 | 39799599.31 | pass |  |
| `customer_master` | sum(past_due_amt) | 7330214.66 | 7330214.66 | pass |  |
| `customer_master` | sum(ytd_billed_amt) | 208213120.84 | 208213120.84 | pass |  |
| `customer_master` | sum(ltd_billed_amt) | 149 | 149 | pass |  |
| `customer_master` | sum(ytd_paid_amt) | 149 | 149 | pass |  |
| `customer_master` | sum(credit_limit_amt) | 330006000 | 330006000 | pass |  |
| `customer_master` | sum(udf_amt_01) | NULL | NULL | pass |  |
| `customer_master` | sum(udf_amt_02) | NULL | NULL | pass |  |
| `customer_master` | sum(udf_amt_03) | NULL | NULL | pass |  |
| `customer_master` | sum(udf_amt_04) | NULL | NULL | pass |  |
| `customer_master` | sum(udf_amt_05) | NULL | NULL | pass |  |
| `customer_master` | sum(udf_amt_06) | NULL | NULL | pass |  |
| `customer_master` | sum(udf_amt_07) | NULL | NULL | pass |  |
| `customer_master` | sum(udf_amt_08) | NULL | NULL | pass |  |
| `customer_master` | sum(udf_amt_09) | NULL | NULL | pass |  |
| `customer_master` | sum(udf_amt_10) | NULL | NULL | pass |  |
| `customer_master` | key_coverage(cust_id) | 25001 | 25001 | pass | missing=0 extra=0 |
| `customer_master` | row_checksum(all columns) | 99050de06edc89347b7d36b12e08660f | 99050de06edc89347b7d36b12e08660f | pass | order-independent md5 over every column of every row |
| `customer_master_hist` | columns | 158 | 158 | pass | same column names on both sides |
| `customer_master_hist` | row_count | 0 | 0 | pass |  |
| `customer_master_hist` | sum(cur_bal_amt) | NULL | NULL | pass |  |
| `customer_master_hist` | sum(past_due_amt) | NULL | NULL | pass |  |
| `customer_master_hist` | sum(ytd_billed_amt) | NULL | NULL | pass |  |
| `customer_master_hist` | sum(ltd_billed_amt) | NULL | NULL | pass |  |
| `customer_master_hist` | sum(ytd_paid_amt) | NULL | NULL | pass |  |
| `customer_master_hist` | sum(credit_limit_amt) | NULL | NULL | pass |  |
| `customer_master_hist` | sum(udf_amt_01) | NULL | NULL | pass |  |
| `customer_master_hist` | sum(udf_amt_02) | NULL | NULL | pass |  |
| `customer_master_hist` | sum(udf_amt_03) | NULL | NULL | pass |  |
| `customer_master_hist` | sum(udf_amt_04) | NULL | NULL | pass |  |
| `customer_master_hist` | sum(udf_amt_05) | NULL | NULL | pass |  |
| `customer_master_hist` | sum(udf_amt_06) | NULL | NULL | pass |  |
| `customer_master_hist` | sum(udf_amt_07) | NULL | NULL | pass |  |
| `customer_master_hist` | sum(udf_amt_08) | NULL | NULL | pass |  |
| `customer_master_hist` | sum(udf_amt_09) | NULL | NULL | pass |  |
| `customer_master_hist` | sum(udf_amt_10) | NULL | NULL | pass |  |
| `customer_master_hist` | key_coverage(hist_id) | 0 | 0 | pass | missing=0 extra=0 |
| `customer_master_hist` | row_checksum(all columns) | 00000000000000000000000000000000 | 00000000000000000000000000000000 | pass | order-independent md5 over every column of every row |
| `entity_attr_value` | columns | 7 | 7 | pass | same column names on both sides |
| `entity_attr_value` | row_count | 8337 | 8337 | pass |  |
| `entity_attr_value` | key_coverage(eav_id) | 8337 | 8337 | pass | missing=0 extra=0 |
| `entity_attr_value` | row_checksum(all columns) | 2a24c321d4a7b27f25bc3105e3838618 | 2a24c321d4a7b27f25bc3105e3838618 | pass | order-independent md5 over every column of every row |
| `invoice_header` | columns | 9 | 9 | pass | same column names on both sides |
| `invoice_header` | row_count | 18750 | 18750 | pass |  |
| `invoice_header` | sum(total_amt) | 187618458.58 | 187618458.58 | pass |  |
| `invoice_header` | key_coverage(invoice_id) | 18750 | 18750 | pass | missing=0 extra=0 |
| `invoice_header` | row_checksum(all columns) | 2e8324c8beaa1bf8a0063c3e2b2c7032 | 2e8324c8beaa1bf8a0063c3e2b2c7032 | pass | order-independent md5 over every column of every row |
| `invoice_line` | columns | 20 | 20 | pass | same column names on both sides |
| `invoice_line` | row_count | 150000 | 150000 | pass | 150000 = 149963 + 37 (invoice_line + invoice_line_orphan) |
| `invoice_line` | sum(qty) | 37559773 | 37559773 | pass | 37551539 + 8234 |
| `invoice_line` | sum(unit_price) | 7412636.4387 | 7412636.4387 | pass | 7410996.6001 + 1639.8386 |
| `invoice_line` | sum(amount) | 1855870025.91 | 1855870025.91 | pass | 1855479906.85 + 390119.06 |
| `invoice_line` | sum(tax_amt) | 153109280.16 | 153109280.16 | pass | 153077095.36 + 32184.8 |
| `invoice_line` | key_coverage(line_id) | 150000 | 150000 | pass | missing=0 extra=0 in-both-tables=0 |
| `invoice_line` | row_checksum(all columns) | 86b10023d30cd9bae24bf1fea18f1707 | 86b10023d30cd9bae24bf1fea18f1707 | pass | order-independent md5 over every column of every row (orphan rows without quarantine_reason) |
| `invoice_line_orphan` | row_count | 37 | 37 | pass |  |
| `invoice_line_orphan` | sum(amount) | 390119.06 | 390119.06 | pass |  |
| `invoice_line_orphan` | sum(tax_amt) | 32184.8 | 32184.8 | pass |  |
| `invoice_line_orphan` | key_coverage(line_id) | 37 | 37 | pass | missing=0 extra=0 |
| `invoice_line_orphan` | quarantine_reason populated | 37 | 37 | pass | no INVOICE_HEADER row for invoice_id (Oracle had no FK); held for Finance review x37 |
| `invoice_line` | valid rows (with header) | 149963 | 149963 | pass |  |
| `invoice_line` | valid sum(amount) | 1855479906.85 | 1855479906.85 | pass |  |
| `invoice_line` | valid sum(tax_amt) | 153077095.36 | 153077095.36 | pass |  |
| `credit_notes` | ref_coverage(tenant_id -> tenants.id) | 5/5 | 5/5 | pass | FK fk_cn_tenant; oracle 5/5 covered, postgres 5/5 |
| `dunning_attempts` | ref_coverage(invoice_id -> invoices.id) | 1/1 | 1/1 | pass | FK fk_da_invoice; oracle 1/1 covered, postgres 1/1 |
| `dunning_attempts` | ref_coverage(tenant_id -> tenants.id) | 1/1 | 1/1 | pass | FK fk_da_tenant; oracle 1/1 covered, postgres 1/1 |
| `invoice_line` | ref_coverage(invoice_id -> invoice_header.invoice_id) | 149963 covered + 37 uncovered | 149963 in invoice_line + 37 in invoice_line_orphan | pass | FK fk_invoice_line_header; oracle 149963/150000 covered, postgres 149963/149963; invoice_line_orphan 0/37 covered (quarantined because uncovered) |
| `invoice_lines` | ref_coverage(invoice_id -> invoices.id) | 4/4 | 4/4 | pass | FK fk_il_invoice; oracle 4/4 covered, postgres 4/4 |
| `invoices` | ref_coverage(period_id -> rating_periods.id) | 4/4 | 4/4 | pass | FK fk_inv_period; oracle 4/4 covered, postgres 4/4 |
| `invoices` | ref_coverage(tenant_id -> tenants.id) | 4/4 | 4/4 | pass | FK fk_inv_tenant; oracle 4/4 covered, postgres 4/4 |
| `notifications` | ref_coverage(tenant_id -> tenants.id) | 1/1 | 1/1 | pass | FK fk_notif_tenant; oracle 1/1 covered, postgres 1/1 |
| `rating_periods` | ref_coverage(tenant_id -> tenants.id) | 3/3 | 3/3 | pass | FK fk_rp_tenant; oracle 3/3 covered, postgres 3/3 |
| `rating_results` | ref_coverage(period_id -> rating_periods.id) | 3/3 | 3/3 | pass | FK fk_rr_period; oracle 3/3 covered, postgres 3/3 |
| `rating_results` | ref_coverage(subscription_id -> subscriptions.id) | 3/3 | 3/3 | pass | FK fk_rr_sub; oracle 3/3 covered, postgres 3/3 |
| `subscriptions` | ref_coverage(plan_id -> plans.id) | 70/70 | 70/70 | pass | FK fk_sub_plan; oracle 70/70 covered, postgres 70/70 |
| `subscriptions` | ref_coverage(tenant_id -> tenants.id) | 70/70 | 70/70 | pass | FK fk_sub_tenant; oracle 70/70 covered, postgres 70/70 |
| `usage_events` | ref_coverage(tenant_id -> tenants.id) | 817/817 | 817/817 | pass | FK fk_usage_tenant; oracle 817/817 covered, postgres 817/817 |
| `invoice_line` | ref_coverage(cust_id -> customer_master.cust_id) | 150000/150000 | 150000/150000 | pass | logical ref (not enforced); oracle 150000/150000 covered, postgres 150000/150000 (invoice_line + invoice_line_orphan) |
| `invoice_header` | ref_coverage(cust_id -> customer_master.cust_id) | 18750/18750 | 18750/18750 | pass | logical ref (not enforced); oracle 18750/18750 covered, postgres 18750/18750 |
| `entity_attr_value` | ref_coverage(entity_id -> customer_master.cust_id) | 8337/8337 | 8337/8337 | pass | logical ref (not enforced); oracle 8337/8337 covered, postgres 8337/8337 |
| `seq_billing_audit_log` | next_value | 1 | 1 | pass |  |
| `seq_subscriptions_hist` | next_value | 1 | 1 | pass |  |
| `seq_customer_master` | next_value | 125001 | 125001 | pass |  |
| `seq_customer_master_hist` | next_value | 1 | 1 | pass |  |
| `seq_entity_attr_value` | next_value | 11001 | 11001 | pass |  |
| `(schema)` | named constraints carried over | 38 | 38 | pass | missing=none; added in Postgres=['fk_invoice_line_header', 'pk_invoice_line_orphan', 'pk_migration_baseline'] |
| `customer_master` | seed rows (ns=demo) | 25000 | 25000 | pass |  |
| `entity_attr_value` | seed rows (ns=demo) | 8333 | 8333 | pass |  |
| `invoice_header` | seed rows (ns=demo) | 18750 | 18750 | pass |  |
| `invoice_line` | seed rows (ns=demo) | 150000 | 150000 | pass |  |
| `tenants` | seed rows (ns=demo) | 60 | 60 | pass |  |
| `customer_master` | seed checksum(cust_id, cur_bal_amt) (ns=demo) | 4f92feef2ad58dbab30e289957931928 | 4f92feef2ad58dbab30e289957931928 | pass |  |
| `invoice_line` | seed checksum(line_id, amount) (ns=demo) | 88a66751f0b08b476b492105a2efc537 | 88a66751f0b08b476b492105a2efc537 | pass | over invoice_line + invoice_line_orphan |
| `invoice_line` | anomaly orphaned_rows (ns=demo) | 37 | 37 | pass | oracle.OW_BILLING.INVOICE_LINE |
| `customer_master` | anomaly dirty_dates (ns=demo) | 50 | 50 | pass | oracle.OW_BILLING.CUSTOMER_MASTER.SIGNUP_DT |
| `customer_master` | anomaly malformed_csv_lists (ns=demo) | 31 | 31 | pass | oracle.OW_BILLING.CUSTOMER_MASTER.RELATED_ACCT_IDS |

**Idempotency rerun:** pass. migrate.py executed again against the loaded target; 27 objects (22 tables + 5 sequences) fingerprinted before and after (row count + order-independent md5 of every column): identical; fingerprint sha256[:16]=91f8d80e20bb82f4

**Planted anomalies** (manifest vs detected on Postgres): expected ['dirty_dates:oracle.OW_BILLING.CUSTOMER_MASTER.SIGNUP_DT:50', 'malformed_csv_lists:oracle.OW_BILLING.CUSTOMER_MASTER.RELATED_ACCT_IDS:31', 'orphaned_rows:oracle.OW_BILLING.INVOICE_LINE:37'], detected ['dirty_dates:oracle.OW_BILLING.CUSTOMER_MASTER.SIGNUP_DT:50', 'malformed_csv_lists:oracle.OW_BILLING.CUSTOMER_MASTER.RELATED_ACCT_IDS:31', 'orphaned_rows:oracle.OW_BILLING.INVOICE_LINE:37'], missing none, unexpected none.

**Unverified paths:**

- pkg_ow_util.log_msg: Oracle wrote BILLING_AUDIT_LOG in an autonomous transaction; on Postgres the log row commits or rolls back with the caller. Only the commit path is exercised by the parity run.
- pkg_jobs.job_nightly_dunning / job_purge_audit_log: the DBMS_SCHEDULER jobs were created DISABLED in Oracle and never ran; the Postgres procedure bodies exist but no scheduler is wired and they were not executed.
- Concurrent writers: Oracle row-lock behaviour (SELECT ... FOR UPDATE in sp_change_plan) is ported but not exercised under concurrency.
- Scales other than demo (SCALE=ci/full) were not migrated or reconciled.
