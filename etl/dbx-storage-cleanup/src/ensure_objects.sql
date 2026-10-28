-- ow_tp_analytics_storage_cleanup / ensure_objects
-- Idempotent DDL for the storage_cleanup_daily unit. Creates only objects
-- inside the isolated ow_tp.ow_tp_analytics namespace declared by the wave
-- manifest; never touches customer production catalogs.

CREATE SCHEMA IF NOT EXISTS ow_tp.ow_tp_analytics;

-- Converted input drop: the legacy script listed s3://otterworks-file-storage
-- prefix files/ and scanned DynamoDB otterworks-file-metadata; the converted
-- inputs land here as files_listing_<ds>.jsonl + metadata_keys_<ds>.jsonl.
CREATE VOLUME IF NOT EXISTS ow_tp.ow_tp_analytics.storage_drop;

-- Quarantine action ledger: one row per orphaned object (the legacy script's
-- copy_object to otterworks-file-quarantine + delete_object pair, kept as an
-- auditable action record; source objects are never deleted here). Mirrors
-- the staging shape in ow_tp.ow_tp_analytics_src.orphan_files.
CREATE TABLE IF NOT EXISTS ow_tp.ow_tp_analytics.storage_quarantine_actions (
    s3_key STRING,
    size_bytes BIGINT,
    quarantine_key STRING,
    quarantined_at DATE
)
USING DELTA;

-- Daily savings report: one row per metric (the legacy report.json flattened,
-- matching ow_tp.ow_tp_analytics_src.cleanup_report).
CREATE TABLE IF NOT EXISTS ow_tp.ow_tp_analytics.storage_cleanup_report (
    metric STRING,
    metric_value STRING,
    report_date DATE,
    generated_at TIMESTAMP
)
USING DELTA;
