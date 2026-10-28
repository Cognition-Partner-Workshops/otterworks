-- ow_tp_analytics_user_activity / ensure_objects
-- Idempotent DDL for the user_activity_daily unit. Creates only objects
-- inside the isolated ow_tp.ow_tp_analytics namespace declared by the wave
-- manifest; never touches customer production catalogs.

CREATE SCHEMA IF NOT EXISTS ow_tp.ow_tp_analytics;

-- Flattened user-activity report: one row per (report_date, user_id, metric),
-- mirroring the staged shape at ow_tp.ow_tp_analytics_src.user_activity_report.
-- metric_value stays STRING exactly as staged; Delta key constraints are
-- informational (RELY), so MERGE carries the keying, not a PK.
CREATE TABLE IF NOT EXISTS ow_tp.ow_tp_analytics.user_activity_report (
    report_date DATE,
    user_id STRING,
    metric STRING,
    metric_value STRING,
    generated_at TIMESTAMP
)
USING DELTA;
