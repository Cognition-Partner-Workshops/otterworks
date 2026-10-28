-- u-plans writable tables, Lakebase database ow_tp branch mig-1793185083,
-- schema mig_1793185083.
-- Nullability, uniques and foreign keys mirror the OW_BILLING source as the
-- recon tier-0 structural grade reads them; Oracle DATE lands as timestamp(0)
-- per the oracle-plsql canonicalization type_map (date needs
-- census_midnight_only evidence the spec does not carry).

CREATE SCHEMA IF NOT EXISTS mig_1793185083;

DROP TABLE IF EXISTS mig_1793185083.subscriptions;
DROP TABLE IF EXISTS mig_1793185083.subscriptions_hist;
DROP TABLE IF EXISTS mig_1793185083.plans;
DROP TABLE IF EXISTS mig_1793185083.codes;
DROP TABLE IF EXISTS mig_1793185083.tenants;
DROP SEQUENCE IF EXISTS mig_1793185083.seq_subscriptions_hist;

CREATE TABLE mig_1793185083.plans (
    id             varchar(36) PRIMARY KEY,
    code           varchar(50) NOT NULL,
    tier_cd        bigint NOT NULL,
    monthly_fee    numeric(12,2) NOT NULL,
    included_units bigint NOT NULL,
    overage_rate   numeric(12,6) NOT NULL,
    active_yn      char(1) NOT NULL,
    UNIQUE (code)
);

CREATE TABLE mig_1793185083.codes (
    code_type varchar(30),
    code_val  bigint,
    code_desc varchar(80) NOT NULL,
    PRIMARY KEY (code_type, code_val)
);

CREATE TABLE mig_1793185083.tenants (
    id           varchar(36) PRIMARY KEY,
    name         varchar(200) NOT NULL,
    tax_exempt_yn char(1) NOT NULL,
    status_cd    bigint NOT NULL,
    UNIQUE (name)
);

CREATE TABLE mig_1793185083.subscriptions (
    id           varchar(36) PRIMARY KEY,
    tenant_id    varchar(36) NOT NULL,
    plan_id      varchar(36) NOT NULL,
    starts_on    timestamp(0) NOT NULL,
    ends_on      timestamp(0),
    status_cd    bigint NOT NULL,
    suspended_on timestamp(0),
    FOREIGN KEY (tenant_id) REFERENCES mig_1793185083.tenants (id),
    FOREIGN KEY (plan_id)   REFERENCES mig_1793185083.plans (id)
);

CREATE TABLE mig_1793185083.subscriptions_hist (
    hist_id      bigint PRIMARY KEY,
    hist_dt      text,
    hist_dt_raw  varchar(20),
    hist_op      varchar(3),
    id           varchar(36),
    tenant_id    varchar(36),
    plan_id      varchar(36),
    starts_on    timestamp(0),
    ends_on      timestamp(0),
    status_cd    bigint,
    suspended_on timestamp(0)
);

CREATE SEQUENCE mig_1793185083.seq_subscriptions_hist START WITH 1;
