CREATE OR REPLACE TABLE ow_tp.mig_unt19_20261030_src.rating_results
COMMENT 'frozen snapshot of OW_BILLING.RATING_RESULTS exported 2026-10-31T22:31:25+00:00 (run unt19-20261030, slice-0 access)'
AS SELECT
  `id`,
  `period_id`,
  `subscription_id`,
  CAST(`used_units` AS BIGINT) AS `used_units`,
  CAST(`quota_units` AS BIGINT) AS `quota_units`,
  CAST(`rollover_units` AS BIGINT) AS `rollover_units`,
  CAST(`billable_units` AS BIGINT) AS `billable_units`,
  CAST(`overage_amount` AS DECIMAL(12,2)) AS `overage_amount`,
  CAST(`created_at` AS TIMESTAMP_NTZ) AS `created_at`
FROM read_files('/Volumes/ow_tp/mig_unt19_20261030_src/export/RATING_RESULTS.csv', format => 'csv', header => true, multiLine => true,
  escape => '"', nullValue => '', inferSchema => false, mode => 'FAILFAST',
  schema => '`id` string, `period_id` string, `subscription_id` string, `used_units` string, `quota_units` string, `rollover_units` string, `billable_units` string, `overage_amount` string, `created_at` string');
