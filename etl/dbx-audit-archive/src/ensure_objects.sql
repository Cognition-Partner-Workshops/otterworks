-- ow_tp_analytics_audit_archive / ensure_objects
-- Idempotent DDL for the analytics audit-archive unit. Creates only objects
-- inside the isolated ow_tp.ow_tp_analytics namespace declared by the wave
-- manifest; never touches customer production catalogs.

CREATE SCHEMA IF NOT EXISTS ow_tp.ow_tp_analytics;

-- Weekly audit-archive ledger, mirroring the archived event rows staged at
-- ow_tp.ow_tp_analytics_src.audit_events (the materialized output of the
-- legacy audit_archive_run routine: DynamoDB otterworks-audit-events older
-- than 90d swept to GLACIER jsonl). Columns stay nullable exactly as the
-- source stages them; Delta key constraints are informational (RELY), so the
-- load carries the ledgering, not a PK. archived_at / archive_s3_key are the
-- legacy quarantine evidence fields (when/where the row was archived).
CREATE TABLE IF NOT EXISTS ow_tp.ow_tp_analytics.audit_archive (
    event_id STRING,
    action STRING,
    actor STRING,
    resource STRING,
    tenant STRING,
    timestamp STRING,
    archived_at TIMESTAMP,
    archive_s3_key STRING
)
USING DELTA;

-- Compliance report metrics staged at
-- ow_tp.ow_tp_analytics_src.compliance_report (the legacy run's report.json
-- landed as rows; keyed by metric).
CREATE TABLE IF NOT EXISTS ow_tp.ow_tp_analytics.audit_archive_report (
    metric STRING,
    metric_value STRING,
    report_date DATE,
    generated_at TIMESTAMP
)
USING DELTA;
