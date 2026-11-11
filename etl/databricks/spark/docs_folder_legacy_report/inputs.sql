-- run_token=dbx-d1111 expires=2026-11-24
-- Input adapter: live cpw.dbx_d1111_before (Teradata-style names) -> Spark landing layout (etl/spark/jobs/py/common/schemas.py).
-- One SELECT per landing table, introduced by "-- landing: <area>/<TABLE>". Unmapped landing columns are NULL (no defensible live source).

-- landing: documents/FOLDER
-- PARENT_FOLDER_ID: NO live equivalent (not in documents__folder, documents__stg_folder, nor SFX_DOCUMENTS.FOLDER DDL).
-- It is an output column of the job, so it is the first failing input; it is left NULL and the job row stays RED.
SELECT folder_id AS FOLDER_ID, owner_user_id AS OWNER_USER_ID, CAST(NULL AS BIGINT) AS PARENT_FOLDER_ID, folder_name AS FOLDER_NAME
FROM cpw.dbx_d1111_before.documents__folder;

-- landing: documents/DOCUMENT
-- Shared DOCUMENT mapping (same as ../docs_event_export_hourly/inputs.sql): TITLE=document_name,
-- CREATED_AT=CAST(created_dt AS TIMESTAMP) (DATE at midnight), STATUS=rtrim(status_cd) (CHAR(12) pad is not data).
-- CREATED_AT and STATUS are not read by this job.
SELECT document_id AS DOCUMENT_ID, owner_user_id AS OWNER_USER_ID, folder_id AS FOLDER_ID, document_name AS TITLE,
       CAST(created_dt AS TIMESTAMP) AS CREATED_AT, rtrim(status_cd) AS STATUS
FROM cpw.dbx_d1111_before.documents__document;
