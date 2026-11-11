/* run=dbx-d1111 act=spark step=parity consumer=doc_version_diff_stats */
-- run_token=dbx-d1111 expires=2026-11-24
-- Intentionally fails: CONTENT_HASH is not a defensible substitute for BODY.
SELECT version_id, document_id, version_no, body, version_ts
FROM cpw.dbx_d1111_before.documents__doc_version;

/* run=dbx-d1111 act=spark step=inputs consumer=doc_version_diff_stats */
DESCRIBE TABLE cpw.dbx_d1111_before.documents__stg_doc_version;
