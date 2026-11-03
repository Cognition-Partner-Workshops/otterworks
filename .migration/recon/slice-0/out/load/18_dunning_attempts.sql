CREATE OR REPLACE TABLE ow_tp.mig_unt19_20261030_src.dunning_attempts
COMMENT 'frozen snapshot of OW_BILLING.DUNNING_ATTEMPTS exported 2026-10-31T22:31:25+00:00 (run unt19-20261030, slice-0 access)'
AS SELECT
  `id`,
  `tenant_id`,
  `invoice_id`,
  CAST(`attempt_no` AS BIGINT) AS `attempt_no`,
  CAST(`scheduled_for` AS TIMESTAMP_NTZ) AS `scheduled_for`,
  CAST(`status_cd` AS BIGINT) AS `status_cd`
FROM read_files('/Volumes/ow_tp/mig_unt19_20261030_src/export/DUNNING_ATTEMPTS.csv', format => 'csv', header => true, multiLine => true,
  escape => '"', nullValue => '', inferSchema => false, mode => 'FAILFAST',
  schema => '`id` string, `tenant_id` string, `invoice_id` string, `attempt_no` string, `scheduled_for` string, `status_cd` string');
