/* run=dbx-d1111 act=spark step=run consumer=docs_storage_by_owner */
-- run_token=dbx-d1111 expires=2026-11-24
-- Migrated from etl/spark/jobs/py/docs_storage_by_owner.py. Inner joins and COUNT(*) per (USER_ID, EMAIL) as in the source.
CREATE OR REPLACE TABLE cpw.dbx_d1111_after.documents__spark_docs_storage_by_owner
COMMENT 'Migrated Spark job docs_storage_by_owner. run_token=dbx-d1111 expires=2026-11-24'
TBLPROPERTIES ('run_token'='dbx-d1111','expires'='2026-11-24','act'='spark')
AS SELECT u.user_id AS USER_ID, u.email AS EMAIL, COUNT(*) AS FILE_COUNT, SUM(f.bytes_used) AS SIZE_BYTES
FROM cpw.dbx_d1111_before.documents__document d
JOIN cpw.dbx_d1111_before.documents__file_object f ON d.document_id = f.document_id
JOIN cpw.dbx_d1111_before.users__app_user u ON d.owner_user_id = u.user_id
GROUP BY u.user_id, u.email
