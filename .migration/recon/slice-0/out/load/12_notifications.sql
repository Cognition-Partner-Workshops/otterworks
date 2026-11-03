CREATE OR REPLACE TABLE ow_tp.mig_unt19_20261030_src.notifications
COMMENT 'frozen snapshot of OW_BILLING.NOTIFICATIONS exported 2026-10-31T22:31:25+00:00 (run unt19-20261030, slice-0 access)'
AS SELECT
  `id`,
  `tenant_id`,
  CAST(`kind_cd` AS BIGINT) AS `kind_cd`,
  CAST(`sent_at` AS TIMESTAMP_NTZ) AS `sent_at`
FROM read_files('/Volumes/ow_tp/mig_unt19_20261030_src/export/NOTIFICATIONS.csv', format => 'csv', header => true, multiLine => true,
  escape => '"', nullValue => '', inferSchema => false, mode => 'FAILFAST',
  schema => '`id` string, `tenant_id` string, `kind_cd` string, `sent_at` string');
