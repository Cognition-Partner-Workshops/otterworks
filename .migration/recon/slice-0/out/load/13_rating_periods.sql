CREATE OR REPLACE TABLE ow_tp.mig_unt19_20261030_src.rating_periods
COMMENT 'frozen snapshot of OW_BILLING.RATING_PERIODS exported 2026-10-31T22:31:25+00:00 (run unt19-20261030, slice-0 access)'
AS SELECT
  `id`,
  `tenant_id`,
  CAST(`period_start` AS TIMESTAMP_NTZ) AS `period_start`,
  CAST(`period_end` AS TIMESTAMP_NTZ) AS `period_end`
FROM read_files('/Volumes/ow_tp/mig_unt19_20261030_src/export/RATING_PERIODS.csv', format => 'csv', header => true, multiLine => true,
  escape => '"', nullValue => '', inferSchema => false, mode => 'FAILFAST',
  schema => '`id` string, `tenant_id` string, `period_start` string, `period_end` string');
