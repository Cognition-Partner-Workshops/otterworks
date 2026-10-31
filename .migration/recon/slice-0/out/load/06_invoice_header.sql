CREATE OR REPLACE TABLE ow_tp.mig_unt19_20261030_src.invoice_header
COMMENT 'frozen snapshot of OW_BILLING.INVOICE_HEADER exported 2026-10-31T22:31:25+00:00 (run unt19-20261030, slice-0 access)'
AS SELECT
  `invoice_id`,
  `invoice_no`,
  `cust_id`,
  `tenant_id`,
  `invoice_dt`,
  `due_dt`,
  CAST(`status_cd` AS BIGINT) AS `status_cd`,
  CAST(`total_amt` AS DECIMAL(14,2)) AS `total_amt`,
  CAST(`batch_no` AS BIGINT) AS `batch_no`
FROM read_files('/Volumes/ow_tp/mig_unt19_20261030_src/export/INVOICE_HEADER.csv', format => 'csv', header => true, multiLine => true,
  escape => '"', nullValue => '', inferSchema => false, mode => 'FAILFAST',
  schema => '`invoice_id` string, `invoice_no` string, `cust_id` string, `tenant_id` string, `invoice_dt` string, `due_dt` string, `status_cd` string, `total_amt` string, `batch_no` string');
