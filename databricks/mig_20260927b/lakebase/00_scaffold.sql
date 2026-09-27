-- Run 20260927b, unit lakebase_scaffold (wave 0).
-- Lakebase project ow-tp-billing, database ow_tp, branch mig-20260927b-w0, schema billing.
-- Types per .migration/units/lakebase_scaffold/mapping_spec.json; keys per
-- .migration/inventory/oracle_dictionary_20260927b.json (OW_BILLING).
-- Owns exactly: billing.codes, billing.plans, billing.tenants, billing.usage_events.

CREATE SCHEMA IF NOT EXISTS billing;

DROP TABLE IF EXISTS billing.usage_events;
DROP TABLE IF EXISTS billing.plans;
DROP TABLE IF EXISTS billing.tenants;
DROP TABLE IF EXISTS billing.codes;

CREATE TABLE billing.codes (
    code_type varchar(30) NOT NULL,
    code_val  bigint      NOT NULL,
    code_desc varchar(80) NOT NULL,
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
    CONSTRAINT pk_plans PRIMARY KEY (id),
    CONSTRAINT uq_plans_code UNIQUE (code)
);

CREATE TABLE billing.tenants (
    id            varchar(36)  NOT NULL,
    name          varchar(200) NOT NULL,
    tax_exempt_yn char(1)      NOT NULL,
    status_cd     bigint       NOT NULL,
    CONSTRAINT pk_tenants PRIMARY KEY (id),
    CONSTRAINT uq_tenants_name UNIQUE (name)
);

CREATE TABLE billing.usage_events (
    id          varchar(36)  NOT NULL,
    tenant_id   varchar(36)  NOT NULL,
    occurred_at timestamp(6) NOT NULL,
    units       bigint       NOT NULL,
    kind_cd     bigint       NOT NULL,
    CONSTRAINT pk_usage_events PRIMARY KEY (id),
    CONSTRAINT fk_usage_tenant FOREIGN KEY (tenant_id) REFERENCES billing.tenants (id)
);
