CREATE OR REPLACE TABLE ow_tp.mig_unt19_20261030_src.plans
COMMENT 'frozen snapshot of OW_BILLING.PLANS exported 2026-10-31T22:31:25+00:00 (run unt19-20261030, slice-0 access)'
AS SELECT
  `id`,
  `code`,
  CAST(`tier_cd` AS BIGINT) AS `tier_cd`,
  CAST(`monthly_fee` AS DECIMAL(12,2)) AS `monthly_fee`,
  CAST(`included_units` AS BIGINT) AS `included_units`,
  CAST(`overage_rate` AS DECIMAL(12,6)) AS `overage_rate`,
  `active_yn`
FROM read_files('/Volumes/ow_tp/mig_unt19_20261030_src/export/PLANS.csv', format => 'csv', header => true, multiLine => true,
  escape => '"', nullValue => '', inferSchema => false, mode => 'FAILFAST',
  schema => '`id` string, `code` string, `tier_cd` string, `monthly_fee` string, `included_units` string, `overage_rate` string, `active_yn` string');
