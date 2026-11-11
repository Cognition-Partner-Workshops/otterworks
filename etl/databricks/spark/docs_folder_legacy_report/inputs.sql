-- run_token=dbx-d1111 expires=2026-11-24
-- Input adapter: live cpw.dbx_d1111_before (Teradata-style names) -> Spark landing layout (etl/spark/jobs/py/common/schemas.py).
-- One SELECT per landing table, introduced by "-- landing: <area>/<TABLE>". Unmapped landing columns are NULL (no defensible live source).

-- landing: documents/FOLDER
-- PARENT_FOLDER_ID: NO live equivalent (not in documents__folder, documents__stg_folder, nor SFX_DOCUMENTS.FOLDER DDL).
-- It is an output column of the job, so it is the first failing input; it is left NULL and the job row stays RED.
SELECT folder_id AS FOLDER_ID, owner_user_id AS OWNER_USER_ID, CAST(NULL AS BIGINT) AS PARENT_FOLDER_ID, folder_name AS FOLDER_NAME
FROM cpw.dbx_d1111_before.documents__folder;

-- landing: documents/DOCUMENT
-- TITLE=document_name, STATUS=status_cd (warehouse/teradata/ddl/documents/00_tables.sql). CREATED_AT is TIMESTAMP in landing but live has DATE only: NULL (unused by job).
SELECT document_id AS DOCUMENT_ID, owner_user_id AS OWNER_USER_ID, folder_id AS FOLDER_ID, document_name AS TITLE,
       CAST(NULL AS TIMESTAMP) AS CREATED_AT, status_cd AS STATUS
FROM cpw.dbx_d1111_before.documents__document;
