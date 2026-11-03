CREATE OR REPLACE TABLE ow_tp.mig_unt19_20261030_src.usage_events
COMMENT 'frozen snapshot of OW_BILLING.USAGE_EVENTS exported 2026-10-31T22:31:25+00:00 (run unt19-20261030, slice-0 access)'
AS SELECT
  `id`,
  `tenant_id`,
  CAST(`occurred_at` AS TIMESTAMP_NTZ) AS `occurred_at`,
  CAST(`units` AS BIGINT) AS `units`,
  CAST(`kind_cd` AS BIGINT) AS `kind_cd`
FROM read_files('/Volumes/ow_tp/mig_unt19_20261030_src/export/USAGE_EVENTS.csv', format => 'csv', header => true, multiLine => true,
  escape => '"', nullValue => '', inferSchema => false, mode => 'FAILFAST',
  schema => '`id` string, `tenant_id` string, `occurred_at` string, `units` string, `kind_cd` string');
