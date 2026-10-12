-- fact: daily grain facts, keyed by business_date. Every rollup deletes its
-- business_date before it inserts, so a rerun for the same date is safe.
IF SCHEMA_ID('fact') IS NULL EXEC('CREATE SCHEMA fact');
GO

CREATE TABLE fact.fact_storage_usage_daily (
    business_date         date           NOT NULL,
    tenant_id             varchar(36)    NOT NULL,
    plan_id               varchar(36)    NULL,
    sample_count          int            NOT NULL,
    peak_storage_mb       int            NOT NULL,
    bytes_used            bigint         NOT NULL,
    included_bytes        bigint         NULL,
    overage_gb            int            NULL,
    overage_cents         int            NULL,
    loaded_at             datetime2      NOT NULL
);

CREATE TABLE fact.fact_usage_events (
    business_date         date           NOT NULL,
    event_id              varchar(36)    NOT NULL,
    tenant_id             varchar(36)    NOT NULL,
    event_kind            varchar(20)    NOT NULL,
    units                 int            NOT NULL,
    event_ts_utc          datetime2      NOT NULL,
    loaded_at             datetime2      NOT NULL
);
CREATE INDEX ix_fact_usage_events_bd ON fact.fact_usage_events (business_date, tenant_id);

CREATE TABLE fact.fact_seat_assignments (
    business_date         date           NOT NULL,
    tenant_id             varchar(36)    NOT NULL,
    plan_id               varchar(36)    NULL,
    plan_tier             varchar(20)    NULL,
    seat_count            int            NOT NULL,
    seat_limit            int            NULL,
    over_limit            bit            NULL,
    loaded_at             datetime2      NOT NULL
);

CREATE TABLE fact.fact_collab_activity_daily (
    business_date         date           NOT NULL,
    tenant_id             varchar(36)    NOT NULL,
    document_id           varchar(36)    NOT NULL,
    comment_count         int            NOT NULL,
    session_count         int            NOT NULL,
    collaborator_count    int            NOT NULL,
    loaded_at             datetime2      NOT NULL
);

CREATE TABLE fact.fact_audit_events (
    business_date         date           NOT NULL,
    audit_id              varchar(64)    NOT NULL,
    tenant_id             varchar(36)    NULL,
    user_id               varchar(36)    NOT NULL,
    action                varchar(30)    NOT NULL,
    resource_type         varchar(30)    NOT NULL,
    resource_id           varchar(64)    NOT NULL,
    ip_address            varchar(45)    NULL,
    event_ts_utc          datetime2      NOT NULL,
    loaded_at             datetime2      NOT NULL
);

CREATE TABLE fact.fact_invoice_lines (
    business_date         date           NOT NULL,
    invoice_id            varchar(36)    NOT NULL,
    line_no               int            NOT NULL,
    tenant_id             varchar(36)    NOT NULL,
    period_start          date           NOT NULL,
    period_end            date           NOT NULL,
    line_type             varchar(20)    NOT NULL,
    description           nvarchar(400)  NOT NULL,
    amount_cents          int            NOT NULL,
    invoice_status        varchar(20)    NOT NULL,
    loaded_at             datetime2      NOT NULL
);

CREATE TABLE fact.fact_retention_actions (
    business_date         date           NOT NULL,
    tenant_id             varchar(36)    NULL,
    resource_type         varchar(20)    NOT NULL,
    resource_id           varchar(36)    NOT NULL,
    retention_action      varchar(30)    NOT NULL,
    days_since_update     int            NOT NULL,
    loaded_at             datetime2      NOT NULL
);

CREATE TABLE fact.fact_document_status_daily (
    business_date         date           NOT NULL,
    tenant_id             varchar(36)    NULL,
    workspace_id          varchar(36)    NOT NULL,
    status_label          varchar(20)    NOT NULL,
    document_count        int            NOT NULL,
    word_count            bigint         NOT NULL,
    loaded_at             datetime2      NOT NULL
);
GO
