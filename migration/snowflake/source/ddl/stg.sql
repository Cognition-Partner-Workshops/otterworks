-- stg: landing tables. Each one is filled by exactly one SSIS package and
-- truncated by that package before it loads (stg_billing_usage_events is the
-- exception: it loads incrementally from the watermark).
IF SCHEMA_ID('stg') IS NULL EXEC('CREATE SCHEMA stg');
GO

CREATE TABLE stg.stg_billing_tenants (
    id              varchar(36)    NOT NULL,
    name            nvarchar(200)  NOT NULL,
    tax_exempt      bit            NOT NULL,
    status          varchar(20)    NOT NULL,
    region_code     varchar(20)    NULL,
    extracted_at    datetime2      NOT NULL,
    source_system   nvarchar(40)   NOT NULL
);

CREATE TABLE stg.stg_billing_plans (
    id                    varchar(36)    NOT NULL,
    code                  varchar(40)    NOT NULL,
    tier                  varchar(20)    NOT NULL,
    monthly_fee           decimal(12, 2) NOT NULL,
    included_units        int            NOT NULL,
    overage_rate          decimal(12, 6) NOT NULL,
    active                bit            NOT NULL,
    included_bytes        bigint         NULL,
    overage_cents_per_gb  int            NULL,
    extracted_at          datetime2      NOT NULL,
    source_system         nvarchar(40)   NOT NULL
);

CREATE TABLE stg.stg_billing_subscriptions (
    id              varchar(36)    NOT NULL,
    tenant_id       varchar(36)    NOT NULL,
    plan_id         varchar(36)    NOT NULL,
    starts_on       date           NOT NULL,
    ends_on         date           NULL,
    status          varchar(20)    NOT NULL,
    suspended_on    date           NULL,
    extracted_at    datetime2      NOT NULL,
    source_system   nvarchar(40)   NOT NULL
);

CREATE TABLE stg.stg_billing_usage_events (
    id              varchar(36)    NOT NULL,
    tenant_id       varchar(36)    NOT NULL,
    occurred_at     datetime2      NOT NULL,
    units           int            NOT NULL,
    kind            varchar(20)    NOT NULL,
    event_ts_utc    datetime2      NOT NULL,
    extracted_at    datetime2      NOT NULL,
    source_system   nvarchar(40)   NOT NULL
);
CREATE INDEX ix_stg_billing_usage_events_ts ON stg.stg_billing_usage_events (event_ts_utc, kind);

CREATE TABLE stg.stg_billing_invoices (
    invoice_id      varchar(36)    NOT NULL,
    tenant_id       varchar(36)    NOT NULL,
    period_start    date           NOT NULL,
    period_end      date           NOT NULL,
    issued_at       datetime2      NOT NULL,
    subtotal        decimal(12, 2) NOT NULL,
    tax             decimal(12, 2) NOT NULL,
    total           decimal(12, 2) NOT NULL,
    status          varchar(20)    NOT NULL,
    line_id         varchar(36)    NOT NULL,
    line_no         int            NOT NULL,
    line_type       varchar(20)    NOT NULL,
    description     nvarchar(400)  NOT NULL,
    amount          decimal(12, 2) NOT NULL,
    extracted_at    datetime2      NOT NULL,
    source_system   nvarchar(40)   NOT NULL
);

CREATE TABLE stg.stg_auth_users (
    id              varchar(36)    NOT NULL,
    email           nvarchar(255)  NOT NULL,
    display_name    nvarchar(100)  NOT NULL,
    email_verified  bit            NOT NULL,
    mfa_enabled     bit            NOT NULL,
    created_at      datetime2      NOT NULL,
    updated_at      datetime2      NOT NULL,
    last_login_at   datetime2      NULL,
    email_domain    nvarchar(255)  NULL,
    extracted_at    datetime2      NOT NULL,
    source_system   nvarchar(40)   NOT NULL
);

CREATE TABLE stg.stg_auth_workspace_members (
    user_id         varchar(36)    NOT NULL,
    workspace_id    varchar(36)    NOT NULL,
    workspace_name  nvarchar(200)  NOT NULL,
    tenant_id       varchar(36)    NOT NULL,
    role            varchar(50)    NOT NULL,
    joined_at       datetime2      NOT NULL,
    extracted_at    datetime2      NOT NULL,
    source_system   nvarchar(40)   NOT NULL
);
CREATE INDEX ix_stg_auth_workspace_members_user ON stg.stg_auth_workspace_members (user_id);

CREATE TABLE stg.stg_documents (
    id              varchar(36)    NOT NULL,
    title           nvarchar(500)  NOT NULL,
    content_type    varchar(50)    NOT NULL,
    owner_id        varchar(36)    NOT NULL,
    folder_id       varchar(36)    NULL,
    workspace_id    varchar(36)    NOT NULL,
    is_deleted      bit            NOT NULL,
    is_template     bit            NOT NULL,
    archived        bit            NULL,
    word_count      int            NOT NULL,
    version         int            NOT NULL,
    created_at      datetime2      NOT NULL,
    updated_at      datetime2      NOT NULL,
    tenant_id       varchar(36)    NULL,
    extracted_at    datetime2      NOT NULL,
    source_system   nvarchar(40)   NOT NULL
);

CREATE TABLE stg.stg_document_versions (
    id              varchar(36)    NOT NULL,
    document_id     varchar(36)    NOT NULL,
    version_number  int            NOT NULL,
    title           nvarchar(500)  NOT NULL,
    created_by      varchar(36)    NOT NULL,
    created_at      datetime2      NOT NULL,
    content_length  int            NULL,
    extracted_at    datetime2      NOT NULL,
    source_system   nvarchar(40)   NOT NULL
);

CREATE TABLE stg.stg_files (
    id              varchar(36)    NOT NULL,
    name            nvarchar(500)  NOT NULL,
    mime_type       varchar(100)   NOT NULL,
    size_bytes      bigint         NOT NULL,
    folder_id       varchar(36)    NULL,
    owner_id        varchar(36)    NOT NULL,
    workspace_id    varchar(36)    NOT NULL,
    version         int            NOT NULL,
    is_trashed      bit            NOT NULL,
    archived        bit            NULL,
    created_at      datetime2      NOT NULL,
    updated_at      datetime2      NOT NULL,
    size_mb         decimal(18, 3) NULL,
    tenant_id       varchar(36)    NULL,
    extracted_at    datetime2      NOT NULL,
    source_system   nvarchar(40)   NOT NULL
);

CREATE TABLE stg.stg_file_versions (
    file_id         varchar(36)    NOT NULL,
    version         int            NOT NULL,
    size_bytes      bigint         NOT NULL,
    created_by      varchar(36)    NOT NULL,
    created_at      datetime2      NOT NULL,
    extracted_at    datetime2      NOT NULL,
    source_system   nvarchar(40)   NOT NULL
);

CREATE TABLE stg.stg_collab_events (
    id              varchar(36)    NOT NULL,
    event_type      varchar(30)    NOT NULL,
    document_id     varchar(36)    NOT NULL,
    user_id         varchar(36)    NOT NULL,
    session_id      varchar(36)    NULL,
    created_at      datetime2      NOT NULL,
    tenant_id       varchar(36)    NULL,
    extracted_at    datetime2      NOT NULL,
    source_system   nvarchar(40)   NOT NULL
);

CREATE TABLE stg.stg_audit_events (
    id              varchar(64)    NOT NULL,
    user_id         varchar(36)    NOT NULL,
    action          varchar(30)    NOT NULL,
    resource_type   varchar(30)    NOT NULL,
    resource_id     varchar(64)    NOT NULL,
    details         nvarchar(2000) NULL,
    ip_address      varchar(45)    NULL,
    user_agent      nvarchar(400)  NULL,
    [timestamp]     datetime2      NOT NULL,
    tenant_id       varchar(36)    NULL,
    extracted_at    datetime2      NOT NULL,
    source_system   nvarchar(40)   NOT NULL
);

CREATE TABLE stg.stg_analytics_events (
    event_id        varchar(64)    NOT NULL,
    event_type      varchar(64)    NOT NULL,
    user_id         varchar(128)   NOT NULL,
    resource_id     varchar(128)   NOT NULL,
    resource_type   varchar(64)    NOT NULL,
    metadata        nvarchar(2000) NOT NULL,
    occurred_at     bigint         NOT NULL,
    event_ts_utc    datetime2      NOT NULL,
    row_checksum    varchar(64)    NULL,
    tenant_id       varchar(36)    NULL,
    extracted_at    datetime2      NOT NULL,
    source_system   nvarchar(40)   NOT NULL
);
GO
