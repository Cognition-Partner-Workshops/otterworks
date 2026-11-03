CREATE OR REPLACE TABLE ow_tp.mig_unt19_20261030_src.invoices
COMMENT 'frozen snapshot of OW_BILLING.INVOICES exported 2026-10-31T22:31:25+00:00 (run unt19-20261030, slice-0 access)'
AS SELECT
  `id`,
  `tenant_id`,
  `period_id`,
  CAST(`issued_at` AS TIMESTAMP_NTZ) AS `issued_at`,
  CAST(`subtotal` AS DECIMAL(12,2)) AS `subtotal`,
  CAST(`tax` AS DECIMAL(12,2)) AS `tax`,
  CAST(`total` AS DECIMAL(12,2)) AS `total`,
  CAST(`status_cd` AS BIGINT) AS `status_cd`
FROM read_files('/Volumes/ow_tp/mig_unt19_20261030_src/export/INVOICES.csv', format => 'csv', header => true, multiLine => true,
  escape => '"', nullValue => '', inferSchema => false, mode => 'FAILFAST',
  schema => '`id` string, `tenant_id` string, `period_id` string, `issued_at` string, `subtotal` string, `tax` string, `total` string, `status_cd` string');
