/* run=dbx-d1111 act=spark step=inputs consumer=docs_storage_by_owner */
-- run_token=dbx-d1111 expires=2026-11-24
-- Input adapter: live cpw.dbx_d1111_before (Teradata-style names) -> Spark landing layout (etl/spark/jobs/py/common/schemas.py).
-- One SELECT per landing table, introduced by "-- landing: <area>/<TABLE>". Unmapped landing columns are NULL (no defensible live source).

-- landing: documents/DOCUMENT
-- Shared DOCUMENT mapping (same as ../docs_event_export_hourly/inputs.sql): TITLE=document_name,
-- CREATED_AT=CAST(created_dt AS TIMESTAMP) (DATE at midnight), STATUS=rtrim(status_cd) (CHAR(12) pad is not data).
-- CREATED_AT and STATUS are not read by this job.
SELECT document_id AS DOCUMENT_ID, owner_user_id AS OWNER_USER_ID, folder_id AS FOLDER_ID, document_name AS TITLE,
       CAST(created_dt AS TIMESTAMP) AS CREATED_AT, rtrim(status_cd) AS STATUS
FROM cpw.dbx_d1111_before.documents__document;

/* run=dbx-d1111 act=spark step=inputs consumer=docs_storage_by_owner */
-- landing: documents/FILE_OBJECT
-- SIZE_BYTES=bytes_used, STORAGE_KEY=object_key. CHECKSUM has no live column: NULL (unused by job).
SELECT file_object_id AS FILE_OBJECT_ID, document_id AS DOCUMENT_ID, bytes_used AS SIZE_BYTES,
       CAST(NULL AS STRING) AS CHECKSUM, object_key AS STORAGE_KEY
FROM cpw.dbx_d1111_before.documents__file_object;

/* run=dbx-d1111 act=spark step=inputs consumer=docs_storage_by_owner */
-- landing: users/APP_USER
-- STATUS=rtrim(status_cd) (CHAR(12) pad). CREATED_AT is TIMESTAMP in landing but live has DATE only: NULL. Neither is read by the job.
SELECT user_id AS USER_ID, email AS EMAIL, display_name AS DISPLAY_NAME, CAST(NULL AS TIMESTAMP) AS CREATED_AT, rtrim(status_cd) AS STATUS
FROM cpw.dbx_d1111_before.users__app_user;
