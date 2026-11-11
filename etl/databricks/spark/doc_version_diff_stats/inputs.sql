/* run=dbx-d1111 act=spark step=inputs consumer=doc_version_diff_stats */
-- run_token=dbx-d1111 expires=2026-11-24
-- BODY intentionally unresolved: a hash is not document text.
SELECT version_id AS DOC_VERSION_ID, document_id AS DOCUMENT_ID,
       CAST(version_no AS BIGINT) AS VERSION_NUMBER, body AS BODY,
       version_ts AS CREATED_AT
FROM cpw.dbx_d1111_before.documents__doc_version;
