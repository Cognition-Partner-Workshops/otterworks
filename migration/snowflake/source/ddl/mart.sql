-- mart: what the reports, the admin dashboard, the analytics usage API and the
-- weekly capacity forecast read.
IF SCHEMA_ID('mart') IS NULL EXEC('CREATE SCHEMA mart');
GO

CREATE TABLE mart.mart_tenant_usage_daily (
    business_date         date           NOT NULL,
    tenant_id             varchar(36)    NOT NULL,
    tenant_name           nvarchar(200)  NOT NULL,
    plan_tier             varchar(20)    NULL,
    region_code           varchar(20)    NULL,
    api_units             int            NOT NULL,
    compute_units         int            NOT NULL,
    storage_peak_mb       int            NOT NULL,
    bytes_used            bigint         NOT NULL,
    active_users          int            NOT NULL,
    document_count        int            NOT NULL,
    file_count            int            NOT NULL,
    loaded_at             datetime2      NOT NULL
);

CREATE TABLE mart.mart_plan_seat_summary (
    business_date         date           NOT NULL,
    plan_tier             varchar(20)    NOT NULL,
    tenant_count          int            NOT NULL,
    seat_count            int            NOT NULL,
    seat_limit_total      int            NOT NULL,
    tenants_over_limit    int            NOT NULL,
    avg_seats_per_tenant  decimal(10, 2) NOT NULL,
    loaded_at             datetime2      NOT NULL
);

CREATE TABLE mart.mart_overage_charges (
    business_date         date           NOT NULL,
    tenant_id             varchar(36)    NOT NULL,
    tenant_name           nvarchar(200)  NOT NULL,
    plan_tier             varchar(20)    NULL,
    bytes_used            bigint         NOT NULL,
    included_bytes        bigint         NOT NULL,
    overage_gb            int            NOT NULL,
    overage_cents_per_gb  int            NOT NULL,
    overage_cents         int            NOT NULL,
    loaded_at             datetime2      NOT NULL
);

CREATE TABLE mart.mart_retention_summary (
    business_date         date           NOT NULL,
    tenant_id             varchar(36)    NULL,
    resource_type         varchar(20)    NOT NULL,
    retention_action      varchar(30)    NOT NULL,
    item_count            int            NOT NULL,
    loaded_at             datetime2      NOT NULL
);

CREATE TABLE mart.mart_audit_rollup (
    business_date         date           NOT NULL,
    tenant_id             varchar(36)    NULL,
    action                varchar(30)    NOT NULL,
    resource_type         varchar(30)    NOT NULL,
    event_count           int            NOT NULL,
    distinct_users        int            NOT NULL,
    first_event_utc       datetime2      NOT NULL,
    last_event_utc        datetime2      NOT NULL,
    loaded_at             datetime2      NOT NULL
);

CREATE TABLE mart.mart_capacity_forecast_input (
    business_date         date           NOT NULL,
    tenant_id             varchar(36)    NOT NULL,
    observation_date      date           NOT NULL,
    plan_tier             varchar(20)    NULL,
    peak_storage_mb       int            NOT NULL,
    bytes_used            bigint         NOT NULL,
    seat_count            int            NULL,
    forecast_bytes_30d    bigint         NULL,
    forecast_generated_at datetime2      NULL,
    loaded_at             datetime2      NOT NULL
);
GO
