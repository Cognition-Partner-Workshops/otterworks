/* run=dbx-d1111 act=spark step=run consumer=lake_compaction_documents */
-- run_token=dbx-d1111 expires=2026-11-24
-- Migrated from etl/spark/scala/src/main/scala/sfx/LakeCompactionDocuments.scala: read the export
-- (parquet with basePath, so EXPORT_BUCKET is the inferred INT partition column, last) and rewrite it
-- whole. coalesce(4) is dropped; Delta sizes the files.
CREATE OR REPLACE TABLE cpw.dbx_d1111_after.documents__spark_lake_compaction_documents
COMMENT 'run_token=dbx-d1111 expires=2026-11-24 act=spark source=etl/spark/scala/src/main/scala/sfx/LakeCompactionDocuments.scala'
TBLPROPERTIES ('run_token'='dbx-d1111','expires'='2026-11-24','act'='spark')
AS
SELECT DOCUMENT_ID, OWNER_USER_ID, FOLDER_ID, TITLE, CREATED_AT, STATUS,
       CAST(EXPORT_BUCKET AS INT) AS EXPORT_BUCKET
FROM cpw.dbx_d1111_after.documents__spark_docs_event_export_hourly
