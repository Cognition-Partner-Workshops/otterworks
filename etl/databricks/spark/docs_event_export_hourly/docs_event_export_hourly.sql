/* run=dbx-d1111 act=spark step=run consumer=docs_event_export_hourly */
-- run_token=dbx-d1111 expires=2026-11-24
-- Migrated from etl/spark/jobs/py/docs_event_export_hourly.py: the DOCUMENT landing rows plus
-- EXPORT_BUCKET = pmod(DOCUMENT_ID, 10000), written as one Delta table that is fully replaced on
-- every run (the source overwrote the whole export directory). The 10,000 bucket directories are
-- not reproduced: EXPORT_BUCKET stays a column and file sizing is left to Delta.
CREATE OR REPLACE TABLE cpw.dbx_d1111_after.documents__spark_docs_event_export_hourly
COMMENT 'run_token=dbx-d1111 expires=2026-11-24 act=spark source=etl/spark/jobs/py/docs_event_export_hourly.py'
TBLPROPERTIES ('run_token'='dbx-d1111','expires'='2026-11-24','act'='spark')
AS
WITH document AS (
  SELECT document_id                   AS DOCUMENT_ID,
         owner_user_id                 AS OWNER_USER_ID,
         folder_id                     AS FOLDER_ID,
         document_name                 AS TITLE,
         CAST(created_dt AS TIMESTAMP) AS CREATED_AT,
         rtrim(status_cd)              AS STATUS
  FROM cpw.dbx_d1111_before.documents__document
)
SELECT DOCUMENT_ID, OWNER_USER_ID, FOLDER_ID, TITLE, CREATED_AT, STATUS,
       pmod(DOCUMENT_ID, DOCUMENT_ID * 0 + 10000) AS EXPORT_BUCKET
FROM document
