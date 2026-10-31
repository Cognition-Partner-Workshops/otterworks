CREATE OR REPLACE TABLE ow_tp.mig_unt19_20261030_src.subscriptions_hist
COMMENT 'frozen snapshot of OW_BILLING.SUBSCRIPTIONS_HIST exported 2026-10-31T22:31:25+00:00 (run unt19-20261030, slice-0 access)'
AS SELECT
  CAST(`hist_id` AS BIGINT) AS `hist_id`,
  `hist_dt`,
  `hist_op`,
  `id`,
  `tenant_id`,
  `plan_id`,
  CAST(`starts_on` AS TIMESTAMP_NTZ) AS `starts_on`,
  CAST(`ends_on` AS TIMESTAMP_NTZ) AS `ends_on`,
  CAST(`status_cd` AS BIGINT) AS `status_cd`,
  CAST(`suspended_on` AS TIMESTAMP_NTZ) AS `suspended_on`
FROM read_files('/Volumes/ow_tp/mig_unt19_20261030_src/export/SUBSCRIPTIONS_HIST.csv', format => 'csv', header => true, multiLine => true,
  escape => '"', nullValue => '', inferSchema => false, mode => 'FAILFAST',
  schema => '`hist_id` string, `hist_dt` string, `hist_op` string, `id` string, `tenant_id` string, `plan_id` string, `starts_on` string, `ends_on` string, `status_cd` string, `suspended_on` string');
