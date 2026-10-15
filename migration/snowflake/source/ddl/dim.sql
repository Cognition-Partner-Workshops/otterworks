-- dim: conformed dimensions, rebuilt by the usp_load_dim_* procedures.
-- dim_region is reference data the team maintains by hand in this script.
IF SCHEMA_ID('dim') IS NULL EXEC('CREATE SCHEMA dim');
GO

CREATE TABLE dim.dim_date (
    date_key        int            NOT NULL PRIMARY KEY,
    calendar_date   date           NOT NULL,
    year_number     smallint       NOT NULL,
    month_number    tinyint        NOT NULL,
    day_number      tinyint        NOT NULL,
    day_of_week     tinyint        NOT NULL,
    day_name        varchar(10)    NOT NULL,
    month_name      varchar(10)    NOT NULL,
    is_weekend      bit            NOT NULL,
    is_month_end    bit            NOT NULL,
    fiscal_quarter  varchar(7)     NOT NULL,
    loaded_at       datetime2      NOT NULL
);

CREATE TABLE dim.dim_region (
    region_key      int            NOT NULL PRIMARY KEY,
    region_code     varchar(20)    NOT NULL,
    region_name     nvarchar(100)  NOT NULL,
    data_residency  varchar(10)    NOT NULL,
    loaded_at       datetime2      NOT NULL
);

CREATE TABLE dim.dim_plan (
    plan_key              int IDENTITY(1, 1) PRIMARY KEY,
    plan_id               varchar(36)    NOT NULL,
    plan_code             varchar(40)    NOT NULL,
    plan_tier             varchar(20)    NOT NULL,
    monthly_fee_cents     int            NOT NULL,
    included_units        int            NOT NULL,
    included_bytes        bigint         NOT NULL,
    overage_cents_per_gb  int            NOT NULL,
    seat_limit            int            NOT NULL,
    is_active             bit            NOT NULL,
    loaded_at             datetime2      NOT NULL
);

CREATE TABLE dim.dim_tenant (
    tenant_key      int IDENTITY(1, 1) PRIMARY KEY,
    tenant_id       varchar(36)    NOT NULL,
    tenant_name     nvarchar(200)  NOT NULL,
    status          varchar(20)    NOT NULL,
    tax_exempt      bit            NOT NULL,
    region_code     varchar(20)    NULL,
    plan_id         varchar(36)    NULL,
    plan_tier       varchar(20)    NULL,
    subscription_status varchar(20) NULL,
    loaded_at       datetime2      NOT NULL
);

CREATE TABLE dim.dim_user (
    user_key        int IDENTITY(1, 1) PRIMARY KEY,
    user_id         varchar(36)    NOT NULL,
    tenant_id       varchar(36)    NULL,
    email           nvarchar(255)  NOT NULL,
    email_domain    nvarchar(255)  NULL,
    display_name    nvarchar(100)  NOT NULL,
    email_verified  bit            NOT NULL,
    mfa_enabled     bit            NOT NULL,
    created_at_utc  datetime2      NOT NULL,
    last_login_utc  datetime2      NULL,
    loaded_at       datetime2      NOT NULL
);
CREATE INDEX ix_dim_user_user ON dim.dim_user (user_id);

CREATE TABLE dim.dim_workspace (
    workspace_key   int IDENTITY(1, 1) PRIMARY KEY,
    workspace_id    varchar(36)    NOT NULL,
    workspace_name  nvarchar(200)  NOT NULL,
    tenant_id       varchar(36)    NOT NULL,
    member_count    int            NOT NULL,
    loaded_at       datetime2      NOT NULL
);

CREATE TABLE dim.dim_document (
    document_key    int IDENTITY(1, 1) PRIMARY KEY,
    document_id     varchar(36)    NOT NULL,
    tenant_id       varchar(36)    NULL,
    workspace_id    varchar(36)    NOT NULL,
    owner_id        varchar(36)    NOT NULL,
    title           nvarchar(500)  NOT NULL,
    content_type    varchar(50)    NOT NULL,
    is_deleted      bit            NOT NULL,
    is_template     bit            NOT NULL,
    archived        bit            NULL,
    word_count      int            NOT NULL,
    version_count   int            NOT NULL,
    created_at_utc  datetime2      NOT NULL,
    updated_at_utc  datetime2      NOT NULL,
    loaded_at       datetime2      NOT NULL
);
CREATE INDEX ix_dim_document_doc ON dim.dim_document (document_id);

CREATE TABLE dim.dim_file (
    file_key        int IDENTITY(1, 1) PRIMARY KEY,
    file_id         varchar(36)    NOT NULL,
    tenant_id       varchar(36)    NULL,
    workspace_id    varchar(36)    NOT NULL,
    owner_id        varchar(36)    NOT NULL,
    file_name       nvarchar(500)  NOT NULL,
    mime_type       varchar(100)   NOT NULL,
    size_bytes      bigint         NOT NULL,
    size_mb         decimal(18, 3) NULL,
    is_trashed      bit            NOT NULL,
    archived        bit            NULL,
    version_count   int            NOT NULL,
    created_at_utc  datetime2      NOT NULL,
    updated_at_utc  datetime2      NOT NULL,
    loaded_at       datetime2      NOT NULL
);
GO

INSERT INTO dim.dim_region (region_key, region_code, region_name, data_residency, loaded_at) VALUES
(1, 'us-east-1', N'US East (N. Virginia)', 'US', GETDATE()),
(2, 'us-west-2', N'US West (Oregon)', 'US', GETDATE()),
(3, 'eu-west-1', N'EU (Ireland)', 'EU', GETDATE()),
(4, 'eu-central-1', N'EU (Frankfurt)', 'EU', GETDATE()),
(5, 'ap-southeast-2', N'Asia Pacific (Sydney)', 'APAC', GETDATE());
GO
