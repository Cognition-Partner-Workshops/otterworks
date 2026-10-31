CREATE OR REPLACE TABLE ow_tp.mig_unt19_20261030_src.invoice_line
COMMENT 'frozen snapshot of OW_BILLING.INVOICE_LINE exported 2026-10-31T22:31:25+00:00 (run unt19-20261030, slice-0 access)'
AS SELECT
  `line_id`,
  `invoice_no`,
  `invoice_id`,
  `cust_id`,
  `cust_no`,
  `cust_name`,
  `tenant_id`,
  CAST(`line_no` AS BIGINT) AS `line_no`,
  CAST(`line_type_cd` AS BIGINT) AS `line_type_cd`,
  `item_desc`,
  CAST(`qty` AS DECIMAL(12,3)) AS `qty`,
  CAST(`unit_price` AS DECIMAL(14,4)) AS `unit_price`,
  CAST(`amount` AS DECIMAL(14,2)) AS `amount`,
  CAST(`tax_amt` AS DECIMAL(14,2)) AS `tax_amt`,
  `invoice_dt`,
  `service_period`,
  `posted_yn`,
  `gl_acct_csv`,
  CAST(`batch_no` AS BIGINT) AS `batch_no`,
  `src_system`
FROM read_files('/Volumes/ow_tp/mig_unt19_20261030_src/export/INVOICE_LINE.csv', format => 'csv', header => true, multiLine => true,
  escape => '"', nullValue => '', inferSchema => false, mode => 'FAILFAST',
  schema => '`line_id` string, `invoice_no` string, `invoice_id` string, `cust_id` string, `cust_no` string, `cust_name` string, `tenant_id` string, `line_no` string, `line_type_cd` string, `item_desc` string, `qty` string, `unit_price` string, `amount` string, `tax_amt` string, `invoice_dt` string, `service_period` string, `posted_yn` string, `gl_acct_csv` string, `batch_no` string, `src_system` string');
