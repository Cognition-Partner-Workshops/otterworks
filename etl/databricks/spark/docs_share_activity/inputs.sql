-- run_token=dbx-d1111 expires=2026-11-24
-- Input adapter: live cpw.dbx_d1111_before (Teradata-style names) -> Spark landing layout (etl/spark/jobs/py/common/schemas.py).
-- One SELECT per landing table, introduced by "-- landing: <area>/<TABLE>". Unmapped landing columns are NULL (no defensible live source).

-- landing: documents/DOC_SHARE
-- DOC_SHARE_ID=share_id, SHARED_WITH_USER_ID=user_id (the grantee; Teradata DOC_SHARE.USER_ID), PERMISSION=rtrim(access_level):
-- access_level is CHAR(12) in Teradata, so trailing pad blanks are not data. OWNER_USER_ID has no column on live doc_share,
-- shared mapping (same as ../doc_share_graph_reach/inputs.sql): documents__document.owner_user_id on DOCUMENT_ID (UNIQUE PRIMARY
-- INDEX, no fan-out), LEFT JOIN keeps unmatched shares. This job takes the owner from DOCUMENT, so its output is unaffected.
SELECT s.share_id AS DOC_SHARE_ID, s.document_id AS DOCUMENT_ID, d.owner_user_id AS OWNER_USER_ID,
       s.user_id AS SHARED_WITH_USER_ID, rtrim(s.access_level) AS PERMISSION
FROM cpw.dbx_d1111_before.documents__doc_share s
LEFT JOIN cpw.dbx_d1111_before.documents__document d ON s.document_id = d.document_id;

-- landing: documents/DOCUMENT
-- Shared DOCUMENT mapping (same as ../docs_event_export_hourly/inputs.sql): TITLE=document_name,
-- CREATED_AT=CAST(created_dt AS TIMESTAMP) (DATE at midnight), STATUS=rtrim(status_cd) (CHAR(12) pad is not data).
-- CREATED_AT and STATUS are not read by this job.
SELECT document_id AS DOCUMENT_ID, owner_user_id AS OWNER_USER_ID, folder_id AS FOLDER_ID, document_name AS TITLE,
       CAST(created_dt AS TIMESTAMP) AS CREATED_AT, rtrim(status_cd) AS STATUS
FROM cpw.dbx_d1111_before.documents__document;
