-- Run 20260927b, unit lakebase_scaffold: declared EARLIER shape used only as the
-- rerun-proof pre_shape (dbx-recon rerun-proof --prior-shape). Same columns and PKs as
-- 00_scaffold.sql, without uq_plans_code, uq_tenants_name, fk_usage_tenant, and with
-- codes.code_desc varchar(40). Never the shape the loader or recon runs against.

CREATE SCHEMA IF NOT EXISTS billing;

DROP TABLE IF EXISTS billing.usage_events;
DROP TABLE IF EXISTS billing.plans;
DROP TABLE IF EXISTS billing.tenants;
DROP TABLE IF EXISTS billing.codes;

CREATE TABLE billing.codes (
    code_type varchar(30) NOT NULL,
    code_val  bigint      NOT NULL,
    code_desc varchar(40) NOT NULL,
    CONSTRAINT pk_codes PRIMARY KEY (code_type, code_val)
);

CREATE TABLE billing.plans (
    id             varchar(36)   NOT NULL,
    code           varchar(50)   NOT NULL,
    tier_cd        bigint        NOT NULL,
    monthly_fee    numeric(12,2) NOT NULL,
    included_units bigint        NOT NULL,
    overage_rate   numeric(12,6) NOT NULL,
    active_yn      char(1)       NOT NULL,
    CONSTRAINT pk_plans PRIMARY KEY (id)
);

CREATE TABLE billing.tenants (
    id            varchar(36)  NOT NULL,
    name          varchar(200) NOT NULL,
    tax_exempt_yn char(1)      NOT NULL,
    status_cd     bigint       NOT NULL,
    CONSTRAINT pk_tenants PRIMARY KEY (id)
);

CREATE TABLE billing.usage_events (
    id          varchar(36)  NOT NULL,
    tenant_id   varchar(36)  NOT NULL,
    occurred_at timestamp(6) NOT NULL,
    units       bigint       NOT NULL,
    kind_cd     bigint       NOT NULL,
    CONSTRAINT pk_usage_events PRIMARY KEY (id)
);
