CREATE OR REPLACE TABLE ow_tp.mig_unt19_20261030_src.codes
COMMENT 'frozen snapshot of OW_BILLING.CODES exported 2026-10-31T22:31:25+00:00 (run unt19-20261030, slice-0 access)'
AS SELECT
  `code_type`,
  CAST(`code_val` AS BIGINT) AS `code_val`,
  `code_desc`
FROM read_files('/Volumes/ow_tp/mig_unt19_20261030_src/export/CODES.csv', format => 'csv', header => true, multiLine => true,
  escape => '"', nullValue => '', inferSchema => false, mode => 'FAILFAST',
  schema => '`code_type` string, `code_val` string, `code_desc` string');
