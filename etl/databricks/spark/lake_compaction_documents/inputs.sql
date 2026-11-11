/* run=dbx-d1111 act=spark step=inputs consumer=lake_compaction_documents */
-- run_token=dbx-d1111 expires=2026-11-24
-- lake_compaction_documents reads no landing table: its only input is the output of
-- docs_event_export_hourly (lake/documents/docs_event_export_hourly), which on Databricks is
-- cpw.dbx_d1111_after.documents__spark_docs_event_export_hourly. The upstream landing input is
-- documents/DOCUMENT, adapted in ../docs_event_export_hourly/inputs.sql.
SELECT DOCUMENT_ID, OWNER_USER_ID, FOLDER_ID, TITLE, CREATED_AT, STATUS, EXPORT_BUCKET
FROM cpw.dbx_d1111_after.documents__spark_docs_event_export_hourly;
