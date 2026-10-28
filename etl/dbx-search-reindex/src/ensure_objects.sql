-- ow_tp_analytics_search_reindex / ensure_objects
-- Idempotent DDL for the search-reindex unit. Creates only objects inside
-- the isolated ow_tp.ow_tp_analytics namespace declared by the wave
-- manifest; never touches customer production catalogs.

CREATE SCHEMA IF NOT EXISTS ow_tp.ow_tp_analytics;

-- Rebuilt MeiliSearch document/file indexes, mirroring the legacy
-- search_reindex_weekly outputs staged at
-- ow_tp.ow_tp_analytics_src.search_index_documents /
-- ow_tp.ow_tp_analytics_src.search_index_files (keyed by index_name +
-- doc_id). Both source indexes land in one target table discriminated by
-- index_name, exactly as MeiliSearch carries them as separate indexes.
-- doc_sha256 fingerprints the indexed payload (sha2 of doc_json) so the
-- weekly run can detect drift without a payload compare. Columns stay
-- nullable exactly as the source stages them; Delta key constraints are
-- informational (RELY), so MERGE carries the keying, not a PK.
CREATE TABLE IF NOT EXISTS ow_tp.ow_tp_analytics.search_index_docs (
    index_name STRING,
    doc_id STRING,
    doc_sha256 STRING,
    doc_json STRING
)
USING DELTA;

-- Per-run reindex counts, mirroring the staged legacy report at
-- ow_tp.ow_tp_analytics_src.reindex_report (keyed by metric).
CREATE TABLE IF NOT EXISTS ow_tp.ow_tp_analytics.search_reindex_report (
    metric STRING,
    metric_value STRING,
    report_date DATE,
    generated_at TIMESTAMP
)
USING DELTA;
