/* run=dbx-d1111 act=spark step=inputs consumer=docs_event_export_hourly */
-- run_token=dbx-d1111 expires=2026-11-24
-- Input adapter for docs_event_export_hourly: landing table documents/DOCUMENT
-- (etl/spark/jobs/py/common/schemas.py) from the live baseline
-- cpw.dbx_d1111_before.documents__document (warehouse/teradata/ddl/documents/00_tables.sql).
--   DOCUMENT_ID   <- document_id
--   OWNER_USER_ID <- owner_user_id
--   FOLDER_ID     <- folder_id
--   TITLE         <- document_name
--   CREATED_AT    <- created_dt (DATE, cast to TIMESTAMP at midnight UTC)
--   STATUS        <- status_cd (CHAR(12); trailing pad removed, as a CHAR export to TEXT does)
-- customer_id and file_type have no landing column and are not read.
SELECT document_id                  AS DOCUMENT_ID,
       owner_user_id                AS OWNER_USER_ID,
       folder_id                    AS FOLDER_ID,
       document_name                AS TITLE,
       CAST(created_dt AS TIMESTAMP) AS CREATED_AT,
       rtrim(status_cd)             AS STATUS
FROM cpw.dbx_d1111_before.documents__document;
