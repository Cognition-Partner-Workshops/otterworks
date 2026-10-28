-- ow_tp_analytics_daily / ensure_objects
-- Idempotent DDL for the analytics_daily unit. Creates only objects inside the
-- isolated ow_tp.ow_tp_analytics namespace declared by the wave manifest;
-- never touches customer production catalogs.

CREATE SCHEMA IF NOT EXISTS ow_tp.ow_tp_analytics;

CREATE VOLUME IF NOT EXISTS ow_tp.ow_tp_analytics.analytics_drop;

-- Daily rollup: one row per report_date (the Postgres analytics_daily_summary
-- upsert target). Mirrors the staging shape in ow_tp_analytics_src.
CREATE TABLE IF NOT EXISTS ow_tp.ow_tp_analytics.analytics_daily_summary (
    report_date DATE,
    active_users INT,
    active_documents INT,
    active_files INT,
    total_events INT,
    documents_created INT,
    documents_edited INT,
    comments_added INT,
    files_uploaded INT,
    files_shared INT,
    files_deleted INT,
    bytes_uploaded BIGINT,
    updated_at TIMESTAMP,
    CONSTRAINT analytics_daily_summary_pk PRIMARY KEY (report_date)
)
USING DELTA;

-- Report landing: one row per report key (the S3
-- s3://otterworks-data-lake/reports/analytics/daily/<ds>/report.json artifact).
-- report_json keeps the serialized report verbatim; s3_key is the lineage key.
CREATE TABLE IF NOT EXISTS ow_tp.ow_tp_analytics.analytics_daily_report (
    s3_key STRING,
    report_type STRING,
    report_date DATE,
    generated_at TIMESTAMP,
    report_json STRING,
    CONSTRAINT analytics_daily_report_pk PRIMARY KEY (s3_key)
)
USING DELTA;
