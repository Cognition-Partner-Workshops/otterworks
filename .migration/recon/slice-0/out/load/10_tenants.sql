CREATE OR REPLACE TABLE ow_tp.mig_unt19_20261030_src.tenants
COMMENT 'frozen snapshot of OW_BILLING.TENANTS exported 2026-10-31T22:31:25+00:00 (run unt19-20261030, slice-0 access)'
AS SELECT
  `id`,
  `name`,
  `tax_exempt_yn`,
  CAST(`status_cd` AS BIGINT) AS `status_cd`
FROM read_files('/Volumes/ow_tp/mig_unt19_20261030_src/export/TENANTS.csv', format => 'csv', header => true, multiLine => true,
  escape => '"', nullValue => '', inferSchema => false, mode => 'FAILFAST',
  schema => '`id` string, `name` string, `tax_exempt_yn` string, `status_cd` string');
