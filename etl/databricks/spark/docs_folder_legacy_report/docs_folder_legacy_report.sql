/* run=dbx-d1111 act=spark step=run consumer=docs_folder_legacy_report */
-- run_token=dbx-d1111 expires=2026-11-24
-- Migrated from etl/spark/jobs/py/docs_folder_legacy_report.py. LEFT JOIN keeps empty folders (DOCUMENTS=0).
-- PARENT_FOLDER_ID has no live source (see inputs.sql) and is NULL: this job stays RED.
CREATE OR REPLACE TABLE cpw.dbx_d1111_after.documents__spark_docs_folder_legacy_report
COMMENT 'Migrated Spark job docs_folder_legacy_report (retire candidate). run_token=dbx-d1111 expires=2026-11-24'
TBLPROPERTIES ('run_token'='dbx-d1111','expires'='2026-11-24','act'='spark')
AS SELECT f.folder_id AS FOLDER_ID, f.folder_name AS FOLDER_NAME, CAST(NULL AS BIGINT) AS PARENT_FOLDER_ID,
       COUNT(d.document_id) AS DOCUMENTS
FROM cpw.dbx_d1111_before.documents__folder f
LEFT JOIN cpw.dbx_d1111_before.documents__document d ON f.folder_id = d.folder_id
GROUP BY f.folder_id, f.folder_name
