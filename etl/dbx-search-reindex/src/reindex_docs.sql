-- ow_tp_analytics_search_reindex / reindex_docs
-- Converted search_reindex_weekly.py index rebuild.
--
-- The legacy job paged document-service /api/v1/documents and file-service
-- /api/v1/files, deleted and recreated the MeiliSearch `documents` and
-- `files` indexes, and bulk-indexed every document. The converted input is
-- the staged index state the source read once and mirrored into
-- ow_tp.ow_tp_analytics_src (search_index_documents + search_index_files);
-- both land in search_index_docs discriminated by index_name, keyed
-- (index_name, doc_id).
--
-- Idempotent snapshot load: MERGE on (index_name, doc_id), and keys absent
-- from the current index drop out — the legacy job rebuilt both indexes
-- from scratch each run, so the target reflects the current snapshot, not
-- an accumulation.

MERGE INTO ow_tp.ow_tp_analytics.search_index_docs AS tgt
USING (
    SELECT
        index_name,
        doc_id,
        sha2(doc_json, 256) AS doc_sha256,
        doc_json
    FROM ow_tp.ow_tp_analytics_src.search_index_documents
    UNION ALL
    SELECT
        index_name,
        doc_id,
        sha2(doc_json, 256) AS doc_sha256,
        doc_json
    FROM ow_tp.ow_tp_analytics_src.search_index_files
) AS src
ON tgt.index_name = src.index_name AND tgt.doc_id = src.doc_id
WHEN MATCHED THEN UPDATE SET
    doc_sha256 = src.doc_sha256,
    doc_json = src.doc_json
WHEN NOT MATCHED THEN INSERT *
WHEN NOT MATCHED BY SOURCE THEN DELETE;
