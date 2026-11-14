-- OW_BILLING on PostgreSQL 15: translation of
-- services/legacy-billing/db/oracle/schema/01_tables.sql and 02_horror.sql.
--
-- Type mapping (see ../README.md for the full table):
--   VARCHAR2(n) -> varchar(n)        CHAR(1)      -> char(1)
--   NUMBER(p<=4) -> smallint         NUMBER(p<=9) -> integer
--   NUMBER(p<=18) -> bigint          NUMBER(p,s)  -> numeric(p,s)
--   DATE -> date (every source DATE value is midnight; recon proves it),
--           except billing_audit_log.logged_at -> timestamp(0)
--   TIMESTAMP -> timestamp(6)        SYSDATE / SYSTIMESTAMP -> LOCALTIMESTAMP
-- Dirty legacy text columns (DD-MON-YY strings, CSV lists, EAV values) are
-- carried over verbatim on purpose: the takeout is a lift, not a cleanup.
--
-- One deliberate change, agreed with the data owner: the bulk INVOICE_LINE
-- estate gets a real foreign key to INVOICE_HEADER. The lines Oracle let in
-- without a header live unchanged in invoice_line_orphan, with a reason.
\set ON_ERROR_STOP on
SET ROLE ow_billing;
SET search_path = ow_billing, public;

-- Package ordering (ORDER BY code, ORDER BY id, GROUP BY kind) relies on
-- byte-order comparison, the same as Oracle's BINARY sort. Refuse to build
-- on a database with a linguistic default collation.
DO $$
BEGIN
    IF (SELECT datcollate FROM pg_database WHERE datname = current_database()) <> 'C' THEN
        RAISE EXCEPTION 'ow_billing requires a database created with LC_COLLATE=C';
    END IF;
END
$$;

-- ---------------------------------------------------------------------------
-- Transactional core (01_tables.sql)
-- ---------------------------------------------------------------------------

-- Generic lookup table: every *_cd column resolves through here.
CREATE TABLE codes (
    code_type  varchar(30) NOT NULL,
    code_val   smallint    NOT NULL,
    code_desc  varchar(80) NOT NULL,
    CONSTRAINT pk_codes PRIMARY KEY (code_type, code_val)
);

CREATE TABLE tenants (
    id             varchar(36)  NOT NULL,
    name           varchar(200) NOT NULL,
    tax_exempt_yn  char(1) DEFAULT 'N' NOT NULL,
    status_cd      smallint     NOT NULL,   -- CODES('TENANT_STATUS')
    CONSTRAINT pk_tenants PRIMARY KEY (id),
    CONSTRAINT uq_tenants_name UNIQUE (name)
);

CREATE TABLE plans (
    id              varchar(36)   NOT NULL,
    code            varchar(50)   NOT NULL,
    tier_cd         smallint      NOT NULL, -- CODES('PLAN_TIER')
    monthly_fee     numeric(12,2) NOT NULL,
    included_units  bigint        NOT NULL,
    overage_rate    numeric(12,6) NOT NULL,
    active_yn       char(1) DEFAULT 'Y' NOT NULL,
    CONSTRAINT pk_plans PRIMARY KEY (id),
    CONSTRAINT uq_plans_code UNIQUE (code)
);

CREATE TABLE subscriptions (
    id            varchar(36) NOT NULL,
    tenant_id     varchar(36) NOT NULL,
    plan_id       varchar(36) NOT NULL,
    starts_on     date        NOT NULL,
    ends_on       date,
    status_cd     smallint    NOT NULL,     -- CODES('SUB_STATUS')
    suspended_on  date,
    CONSTRAINT pk_subscriptions PRIMARY KEY (id),
    CONSTRAINT fk_sub_tenant FOREIGN KEY (tenant_id) REFERENCES tenants (id),
    CONSTRAINT fk_sub_plan   FOREIGN KEY (plan_id)   REFERENCES plans (id)
);

CREATE TABLE usage_events (
    id           varchar(36)  NOT NULL,
    tenant_id    varchar(36)  NOT NULL,
    occurred_at  timestamp(6) NOT NULL,
    units        bigint       NOT NULL,
    kind_cd      smallint     NOT NULL,     -- CODES('USAGE_KIND')
    CONSTRAINT pk_usage_events PRIMARY KEY (id),
    CONSTRAINT fk_usage_tenant FOREIGN KEY (tenant_id) REFERENCES tenants (id)
);

CREATE TABLE rating_periods (
    id            varchar(36) NOT NULL,
    tenant_id     varchar(36) NOT NULL,
    period_start  date        NOT NULL,
    period_end    date        NOT NULL,
    CONSTRAINT pk_rating_periods PRIMARY KEY (id),
    CONSTRAINT uq_rating_periods UNIQUE (tenant_id, period_start),
    CONSTRAINT fk_rp_tenant FOREIGN KEY (tenant_id) REFERENCES tenants (id)
);

CREATE TABLE rating_results (
    id               varchar(36)   NOT NULL,
    period_id        varchar(36)   NOT NULL,
    subscription_id  varchar(36)   NOT NULL,
    used_units       bigint        NOT NULL,
    quota_units      bigint        NOT NULL,
    rollover_units   bigint        NOT NULL,
    billable_units   bigint        NOT NULL,
    overage_amount   numeric(12,2) NOT NULL,
    created_at       timestamp(6)  NOT NULL,
    CONSTRAINT pk_rating_results PRIMARY KEY (id),
    CONSTRAINT fk_rr_period FOREIGN KEY (period_id)       REFERENCES rating_periods (id),
    CONSTRAINT fk_rr_sub    FOREIGN KEY (subscription_id) REFERENCES subscriptions (id)
);

CREATE TABLE invoices (
    id         varchar(36)   NOT NULL,
    tenant_id  varchar(36)   NOT NULL,
    period_id  varchar(36)   NOT NULL,
    issued_at  timestamp(6)  NOT NULL,
    subtotal   numeric(12,2) NOT NULL,
    tax        numeric(12,2) NOT NULL,
    total      numeric(12,2) NOT NULL,
    status_cd  smallint      NOT NULL,      -- CODES('INV_STATUS')
    CONSTRAINT pk_invoices PRIMARY KEY (id),
    CONSTRAINT fk_inv_tenant FOREIGN KEY (tenant_id) REFERENCES tenants (id),
    CONSTRAINT fk_inv_period FOREIGN KEY (period_id) REFERENCES rating_periods (id)
);

CREATE TABLE invoice_lines (
    id           varchar(36)   NOT NULL,
    invoice_id   varchar(36)   NOT NULL,
    line_no      integer       NOT NULL,
    line_type    varchar(10)   NOT NULL,
    description  varchar(400)  NOT NULL,
    amount       numeric(12,2) NOT NULL,
    CONSTRAINT pk_invoice_lines PRIMARY KEY (id),
    CONSTRAINT uq_invoice_lines UNIQUE (invoice_id, line_no),
    CONSTRAINT fk_il_invoice FOREIGN KEY (invoice_id)
        REFERENCES invoices (id) ON DELETE CASCADE
);

CREATE TABLE credit_notes (
    id                varchar(36)   NOT NULL,
    tenant_id         varchar(36)   NOT NULL,
    issued_on         date          NOT NULL,
    amount            numeric(12,2) NOT NULL,
    remaining_amount  numeric(12,2) NOT NULL,
    CONSTRAINT pk_credit_notes PRIMARY KEY (id),
    CONSTRAINT fk_cn_tenant FOREIGN KEY (tenant_id) REFERENCES tenants (id)
);

CREATE TABLE dunning_attempts (
    id             varchar(36) NOT NULL,
    tenant_id      varchar(36) NOT NULL,
    invoice_id     varchar(36) NOT NULL,
    attempt_no     smallint    NOT NULL,
    scheduled_for  date        NOT NULL,
    status_cd      smallint    NOT NULL,    -- CODES('DUN_STATUS')
    CONSTRAINT pk_dunning_attempts PRIMARY KEY (id),
    CONSTRAINT uq_dunning_attempts UNIQUE (invoice_id, attempt_no),
    CONSTRAINT fk_da_tenant  FOREIGN KEY (tenant_id)  REFERENCES tenants (id),
    CONSTRAINT fk_da_invoice FOREIGN KEY (invoice_id) REFERENCES invoices (id)
);

CREATE TABLE notifications (
    id         varchar(36)  NOT NULL,
    tenant_id  varchar(36)  NOT NULL,
    kind_cd    smallint     NOT NULL,       -- CODES('NOTIF_KIND')
    sent_at    timestamp(6) NOT NULL,
    CONSTRAINT pk_notifications PRIMARY KEY (id),
    CONSTRAINT uq_notifications UNIQUE (tenant_id, kind_cd, sent_at),
    CONSTRAINT fk_notif_tenant FOREIGN KEY (tenant_id) REFERENCES tenants (id)
);

-- Oracle wrote this from an AUTONOMOUS_TRANSACTION; pkg_ow_util.log_msg
-- does the same through its own connection as ow_billing_audit.
CREATE TABLE billing_audit_log (
    log_id     bigint NOT NULL,
    logged_at  timestamp(0) DEFAULT LOCALTIMESTAMP(0) NOT NULL,
    module     varchar(30),
    message    varchar(4000),
    CONSTRAINT pk_billing_audit_log PRIMARY KEY (log_id)
);

CREATE SEQUENCE seq_billing_audit_log START WITH 1 INCREMENT BY 1;
GRANT USAGE ON SCHEMA ow_billing TO ow_billing_audit;
GRANT INSERT ON billing_audit_log TO ow_billing_audit;
GRANT USAGE ON SEQUENCE seq_billing_audit_log TO ow_billing_audit;

CREATE TABLE subscriptions_hist (
    hist_id       bigint NOT NULL,
    hist_dt       varchar(20),              -- yes, still a string
    hist_op       varchar(3),
    id            varchar(36),
    tenant_id     varchar(36),
    plan_id       varchar(36),
    starts_on     date,
    ends_on       date,
    status_cd     smallint,
    suspended_on  date,
    CONSTRAINT pk_subscriptions_hist PRIMARY KEY (hist_id)
);

CREATE SEQUENCE seq_subscriptions_hist START WITH 1 INCREMENT BY 1;

-- Idempotency marker written by the Oracle init (00_init.sh); migrated as data.
CREATE TABLE fixture_meta (
    marker          varchar(100),
    value           varchar(100),
    initialized_at  timestamp(6) DEFAULT LOCALTIMESTAMP NOT NULL
);

-- ---------------------------------------------------------------------------
-- Data-model horror estate (02_horror.sql)
-- ---------------------------------------------------------------------------

-- 155 columns, repeating groups, VARCHAR2 dates and CSV id lists, carried
-- over column for column.
CREATE TABLE customer_master (
    cust_id                varchar(36) NOT NULL,
    cust_seq_no            bigint,
    tenant_id              varchar(36),
    cust_no                varchar(20),
    cust_name              varchar(200),
    cust_name_upper        varchar(200),
    legal_name             varchar(200),
    dba_name               varchar(200),
    addr_line_1            varchar(120),
    addr_line_2            varchar(120),
    addr_line_3            varchar(120),
    addr_line_4            varchar(120),
    addr_line_5            varchar(120),
    addr_line_6            varchar(120),
    city                   varchar(80),
    state_cd               varchar(4),
    zip                    varchar(12),
    zip4                   varchar(6),
    country_cd             varchar(4),
    mail_addr_line_1       varchar(120),
    mail_addr_line_2       varchar(120),
    mail_addr_line_3       varchar(120),
    mail_addr_line_4       varchar(120),
    mail_addr_line_5       varchar(120),
    mail_addr_line_6       varchar(120),
    mail_city              varchar(80),
    mail_state_cd          varchar(4),
    mail_zip               varchar(12),
    phone1                 varchar(25),
    phone2                 varchar(25),
    phone3                 varchar(25),
    phone4                 varchar(25),
    phone1_type_cd         smallint,
    phone2_type_cd         smallint,
    phone3_type_cd         smallint,
    phone4_type_cd         smallint,
    fax                    varchar(25),
    email_1                varchar(200),
    email_2                varchar(200),
    email_3                varchar(200),
    signup_dt              varchar(9),
    last_activity_dt       varchar(9),
    last_invoice_dt        varchar(9),
    last_payment_dt        varchar(9),
    terminate_dt           varchar(9),
    status_cd              smallint,
    sub_status_cd          smallint,
    cust_type_cd           smallint,
    segment_cd             smallint,
    region_cd              smallint,
    territory_cd           smallint,
    channel_cd             smallint,
    rate_class_cd          smallint,
    tax_exempt_yn          char(1),
    credit_hold_yn         char(1),
    dunning_exempt_yn      char(1),
    vip_yn                 char(1),
    cur_bal_amt            numeric(14,2),
    past_due_amt           numeric(14,2),
    ytd_billed_amt         numeric(14,2),
    ltd_billed_amt         numeric(14,2),
    ytd_paid_amt           numeric(14,2),
    credit_limit_amt       numeric(14,2),
    related_acct_ids       varchar(2000),
    child_acct_ids         varchar(2000),
    promo_codes_csv        varchar(1000),
    contact_notes          varchar(4000),
    legacy_sys_key         varchar(50),
    mainframe_acct_no      varchar(30),
    conversion_batch_no    integer,
    flag_01                char(1),
    flag_02                char(1),
    flag_03                char(1),
    flag_04                char(1),
    flag_05                char(1),
    flag_06                char(1),
    flag_07                char(1),
    flag_08                char(1),
    flag_09                char(1),
    flag_10                char(1),
    flag_11                char(1),
    flag_12                char(1),
    flag_13                char(1),
    flag_14                char(1),
    flag_15                char(1),
    flag_16                char(1),
    flag_17                char(1),
    flag_18                char(1),
    flag_19                char(1),
    flag_20                char(1),
    udf_01                 varchar(100),
    udf_02                 varchar(100),
    udf_03                 varchar(100),
    udf_04                 varchar(100),
    udf_05                 varchar(100),
    udf_06                 varchar(100),
    udf_07                 varchar(100),
    udf_08                 varchar(100),
    udf_09                 varchar(100),
    udf_10                 varchar(100),
    udf_11                 varchar(100),
    udf_12                 varchar(100),
    udf_13                 varchar(100),
    udf_14                 varchar(100),
    udf_15                 varchar(100),
    udf_16                 varchar(100),
    udf_17                 varchar(100),
    udf_18                 varchar(100),
    udf_19                 varchar(100),
    udf_20                 varchar(100),
    udf_21                 varchar(100),
    udf_22                 varchar(100),
    udf_23                 varchar(100),
    udf_24                 varchar(100),
    udf_25                 varchar(100),
    udf_26                 varchar(100),
    udf_27                 varchar(100),
    udf_28                 varchar(100),
    udf_29                 varchar(100),
    udf_30                 varchar(100),
    udf_31                 varchar(100),
    udf_32                 varchar(100),
    udf_33                 varchar(100),
    udf_34                 varchar(100),
    udf_35                 varchar(100),
    udf_36                 varchar(100),
    udf_37                 varchar(100),
    udf_38                 varchar(100),
    udf_39                 varchar(100),
    udf_40                 varchar(100),
    udf_amt_01             numeric(14,2),
    udf_amt_02             numeric(14,2),
    udf_amt_03             numeric(14,2),
    udf_amt_04             numeric(14,2),
    udf_amt_05             numeric(14,2),
    udf_amt_06             numeric(14,2),
    udf_amt_07             numeric(14,2),
    udf_amt_08             numeric(14,2),
    udf_amt_09             numeric(14,2),
    udf_amt_10             numeric(14,2),
    udf_dt_01              varchar(9),
    udf_dt_02              varchar(9),
    udf_dt_03              varchar(9),
    udf_dt_04              varchar(9),
    udf_dt_05              varchar(9),
    udf_dt_06              varchar(9),
    udf_dt_07              varchar(9),
    udf_dt_08              varchar(9),
    udf_dt_09              varchar(9),
    udf_dt_10              varchar(9),
    created_by             varchar(30),
    created_dt             date,
    updated_by             varchar(30),
    updated_dt             date,
    row_version_no         integer,
    CONSTRAINT pk_customer_master PRIMARY KEY (cust_id)
);

CREATE TABLE customer_master_hist (
    hist_id                bigint NOT NULL,
    hist_dt                varchar(20),
    hist_op                varchar(3),
    cust_id                varchar(36),
    cust_seq_no            bigint,
    tenant_id              varchar(36),
    cust_no                varchar(20),
    cust_name              varchar(200),
    cust_name_upper        varchar(200),
    legal_name             varchar(200),
    dba_name               varchar(200),
    addr_line_1            varchar(120),
    addr_line_2            varchar(120),
    addr_line_3            varchar(120),
    addr_line_4            varchar(120),
    addr_line_5            varchar(120),
    addr_line_6            varchar(120),
    city                   varchar(80),
    state_cd               varchar(4),
    zip                    varchar(12),
    zip4                   varchar(6),
    country_cd             varchar(4),
    mail_addr_line_1       varchar(120),
    mail_addr_line_2       varchar(120),
    mail_addr_line_3       varchar(120),
    mail_addr_line_4       varchar(120),
    mail_addr_line_5       varchar(120),
    mail_addr_line_6       varchar(120),
    mail_city              varchar(80),
    mail_state_cd          varchar(4),
    mail_zip               varchar(12),
    phone1                 varchar(25),
    phone2                 varchar(25),
    phone3                 varchar(25),
    phone4                 varchar(25),
    phone1_type_cd         smallint,
    phone2_type_cd         smallint,
    phone3_type_cd         smallint,
    phone4_type_cd         smallint,
    fax                    varchar(25),
    email_1                varchar(200),
    email_2                varchar(200),
    email_3                varchar(200),
    signup_dt              varchar(9),
    last_activity_dt       varchar(9),
    last_invoice_dt        varchar(9),
    last_payment_dt        varchar(9),
    terminate_dt           varchar(9),
    status_cd              smallint,
    sub_status_cd          smallint,
    cust_type_cd           smallint,
    segment_cd             smallint,
    region_cd              smallint,
    territory_cd           smallint,
    channel_cd             smallint,
    rate_class_cd          smallint,
    tax_exempt_yn          char(1),
    credit_hold_yn         char(1),
    dunning_exempt_yn      char(1),
    vip_yn                 char(1),
    cur_bal_amt            numeric(14,2),
    past_due_amt           numeric(14,2),
    ytd_billed_amt         numeric(14,2),
    ltd_billed_amt         numeric(14,2),
    ytd_paid_amt           numeric(14,2),
    credit_limit_amt       numeric(14,2),
    related_acct_ids       varchar(2000),
    child_acct_ids         varchar(2000),
    promo_codes_csv        varchar(1000),
    contact_notes          varchar(4000),
    legacy_sys_key         varchar(50),
    mainframe_acct_no      varchar(30),
    conversion_batch_no    integer,
    flag_01                char(1),
    flag_02                char(1),
    flag_03                char(1),
    flag_04                char(1),
    flag_05                char(1),
    flag_06                char(1),
    flag_07                char(1),
    flag_08                char(1),
    flag_09                char(1),
    flag_10                char(1),
    flag_11                char(1),
    flag_12                char(1),
    flag_13                char(1),
    flag_14                char(1),
    flag_15                char(1),
    flag_16                char(1),
    flag_17                char(1),
    flag_18                char(1),
    flag_19                char(1),
    flag_20                char(1),
    udf_01                 varchar(100),
    udf_02                 varchar(100),
    udf_03                 varchar(100),
    udf_04                 varchar(100),
    udf_05                 varchar(100),
    udf_06                 varchar(100),
    udf_07                 varchar(100),
    udf_08                 varchar(100),
    udf_09                 varchar(100),
    udf_10                 varchar(100),
    udf_11                 varchar(100),
    udf_12                 varchar(100),
    udf_13                 varchar(100),
    udf_14                 varchar(100),
    udf_15                 varchar(100),
    udf_16                 varchar(100),
    udf_17                 varchar(100),
    udf_18                 varchar(100),
    udf_19                 varchar(100),
    udf_20                 varchar(100),
    udf_21                 varchar(100),
    udf_22                 varchar(100),
    udf_23                 varchar(100),
    udf_24                 varchar(100),
    udf_25                 varchar(100),
    udf_26                 varchar(100),
    udf_27                 varchar(100),
    udf_28                 varchar(100),
    udf_29                 varchar(100),
    udf_30                 varchar(100),
    udf_31                 varchar(100),
    udf_32                 varchar(100),
    udf_33                 varchar(100),
    udf_34                 varchar(100),
    udf_35                 varchar(100),
    udf_36                 varchar(100),
    udf_37                 varchar(100),
    udf_38                 varchar(100),
    udf_39                 varchar(100),
    udf_40                 varchar(100),
    udf_amt_01             numeric(14,2),
    udf_amt_02             numeric(14,2),
    udf_amt_03             numeric(14,2),
    udf_amt_04             numeric(14,2),
    udf_amt_05             numeric(14,2),
    udf_amt_06             numeric(14,2),
    udf_amt_07             numeric(14,2),
    udf_amt_08             numeric(14,2),
    udf_amt_09             numeric(14,2),
    udf_amt_10             numeric(14,2),
    udf_dt_01              varchar(9),
    udf_dt_02              varchar(9),
    udf_dt_03              varchar(9),
    udf_dt_04              varchar(9),
    udf_dt_05              varchar(9),
    udf_dt_06              varchar(9),
    udf_dt_07              varchar(9),
    udf_dt_08              varchar(9),
    udf_dt_09              varchar(9),
    udf_dt_10              varchar(9),
    created_by             varchar(30),
    created_dt             date,
    updated_by             varchar(30),
    updated_dt             date,
    row_version_no         integer,
    CONSTRAINT pk_customer_master_hist PRIMARY KEY (hist_id)
);

CREATE SEQUENCE seq_customer_master START WITH 100000 INCREMENT BY 1;
CREATE SEQUENCE seq_customer_master_hist START WITH 1 INCREMENT BY 1;

-- Entity-attribute-value dumping ground.
CREATE TABLE entity_attr_value (
    eav_id       bigint       NOT NULL,
    entity_type  varchar(30)  NOT NULL,   -- 'CUSTOMER', 'INVOICE', ...
    entity_id    varchar(36)  NOT NULL,
    attr_name    varchar(100) NOT NULL,
    attr_value   varchar(4000),
    attr_type    varchar(10) DEFAULT 'STR',
    created_dt   varchar(9),              -- DD-MON-YY text
    CONSTRAINT pk_entity_attr_value PRIMARY KEY (eav_id)
);

CREATE SEQUENCE seq_entity_attr_value START WITH 1 INCREMENT BY 1;

CREATE TABLE invoice_header (
    invoice_id  varchar(36) NOT NULL,
    invoice_no  varchar(30),
    cust_id     varchar(36),
    tenant_id   varchar(36),
    invoice_dt  varchar(9),               -- DD-MON-YY text
    due_dt      varchar(9),
    status_cd   smallint,                 -- CODES('INV_STATUS')
    total_amt   numeric(14,2),
    batch_no    integer,
    CONSTRAINT pk_invoice_header PRIMARY KEY (invoice_id)
);

CREATE INDEX ix_invoice_header_batch_no ON invoice_header (batch_no);

-- Bulk invoice lines. Unlike Oracle, every row here has a header: invoice_id
-- is NOT NULL and enforced by fk_invoice_line_header.
CREATE TABLE invoice_line (
    line_id         varchar(36) NOT NULL,
    invoice_no      varchar(30),
    invoice_id      varchar(36) NOT NULL,
    cust_id         varchar(36),          -- unenforced pointer at customer_master (as in Oracle)
    cust_no         varchar(20),
    cust_name       varchar(200),         -- denormalized copy
    tenant_id       varchar(36),
    line_no         integer,
    line_type_cd    smallint,
    item_desc       varchar(400),
    qty             numeric(12,3),
    unit_price      numeric(14,4),
    amount          numeric(14,2),
    tax_amt         numeric(14,2),
    invoice_dt      varchar(9),           -- DD-MON-YY text
    service_period  varchar(20),          -- 'MMYYYY-MMYYYY' text
    posted_yn       char(1),
    gl_acct_csv     varchar(200),         -- comma-separated GL account splits
    batch_no        integer,
    src_system      varchar(10),
    CONSTRAINT pk_invoice_line PRIMARY KEY (line_id),
    CONSTRAINT fk_invoice_line_header FOREIGN KEY (invoice_id)
        REFERENCES invoice_header (invoice_id)
);

CREATE INDEX ix_invoice_line_invoice_id ON invoice_line (invoice_id);

-- Quarantine for Oracle INVOICE_LINE rows with no INVOICE_HEADER (the
-- DEMO-GHOST lines). Source columns unchanged, plus why the row is here.
-- Kept for Finance review; never joined into month-end totals.
CREATE TABLE invoice_line_orphan (
    line_id            varchar(36) NOT NULL,
    invoice_no         varchar(30),
    invoice_id         varchar(36),
    cust_id            varchar(36),
    cust_no            varchar(20),
    cust_name          varchar(200),
    tenant_id          varchar(36),
    line_no            integer,
    line_type_cd       smallint,
    item_desc          varchar(400),
    qty                numeric(12,3),
    unit_price         numeric(14,4),
    amount             numeric(14,2),
    tax_amt            numeric(14,2),
    invoice_dt         varchar(9),
    service_period     varchar(20),
    posted_yn          char(1),
    gl_acct_csv        varchar(200),
    batch_no           integer,
    src_system         varchar(10),
    quarantine_reason  varchar(200) NOT NULL,
    CONSTRAINT pk_invoice_line_orphan PRIMARY KEY (line_id)
);

-- ---------------------------------------------------------------------------
-- Triggers (Oracle row triggers -> PL/pgSQL trigger functions)
-- ---------------------------------------------------------------------------

CREATE FUNCTION trg_billing_audit_log_id() RETURNS trigger
LANGUAGE plpgsql SET search_path = ow_billing, public AS $$
BEGIN
    IF NEW.log_id IS NULL THEN
        NEW.log_id := nextval('seq_billing_audit_log');
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_billing_audit_log_id BEFORE INSERT ON billing_audit_log
    FOR EACH ROW EXECUTE FUNCTION trg_billing_audit_log_id();

-- Full-row-copy version history for subscriptions.
CREATE FUNCTION trg_subscriptions_hist() RETURNS trigger
LANGUAGE plpgsql SET search_path = ow_billing, public AS $$
BEGIN
    INSERT INTO subscriptions_hist (
        hist_id, hist_dt, hist_op, id, tenant_id, plan_id,
        starts_on, ends_on, status_cd, suspended_on
    ) VALUES (
        nextval('seq_subscriptions_hist'),
        to_char(LOCALTIMESTAMP(0), 'DD-MON-YY HH24:MI:SS'),
        CASE TG_OP WHEN 'UPDATE' THEN 'UPD' ELSE 'DEL' END,
        OLD.id, OLD.tenant_id, OLD.plan_id,
        OLD.starts_on, OLD.ends_on, OLD.status_cd, OLD.suspended_on
    );
    RETURN NULL;
END
$$;
CREATE TRIGGER trg_subscriptions_hist AFTER UPDATE OR DELETE ON subscriptions
    FOR EACH ROW EXECUTE FUNCTION trg_subscriptions_hist();

-- A cancelled subscription can never leave the cancelled state.
CREATE FUNCTION trg_sub_no_uncancel() RETURNS trigger
LANGUAGE plpgsql SET search_path = ow_billing, public AS $$
BEGIN
    IF OLD.status_cd = 30 THEN
        NEW.status_cd := 30;
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_sub_no_uncancel BEFORE UPDATE OF status_cd ON subscriptions
    FOR EACH ROW EXECUTE FUNCTION trg_sub_no_uncancel();

-- Usage must be positive and of a known kind. SQLSTATEs OW001/OW002 stand in
-- for ORA-20001/ORA-20002.
CREATE FUNCTION trg_usage_events_check() RETURNS trigger
LANGUAGE plpgsql SET search_path = ow_billing, public AS $$
BEGIN
    IF coalesce(NEW.units, 0) <= 0 THEN
        RAISE EXCEPTION 'units must be > 0' USING ERRCODE = 'OW001';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM codes
                    WHERE code_type = 'USAGE_KIND' AND code_val = NEW.kind_cd) THEN
        RAISE EXCEPTION 'unknown usage kind %', coalesce(NEW.kind_cd::text, '')
            USING ERRCODE = 'OW002';
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_usage_events_check BEFORE INSERT ON usage_events
    FOR EACH ROW EXECUTE FUNCTION trg_usage_events_check();

CREATE FUNCTION trg_customer_master_seq() RETURNS trigger
LANGUAGE plpgsql SET search_path = ow_billing, public AS $$
BEGIN
    IF NEW.cust_seq_no IS NULL THEN
        NEW.cust_seq_no := nextval('seq_customer_master');
    END IF;
    NEW.cust_name_upper := upper(NEW.cust_name);
    NEW.row_version_no := coalesce(NEW.row_version_no, 1);
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_customer_master_seq BEFORE INSERT ON customer_master
    FOR EACH ROW EXECUTE FUNCTION trg_customer_master_seq();

-- customer_master_hist is (hist_id, hist_dt, hist_op) followed by every
-- customer_master column in the same order, so OLD.* lines up positionally.
CREATE FUNCTION trg_customer_master_hist() RETURNS trigger
LANGUAGE plpgsql SET search_path = ow_billing, public AS $$
BEGIN
    INSERT INTO customer_master_hist
    SELECT nextval('seq_customer_master_hist'),
           to_char(LOCALTIMESTAMP(0), 'DD-MON-YY HH24:MI:SS'),
           CASE TG_OP WHEN 'UPDATE' THEN 'UPD' ELSE 'DEL' END,
           (OLD).*;
    RETURN NULL;
END
$$;
CREATE TRIGGER trg_customer_master_hist AFTER UPDATE OR DELETE ON customer_master
    FOR EACH ROW EXECUTE FUNCTION trg_customer_master_hist();

CREATE FUNCTION trg_entity_attr_value_seq() RETURNS trigger
LANGUAGE plpgsql SET search_path = ow_billing, public AS $$
BEGIN
    IF NEW.eav_id IS NULL THEN
        NEW.eav_id := nextval('seq_entity_attr_value');
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_entity_attr_value_seq BEFORE INSERT ON entity_attr_value
    FOR EACH ROW EXECUTE FUNCTION trg_entity_attr_value_seq();

-- ---------------------------------------------------------------------------
-- Takeout bookkeeping (not an Oracle table). migrate.py writes the Oracle-side
-- per-batch figures here at load time; /api/reports/reconciliation recomputes
-- them from Postgres so drift is caught after Oracle is gone.
-- ---------------------------------------------------------------------------
CREATE TABLE migration_baseline (
    batch_no    integer     NOT NULL,
    check_name  varchar(60) NOT NULL,
    expected    varchar(64),
    CONSTRAINT pk_migration_baseline PRIMARY KEY (batch_no, check_name)
);
