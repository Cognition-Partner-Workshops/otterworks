CREATE OR REPLACE TABLE ow_tp.mig_unt19_20261030_src.entity_attr_value
COMMENT 'frozen snapshot of OW_BILLING.ENTITY_ATTR_VALUE exported 2026-10-31T22:31:25+00:00 (run unt19-20261030, slice-0 access)'
AS SELECT
  CAST(`eav_id` AS BIGINT) AS `eav_id`,
  `entity_type`,
  `entity_id`,
  `attr_name`,
  `attr_value`,
  `attr_type`,
  `created_dt`
FROM read_files('/Volumes/ow_tp/mig_unt19_20261030_src/export/ENTITY_ATTR_VALUE.csv', format => 'csv', header => true, multiLine => true,
  escape => '"', nullValue => '', inferSchema => false, mode => 'FAILFAST',
  schema => '`eav_id` string, `entity_type` string, `entity_id` string, `attr_name` string, `attr_value` string, `attr_type` string, `created_dt` string');
