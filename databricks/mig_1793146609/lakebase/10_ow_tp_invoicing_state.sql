-- Run databricks-1793146609, batch w1-b02 (units pkg_ow_util, pkg_plans, pkg_rating,
-- pkg_invoicing, pkg_dunning). Lakebase project ow-tp-billing, database ow_tp, branch
-- mig-invoicing-w1, schema ow_tp_invoicing. Keys, uniques, foreign keys and NOT NULLs
-- follow OW_BILLING (services/legacy-billing/db/oracle/schema/01_tables.sql).
-- Idempotent by drop/recreate of all fourteen tables (FK order); a rerun must be
-- followed by extract_state.py | load_state.py.

CREATE SCHEMA IF NOT EXISTS ow_tp_invoicing;

DROP TABLE IF EXISTS ow_tp_invoicing.billing_audit_log;
DROP TABLE IF EXISTS ow_tp_invoicing.notifications;
DROP TABLE IF EXISTS ow_tp_invoicing.dunning_attempts;
DROP TABLE IF EXISTS ow_tp_invoicing.credit_notes;
DROP TABLE IF EXISTS ow_tp_invoicing.invoice_lines;
DROP TABLE IF EXISTS ow_tp_invoicing.invoices;
DROP TABLE IF EXISTS ow_tp_invoicing.rating_results;
DROP TABLE IF EXISTS ow_tp_invoicing.rating_periods;
DROP TABLE IF EXISTS ow_tp_invoicing.usage_events;
DROP TABLE IF EXISTS ow_tp_invoicing.subscriptions_hist;
DROP TABLE IF EXISTS ow_tp_invoicing.subscriptions;
DROP TABLE IF EXISTS ow_tp_invoicing.plans;
DROP TABLE IF EXISTS ow_tp_invoicing.tenants;
DROP TABLE IF EXISTS ow_tp_invoicing.codes;

DROP SEQUENCE IF EXISTS ow_tp_invoicing.billing_audit_log_seq;
DROP SEQUENCE IF EXISTS ow_tp_invoicing.subscriptions_hist_seq;

-- reference --------------------------------------------------------------------------------
CREATE TABLE ow_tp_invoicing.codes (
    code_type   varchar(30) NOT NULL,
    code_val    bigint      NOT NULL,
    code_desc   varchar(80) NOT NULL,
    CONSTRAINT pk_codes PRIMARY KEY (code_type, code_val)
);

CREATE TABLE ow_tp_invoicing.tenants (
    id            varchar(36)  NOT NULL,
    name          varchar(200) NOT NULL,
    tax_exempt_yn char(1)      NOT NULL DEFAULT 'N',
    status_cd     bigint       NOT NULL,
    CONSTRAINT pk_tenants PRIMARY KEY (id),
    CONSTRAINT uq_tenants_name UNIQUE (name)
);

CREATE TABLE ow_tp_invoicing.plans (
    id             varchar(36)  NOT NULL,
    code           varchar(50)  NOT NULL,
    tier_cd        bigint       NOT NULL,
    monthly_fee    numeric(12,2) NOT NULL,
    included_units bigint       NOT NULL,
    overage_rate   numeric(12,6) NOT NULL,
    active_yn      char(1)      NOT NULL DEFAULT 'Y',
    CONSTRAINT pk_plans PRIMARY KEY (id),
    CONSTRAINT uq_plans_code UNIQUE (code)
);

-- pkg_plans ---------------------------------------------------------------------------------
CREATE TABLE ow_tp_invoicing.subscriptions (
    id           varchar(36)  NOT NULL,
    tenant_id    varchar(36)  NOT NULL,
    plan_id      varchar(36)  NOT NULL,
    starts_on    timestamp(0) NOT NULL,
    ends_on      timestamp(0),
    status_cd    bigint       NOT NULL,
    suspended_on timestamp(0),
    CONSTRAINT pk_subscriptions PRIMARY KEY (id),
    CONSTRAINT fk_sub_tenant FOREIGN KEY (tenant_id) REFERENCES ow_tp_invoicing.tenants (id),
    CONSTRAINT fk_sub_plan FOREIGN KEY (plan_id) REFERENCES ow_tp_invoicing.plans (id)
);

-- SEQ_SUBSCRIPTIONS_HIST + TRG_SUBSCRIPTIONS_HIST's NEXTVAL -> plain sequence default
CREATE SEQUENCE ow_tp_invoicing.subscriptions_hist_seq;
CREATE TABLE ow_tp_invoicing.subscriptions_hist (
    hist_id      bigint NOT NULL DEFAULT nextval('ow_tp_invoicing.subscriptions_hist_seq'),
    hist_dt      varchar(20),
    hist_op      varchar(3),
    id           varchar(36),
    tenant_id    varchar(36),
    plan_id      varchar(36),
    starts_on    timestamp(0),
    ends_on      timestamp(0),
    status_cd    bigint,
    suspended_on timestamp(0),
    CONSTRAINT pk_subscriptions_hist PRIMARY KEY (hist_id)
);

-- pkg_rating ---------------------------------------------------------------------------------
CREATE TABLE ow_tp_invoicing.usage_events (
    id          varchar(36)  NOT NULL,
    tenant_id   varchar(36)  NOT NULL,
    occurred_at timestamp(6) NOT NULL,
    units       bigint       NOT NULL,
    kind_cd     bigint       NOT NULL,
    CONSTRAINT pk_usage_events PRIMARY KEY (id),
    CONSTRAINT fk_usage_tenant FOREIGN KEY (tenant_id) REFERENCES ow_tp_invoicing.tenants (id)
);

CREATE TABLE ow_tp_invoicing.rating_periods (
    id           varchar(36)  NOT NULL,
    tenant_id    varchar(36)  NOT NULL,
    period_start timestamp(0) NOT NULL,
    period_end   timestamp(0) NOT NULL,
    CONSTRAINT pk_rating_periods PRIMARY KEY (id),
    CONSTRAINT uq_rating_periods UNIQUE (tenant_id, period_start),
    CONSTRAINT fk_rp_tenant FOREIGN KEY (tenant_id) REFERENCES ow_tp_invoicing.tenants (id)
);

CREATE TABLE ow_tp_invoicing.rating_results (
    id              varchar(36)   NOT NULL,
    period_id       varchar(36)   NOT NULL,
    subscription_id varchar(36)   NOT NULL,
    used_units      bigint        NOT NULL,
    quota_units     bigint        NOT NULL,
    rollover_units  bigint        NOT NULL,
    billable_units  bigint        NOT NULL,
    overage_amount  numeric(12,2) NOT NULL,
    created_at      timestamp(6)  NOT NULL,
    CONSTRAINT pk_rating_results PRIMARY KEY (id),
    CONSTRAINT fk_rr_period FOREIGN KEY (period_id) REFERENCES ow_tp_invoicing.rating_periods (id),
    CONSTRAINT fk_rr_sub FOREIGN KEY (subscription_id) REFERENCES ow_tp_invoicing.subscriptions (id)
);

-- pkg_invoicing ------------------------------------------------------------------------------
CREATE TABLE ow_tp_invoicing.invoices (
    id        varchar(36)   NOT NULL,
    tenant_id varchar(36)   NOT NULL,
    period_id varchar(36)   NOT NULL,
    issued_at timestamp(6)  NOT NULL,
    subtotal  numeric(12,2) NOT NULL,
    tax       numeric(12,2) NOT NULL,
    total     numeric(12,2) NOT NULL,
    status_cd bigint        NOT NULL,
    CONSTRAINT pk_invoices PRIMARY KEY (id),
    CONSTRAINT fk_inv_tenant FOREIGN KEY (tenant_id) REFERENCES ow_tp_invoicing.tenants (id),
    CONSTRAINT fk_inv_period FOREIGN KEY (period_id) REFERENCES ow_tp_invoicing.rating_periods (id)
);

CREATE TABLE ow_tp_invoicing.invoice_lines (
    id          varchar(36)   NOT NULL,
    invoice_id  varchar(36)   NOT NULL,
    line_no     bigint        NOT NULL,
    line_type   varchar(10)   NOT NULL,
    description varchar(400)  NOT NULL,
    amount      numeric(12,2) NOT NULL,
    CONSTRAINT pk_invoice_lines PRIMARY KEY (id),
    CONSTRAINT uq_invoice_lines UNIQUE (invoice_id, line_no),
    CONSTRAINT fk_il_invoice FOREIGN KEY (invoice_id) REFERENCES ow_tp_invoicing.invoices (id) ON DELETE CASCADE
);

CREATE TABLE ow_tp_invoicing.credit_notes (
    id               varchar(36)   NOT NULL,
    tenant_id        varchar(36)   NOT NULL,
    issued_on        timestamp(0)  NOT NULL,
    amount           numeric(12,2) NOT NULL,
    remaining_amount numeric(12,2) NOT NULL,
    CONSTRAINT pk_credit_notes PRIMARY KEY (id),
    CONSTRAINT fk_cn_tenant FOREIGN KEY (tenant_id) REFERENCES ow_tp_invoicing.tenants (id)
);

-- pkg_dunning --------------------------------------------------------------------------------
CREATE TABLE ow_tp_invoicing.dunning_attempts (
    id            varchar(36)  NOT NULL,
    tenant_id     varchar(36)  NOT NULL,
    invoice_id    varchar(36)  NOT NULL,
    attempt_no    bigint       NOT NULL,
    scheduled_for timestamp(0) NOT NULL,
    status_cd     bigint       NOT NULL,
    CONSTRAINT pk_dunning_attempts PRIMARY KEY (id),
    CONSTRAINT uq_dunning_attempts UNIQUE (invoice_id, attempt_no),
    CONSTRAINT fk_da_tenant FOREIGN KEY (tenant_id) REFERENCES ow_tp_invoicing.tenants (id),
    CONSTRAINT fk_da_invoice FOREIGN KEY (invoice_id) REFERENCES ow_tp_invoicing.invoices (id)
);

CREATE TABLE ow_tp_invoicing.notifications (
    id        varchar(36)  NOT NULL,
    tenant_id varchar(36)  NOT NULL,
    kind_cd   bigint       NOT NULL,
    sent_at   timestamp(6) NOT NULL,
    CONSTRAINT pk_notifications PRIMARY KEY (id),
    CONSTRAINT uq_notifications UNIQUE (tenant_id, kind_cd, sent_at),
    CONSTRAINT fk_notif_tenant FOREIGN KEY (tenant_id) REFERENCES ow_tp_invoicing.tenants (id)
);

-- pkg_ow_util --------------------------------------------------------------------------------
-- SEQ_BILLING_AUDIT_LOG + TRG_BILLING_AUDIT_LOG_ID -> plain sequence default
CREATE SEQUENCE ow_tp_invoicing.billing_audit_log_seq;
CREATE TABLE ow_tp_invoicing.billing_audit_log (
    log_id    bigint NOT NULL DEFAULT nextval('ow_tp_invoicing.billing_audit_log_seq'),
    logged_at timestamp(0) NOT NULL DEFAULT date_trunc('second', localtimestamp),
    module    varchar(30),
    message   varchar(4000),
    CONSTRAINT pk_billing_audit_log PRIMARY KEY (log_id)
);

-- TRG_USAGE_EVENTS_CHECK: usage must be positive and of a known kind.
CREATE OR REPLACE FUNCTION ow_tp_invoicing.trg_usage_events_check()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF coalesce(NEW.units, 0) <= 0 THEN
        RAISE EXCEPTION 'units must be > 0' USING ERRCODE = '20001';
    END IF;
    PERFORM 1 FROM ow_tp_invoicing.codes
     WHERE code_type = 'USAGE_KIND' AND code_val = NEW.kind_cd;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'unknown usage kind %', NEW.kind_cd USING ERRCODE = '20002';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_usage_events_check ON ow_tp_invoicing.usage_events;
CREATE TRIGGER trg_usage_events_check
BEFORE INSERT ON ow_tp_invoicing.usage_events
FOR EACH ROW EXECUTE FUNCTION ow_tp_invoicing.trg_usage_events_check();
