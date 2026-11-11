-- run_token=dbx-d1111 expires=2026-11-24
-- Landing documents/DOC_SHARE (DOC_SHARE_ID, DOCUMENT_ID, OWNER_USER_ID, SHARED_WITH_USER_ID, PERMISSION).
-- Live documents__doc_share has no owner column (first failing result). OWNER_USER_ID is resolved through
-- documents__document.owner_user_id on DOCUMENT_ID, the UNIQUE PRIMARY INDEX of SFX_DOCUMENTS.DOCUMENT
-- (warehouse/teradata/ddl/documents/00_tables.sql), so the lookup cannot fan out; LEFT JOIN keeps unmatched shares (owner NULL).
-- SHARED_WITH_USER_ID <- user_id (the grantee), PERMISSION <- access_level (CHAR(12), trailing pad trimmed).
SELECT s.share_id            AS DOC_SHARE_ID,
       s.document_id         AS DOCUMENT_ID,
       d.owner_user_id       AS OWNER_USER_ID,
       s.user_id             AS SHARED_WITH_USER_ID,
       rtrim(s.access_level) AS PERMISSION
FROM cpw.dbx_d1111_before.documents__doc_share s
LEFT JOIN cpw.dbx_d1111_before.documents__document d ON s.document_id = d.document_id
