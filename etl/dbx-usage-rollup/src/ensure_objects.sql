-- ow_tp_analytics_usage_rollup / ensure_objects
-- Idempotent DDL for the analytics usage-rollup unit. Creates only objects
-- inside the isolated ow_tp.ow_tp_analytics namespace declared by the wave
-- manifest; never touches customer production catalogs.

CREATE SCHEMA IF NOT EXISTS ow_tp.ow_tp_analytics;

-- Converted ROLLUP_INPUT: the legacy job read seed/usage-events.ndjson from
-- the filesystem/classpath; the converted input drop is this UC volume.
CREATE VOLUME IF NOT EXISTS ow_tp.ow_tp_analytics.rollup_input;

-- Per-day usage rollup, mirroring the legacy report rows staged at
-- ow_tp.ow_tp_analytics_src.usage_rollup_output (keyed by date). Columns stay
-- nullable exactly as the source stages them; Delta key constraints are
-- informational (RELY), so MERGE carries the keying, not a PK.
CREATE TABLE IF NOT EXISTS ow_tp.ow_tp_analytics.usage_rollup (
    date DATE,
    active_users INT,
    collab_sessions INT,
    documents_created INT,
    documents_edited INT,
    documents_viewed INT,
    files_downloaded INT,
    files_uploaded INT,
    net_storage_bytes BIGINT,
    storage_allocated_bytes BIGINT,
    storage_released_bytes BIGINT,
    total_events INT,
    generated_at TIMESTAMP,
    day_count INT
)
USING DELTA;
