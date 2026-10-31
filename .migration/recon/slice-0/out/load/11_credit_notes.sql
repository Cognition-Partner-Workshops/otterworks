CREATE OR REPLACE TABLE ow_tp.mig_unt19_20261030_src.credit_notes
COMMENT 'frozen snapshot of OW_BILLING.CREDIT_NOTES exported 2026-10-31T22:31:25+00:00 (run unt19-20261030, slice-0 access)'
AS SELECT
  `id`,
  `tenant_id`,
  CAST(`issued_on` AS TIMESTAMP_NTZ) AS `issued_on`,
  CAST(`amount` AS DECIMAL(12,2)) AS `amount`,
  CAST(`remaining_amount` AS DECIMAL(12,2)) AS `remaining_amount`
FROM read_files('/Volumes/ow_tp/mig_unt19_20261030_src/export/CREDIT_NOTES.csv', format => 'csv', header => true, multiLine => true,
  escape => '"', nullValue => '', inferSchema => false, mode => 'FAILFAST',
  schema => '`id` string, `tenant_id` string, `issued_on` string, `amount` string, `remaining_amount` string');
