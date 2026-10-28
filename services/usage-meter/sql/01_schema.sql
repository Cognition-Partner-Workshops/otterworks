-- Delta tables in ow_tp.ow_tp_usage_meter. The ow_tp_snap_* tables hold a SELECT-only copy
-- of the rating inputs read from Lakebase mig-invoicing-w1 / ow_tp_invoicing; ow_tp_usage_meter
-- is the meter, synced to Lakebase mig-usage-meter (databricks_postgres.ow_tp_usage_meter).
-- One SQL script so the whole file runs as a single warehouse statement.
BEGIN
    CREATE SCHEMA IF NOT EXISTS ow_tp.ow_tp_usage_meter;

    CREATE VOLUME IF NOT EXISTS ow_tp.ow_tp_usage_meter.ow_tp_snap_files;

    CREATE TABLE IF NOT EXISTS ow_tp.ow_tp_usage_meter.ow_tp_snap_plans (
        id STRING NOT NULL, code STRING NOT NULL, included_units BIGINT NOT NULL,
        overage_rate DECIMAL(12,6) NOT NULL);

    CREATE TABLE IF NOT EXISTS ow_tp.ow_tp_usage_meter.ow_tp_snap_tenants (
        id STRING NOT NULL, name STRING NOT NULL);

    CREATE TABLE IF NOT EXISTS ow_tp.ow_tp_usage_meter.ow_tp_snap_subscriptions (
        id STRING NOT NULL, tenant_id STRING NOT NULL, plan_id STRING NOT NULL,
        starts_on TIMESTAMP_NTZ NOT NULL, ends_on TIMESTAMP_NTZ, status_cd BIGINT NOT NULL,
        suspended_on TIMESTAMP_NTZ);

    CREATE TABLE IF NOT EXISTS ow_tp.ow_tp_usage_meter.ow_tp_snap_usage_events (
        id STRING NOT NULL, tenant_id STRING NOT NULL, occurred_at TIMESTAMP_NTZ NOT NULL,
        units BIGINT NOT NULL, kind_cd BIGINT NOT NULL);

    CREATE TABLE IF NOT EXISTS ow_tp.ow_tp_usage_meter.ow_tp_snap_rating_periods (
        id STRING NOT NULL, tenant_id STRING NOT NULL, period_start TIMESTAMP_NTZ NOT NULL,
        period_end TIMESTAMP_NTZ NOT NULL);

    CREATE TABLE IF NOT EXISTS ow_tp.ow_tp_usage_meter.ow_tp_snap_rating_results (
        id STRING NOT NULL, period_id STRING NOT NULL, rollover_units BIGINT NOT NULL);

    CREATE TABLE IF NOT EXISTS ow_tp.ow_tp_usage_meter.ow_tp_snap_log (
        snapshot_at TIMESTAMP NOT NULL, source_branch STRING NOT NULL,
        table_name STRING NOT NULL, row_count BIGINT NOT NULL);

    -- One row per tenant and rating period: the figures pkg_rating.fn_usage_rating returns.
    CREATE TABLE IF NOT EXISTS ow_tp.ow_tp_usage_meter.ow_tp_usage_meter (
        tenant_id         STRING NOT NULL,
        period_start      DATE   NOT NULL,
        period_end        DATE   NOT NULL,
        subscription_id   STRING,
        plan_id           STRING,
        plan_code         STRING,
        event_count       BIGINT NOT NULL,
        used_units        BIGINT NOT NULL,
        quota_units       BIGINT,
        rollover_units    BIGINT,
        billable_units    BIGINT,
        first_tier_units  BIGINT,
        second_tier_units BIGINT,
        overage_amount    DECIMAL(12,2),
        snapshot_at       TIMESTAMP,
        CONSTRAINT ow_tp_usage_meter_pk PRIMARY KEY (tenant_id, period_start));
END;
