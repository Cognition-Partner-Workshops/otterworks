/* run=dbx-d1111 act=spark step=run consumer=docs_share_activity */
-- run_token=dbx-d1111 expires=2026-11-24
-- Migrated from etl/spark/scala/src/main/scala/sfx/DocsShareActivity.scala. PERMISSION = rtrim(access_level) (Teradata CHAR(12) pad).
CREATE OR REPLACE TABLE cpw.dbx_d1111_after.documents__spark_docs_share_activity
COMMENT 'Migrated Spark job docs_share_activity. run_token=dbx-d1111 expires=2026-11-24'
TBLPROPERTIES ('run_token'='dbx-d1111','expires'='2026-11-24','act'='spark')
AS SELECT d.owner_user_id AS OWNER_USER_ID, rtrim(s.access_level) AS PERMISSION, COUNT(*) AS SHARES,
       COUNT(DISTINCT s.user_id) AS RECIPIENTS
FROM cpw.dbx_d1111_before.documents__doc_share s
JOIN cpw.dbx_d1111_before.documents__document d ON s.document_id = d.document_id
GROUP BY d.owner_user_id, rtrim(s.access_level)
