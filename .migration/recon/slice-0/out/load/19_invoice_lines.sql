CREATE OR REPLACE TABLE ow_tp.mig_unt19_20261030_src.invoice_lines
COMMENT 'frozen snapshot of OW_BILLING.INVOICE_LINES exported 2026-10-31T22:31:25+00:00 (run unt19-20261030, slice-0 access)'
AS SELECT
  `id`,
  `invoice_id`,
  CAST(`line_no` AS BIGINT) AS `line_no`,
  `line_type`,
  `description`,
  CAST(`amount` AS DECIMAL(12,2)) AS `amount`
FROM read_files('/Volumes/ow_tp/mig_unt19_20261030_src/export/INVOICE_LINES.csv', format => 'csv', header => true, multiLine => true,
  escape => '"', nullValue => '', inferSchema => false, mode => 'FAILFAST',
  schema => '`id` string, `invoice_id` string, `line_no` string, `line_type` string, `description` string, `amount` string');
