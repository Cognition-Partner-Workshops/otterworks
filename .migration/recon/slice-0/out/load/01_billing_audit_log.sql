CREATE OR REPLACE TABLE ow_tp.mig_unt19_20261030_src.billing_audit_log
COMMENT 'frozen snapshot of OW_BILLING.BILLING_AUDIT_LOG exported 2026-10-31T22:31:25+00:00 (run unt19-20261030, slice-0 access)'
AS SELECT
  CAST(`log_id` AS BIGINT) AS `log_id`,
  CAST(`logged_at` AS TIMESTAMP_NTZ) AS `logged_at`,
  `module`,
  `message`
FROM read_files('/Volumes/ow_tp/mig_unt19_20261030_src/export/BILLING_AUDIT_LOG.csv', format => 'csv', header => true, multiLine => true,
  escape => '"', nullValue => '', inferSchema => false, mode => 'FAILFAST',
  schema => '`log_id` string, `logged_at` string, `module` string, `message` string');
