-- mig_1793176531 wave-0 scaffold (unit: scaffold, batch w0-b01)
-- Idempotent DDL for the run-scoped namespaces and the 14 recon legacy
-- mirrors. Creates only objects inside the isolated ow_tp schemas declared
-- by the wave manifest; never touches customer production catalogs.
-- Structure only: snapshot row loads land per-unit in later waves.
-- Rerun-safe on loaded tables: NOT NULL and constraint fixes are metadata
-- ALTERs (UC constraints are informational), never DROP/REPLACE.

CREATE SCHEMA IF NOT EXISTS ow_tp.r1793176531_staging;
CREATE SCHEMA IF NOT EXISTS ow_tp.r1793176531_recon;
CREATE SCHEMA IF NOT EXISTS ow_tp.r1793176531_quarantine;
CREATE SCHEMA IF NOT EXISTS ow_tp.r1793176531_history;


-- OW_BILLING.CODES -> ow_tp.r1793176531_recon.legacy_codes (structural mirror)
CREATE TABLE IF NOT EXISTS ow_tp.r1793176531_recon.legacy_codes (
    code_type STRING NOT NULL,
    code_val BIGINT NOT NULL,
    code_desc STRING NOT NULL,
    CONSTRAINT legacy_codes_pk PRIMARY KEY (code_type, code_val)
)
USING DELTA;

-- OW_BILLING.TENANTS -> ow_tp.r1793176531_recon.legacy_tenants (structural mirror)
CREATE TABLE IF NOT EXISTS ow_tp.r1793176531_recon.legacy_tenants (
    id STRING NOT NULL,
    name STRING NOT NULL,
    tax_exempt_yn STRING NOT NULL,
    status_cd BIGINT NOT NULL,
    CONSTRAINT legacy_tenants_pk PRIMARY KEY (id),
    CONSTRAINT legacy_tenants_uq1 UNIQUE (name)
)
USING DELTA;

-- OW_BILLING.PLANS -> ow_tp.r1793176531_recon.legacy_plans (structural mirror)
CREATE TABLE IF NOT EXISTS ow_tp.r1793176531_recon.legacy_plans (
    id STRING NOT NULL,
    code STRING NOT NULL,
    tier_cd BIGINT NOT NULL,
    monthly_fee DECIMAL(12,2) NOT NULL,
    included_units BIGINT NOT NULL,
    overage_rate DECIMAL(12,6) NOT NULL,
    active_yn STRING NOT NULL,
    CONSTRAINT legacy_plans_pk PRIMARY KEY (id),
    CONSTRAINT legacy_plans_uq1 UNIQUE (code)
)
USING DELTA;

-- OW_BILLING.SUBSCRIPTIONS -> ow_tp.r1793176531_recon.legacy_subscriptions (structural mirror)
CREATE TABLE IF NOT EXISTS ow_tp.r1793176531_recon.legacy_subscriptions (
    id STRING NOT NULL,
    tenant_id STRING NOT NULL,
    plan_id STRING NOT NULL,
    starts_on TIMESTAMP_NTZ NOT NULL,
    ends_on TIMESTAMP_NTZ,
    status_cd BIGINT NOT NULL,
    suspended_on TIMESTAMP_NTZ,
    CONSTRAINT legacy_subscriptions_pk PRIMARY KEY (id)
)
USING DELTA;

-- OW_BILLING.USAGE_EVENTS -> ow_tp.r1793176531_recon.legacy_usage_events (structural mirror)
CREATE TABLE IF NOT EXISTS ow_tp.r1793176531_recon.legacy_usage_events (
    id STRING NOT NULL,
    tenant_id STRING NOT NULL,
    occurred_at TIMESTAMP_NTZ NOT NULL,
    units BIGINT NOT NULL,
    kind_cd BIGINT NOT NULL,
    CONSTRAINT legacy_usage_events_pk PRIMARY KEY (id)
)
USING DELTA;

-- OW_BILLING.RATING_PERIODS -> ow_tp.r1793176531_recon.legacy_rating_periods (structural mirror)
CREATE TABLE IF NOT EXISTS ow_tp.r1793176531_recon.legacy_rating_periods (
    id STRING NOT NULL,
    tenant_id STRING NOT NULL,
    period_start TIMESTAMP_NTZ NOT NULL,
    period_end TIMESTAMP_NTZ NOT NULL,
    CONSTRAINT legacy_rating_periods_pk PRIMARY KEY (id),
    CONSTRAINT legacy_rating_periods_uq1 UNIQUE (tenant_id, period_start)
)
USING DELTA;

-- OW_BILLING.RATING_RESULTS -> ow_tp.r1793176531_recon.legacy_rating_results (structural mirror)
CREATE TABLE IF NOT EXISTS ow_tp.r1793176531_recon.legacy_rating_results (
    id STRING NOT NULL,
    period_id STRING NOT NULL,
    subscription_id STRING NOT NULL,
    used_units BIGINT NOT NULL,
    quota_units BIGINT NOT NULL,
    rollover_units BIGINT NOT NULL,
    billable_units BIGINT NOT NULL,
    overage_amount DECIMAL(12,2) NOT NULL,
    created_at TIMESTAMP_NTZ NOT NULL,
    CONSTRAINT legacy_rating_results_pk PRIMARY KEY (id)
)
USING DELTA;

-- OW_BILLING.INVOICES -> ow_tp.r1793176531_recon.legacy_invoices (structural mirror)
CREATE TABLE IF NOT EXISTS ow_tp.r1793176531_recon.legacy_invoices (
    id STRING NOT NULL,
    tenant_id STRING NOT NULL,
    period_id STRING NOT NULL,
    issued_at TIMESTAMP_NTZ NOT NULL,
    subtotal DECIMAL(12,2) NOT NULL,
    tax DECIMAL(12,2) NOT NULL,
    total DECIMAL(12,2) NOT NULL,
    status_cd BIGINT NOT NULL,
    CONSTRAINT legacy_invoices_pk PRIMARY KEY (id)
)
USING DELTA;

-- OW_BILLING.INVOICE_LINES -> ow_tp.r1793176531_recon.legacy_invoice_lines (structural mirror)
CREATE TABLE IF NOT EXISTS ow_tp.r1793176531_recon.legacy_invoice_lines (
    id STRING NOT NULL,
    invoice_id STRING NOT NULL,
    line_no BIGINT NOT NULL,
    line_type STRING NOT NULL,
    description STRING NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    CONSTRAINT legacy_invoice_lines_pk PRIMARY KEY (id),
    CONSTRAINT legacy_invoice_lines_uq1 UNIQUE (invoice_id, line_no)
)
USING DELTA;

-- OW_BILLING.CREDIT_NOTES -> ow_tp.r1793176531_recon.legacy_credit_notes (structural mirror)
CREATE TABLE IF NOT EXISTS ow_tp.r1793176531_recon.legacy_credit_notes (
    id STRING NOT NULL,
    tenant_id STRING NOT NULL,
    issued_on TIMESTAMP_NTZ NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    remaining_amount DECIMAL(12,2) NOT NULL,
    CONSTRAINT legacy_credit_notes_pk PRIMARY KEY (id)
)
USING DELTA;

-- OW_BILLING.DUNNING_ATTEMPTS -> ow_tp.r1793176531_recon.legacy_dunning_attempts (structural mirror)
CREATE TABLE IF NOT EXISTS ow_tp.r1793176531_recon.legacy_dunning_attempts (
    id STRING NOT NULL,
    tenant_id STRING NOT NULL,
    invoice_id STRING NOT NULL,
    attempt_no BIGINT NOT NULL,
    scheduled_for TIMESTAMP_NTZ NOT NULL,
    status_cd BIGINT NOT NULL,
    CONSTRAINT legacy_dunning_attempts_pk PRIMARY KEY (id),
    CONSTRAINT legacy_dunning_attempts_uq1 UNIQUE (invoice_id, attempt_no)
)
USING DELTA;

-- OW_BILLING.NOTIFICATIONS -> ow_tp.r1793176531_recon.legacy_notifications (structural mirror)
CREATE TABLE IF NOT EXISTS ow_tp.r1793176531_recon.legacy_notifications (
    id STRING NOT NULL,
    tenant_id STRING NOT NULL,
    kind_cd BIGINT NOT NULL,
    sent_at TIMESTAMP_NTZ NOT NULL,
    CONSTRAINT legacy_notifications_pk PRIMARY KEY (id),
    CONSTRAINT legacy_notifications_uq1 UNIQUE (tenant_id, kind_cd, sent_at)
)
USING DELTA;

-- OW_BILLING.BILLING_AUDIT_LOG -> ow_tp.r1793176531_recon.legacy_billing_audit_log (structural mirror)
CREATE TABLE IF NOT EXISTS ow_tp.r1793176531_recon.legacy_billing_audit_log (
    log_id BIGINT NOT NULL,
    logged_at TIMESTAMP_NTZ NOT NULL,
    module STRING,
    message STRING,
    CONSTRAINT legacy_billing_audit_log_pk PRIMARY KEY (log_id)
)
USING DELTA;

-- OW_BILLING.SUBSCRIPTIONS_HIST -> ow_tp.r1793176531_recon.legacy_subscriptions_hist (structural mirror)
CREATE TABLE IF NOT EXISTS ow_tp.r1793176531_recon.legacy_subscriptions_hist (
    hist_id BIGINT NOT NULL,
    hist_dt STRING,
    hist_op STRING,
    id STRING,
    tenant_id STRING,
    plan_id STRING,
    starts_on TIMESTAMP_NTZ,
    ends_on TIMESTAMP_NTZ,
    status_cd BIGINT,
    suspended_on TIMESTAMP_NTZ,
    CONSTRAINT legacy_subscriptions_hist_pk PRIMARY KEY (hist_id)
)
USING DELTA;

-- constraint + nullability convergence for ow_tp.r1793176531_recon.legacy_codes (idempotent)
ALTER TABLE ow_tp.r1793176531_recon.legacy_codes ALTER COLUMN code_desc SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_codes DROP CONSTRAINT IF EXISTS legacy_codes_pk;
ALTER TABLE ow_tp.r1793176531_recon.legacy_codes ADD CONSTRAINT legacy_codes_pk PRIMARY KEY (code_type, code_val);

-- constraint + nullability convergence for ow_tp.r1793176531_recon.legacy_tenants (idempotent)
ALTER TABLE ow_tp.r1793176531_recon.legacy_tenants ALTER COLUMN name SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_tenants ALTER COLUMN status_cd SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_tenants ALTER COLUMN tax_exempt_yn SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_tenants DROP CONSTRAINT IF EXISTS legacy_tenants_pk;
ALTER TABLE ow_tp.r1793176531_recon.legacy_tenants ADD CONSTRAINT legacy_tenants_pk PRIMARY KEY (id);
ALTER TABLE ow_tp.r1793176531_recon.legacy_tenants DROP CONSTRAINT IF EXISTS legacy_tenants_uq1;
ALTER TABLE ow_tp.r1793176531_recon.legacy_tenants ADD CONSTRAINT legacy_tenants_uq1 UNIQUE (name);

-- constraint + nullability convergence for ow_tp.r1793176531_recon.legacy_plans (idempotent)
ALTER TABLE ow_tp.r1793176531_recon.legacy_plans ALTER COLUMN active_yn SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_plans ALTER COLUMN code SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_plans ALTER COLUMN included_units SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_plans ALTER COLUMN monthly_fee SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_plans ALTER COLUMN overage_rate SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_plans ALTER COLUMN tier_cd SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_plans DROP CONSTRAINT IF EXISTS legacy_plans_pk;
ALTER TABLE ow_tp.r1793176531_recon.legacy_plans ADD CONSTRAINT legacy_plans_pk PRIMARY KEY (id);
ALTER TABLE ow_tp.r1793176531_recon.legacy_plans DROP CONSTRAINT IF EXISTS legacy_plans_uq1;
ALTER TABLE ow_tp.r1793176531_recon.legacy_plans ADD CONSTRAINT legacy_plans_uq1 UNIQUE (code);

-- constraint + nullability convergence for ow_tp.r1793176531_recon.legacy_subscriptions (idempotent)
ALTER TABLE ow_tp.r1793176531_recon.legacy_subscriptions ALTER COLUMN plan_id SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_subscriptions ALTER COLUMN starts_on SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_subscriptions ALTER COLUMN status_cd SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_subscriptions ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_subscriptions DROP CONSTRAINT IF EXISTS legacy_subscriptions_pk;
ALTER TABLE ow_tp.r1793176531_recon.legacy_subscriptions ADD CONSTRAINT legacy_subscriptions_pk PRIMARY KEY (id);
ALTER TABLE ow_tp.r1793176531_recon.legacy_subscriptions DROP CONSTRAINT IF EXISTS legacy_subscriptions_fk1;
ALTER TABLE ow_tp.r1793176531_recon.legacy_subscriptions ADD CONSTRAINT legacy_subscriptions_fk1 FOREIGN KEY (plan_id) REFERENCES ow_tp.r1793176531_recon.legacy_plans (id);
ALTER TABLE ow_tp.r1793176531_recon.legacy_subscriptions DROP CONSTRAINT IF EXISTS legacy_subscriptions_fk2;
ALTER TABLE ow_tp.r1793176531_recon.legacy_subscriptions ADD CONSTRAINT legacy_subscriptions_fk2 FOREIGN KEY (tenant_id) REFERENCES ow_tp.r1793176531_recon.legacy_tenants (id);

-- constraint + nullability convergence for ow_tp.r1793176531_recon.legacy_usage_events (idempotent)
ALTER TABLE ow_tp.r1793176531_recon.legacy_usage_events ALTER COLUMN kind_cd SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_usage_events ALTER COLUMN occurred_at SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_usage_events ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_usage_events ALTER COLUMN units SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_usage_events DROP CONSTRAINT IF EXISTS legacy_usage_events_pk;
ALTER TABLE ow_tp.r1793176531_recon.legacy_usage_events ADD CONSTRAINT legacy_usage_events_pk PRIMARY KEY (id);
ALTER TABLE ow_tp.r1793176531_recon.legacy_usage_events DROP CONSTRAINT IF EXISTS legacy_usage_events_fk1;
ALTER TABLE ow_tp.r1793176531_recon.legacy_usage_events ADD CONSTRAINT legacy_usage_events_fk1 FOREIGN KEY (tenant_id) REFERENCES ow_tp.r1793176531_recon.legacy_tenants (id);

-- constraint + nullability convergence for ow_tp.r1793176531_recon.legacy_rating_periods (idempotent)
ALTER TABLE ow_tp.r1793176531_recon.legacy_rating_periods ALTER COLUMN period_end SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_rating_periods ALTER COLUMN period_start SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_rating_periods ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_rating_periods DROP CONSTRAINT IF EXISTS legacy_rating_periods_pk;
ALTER TABLE ow_tp.r1793176531_recon.legacy_rating_periods ADD CONSTRAINT legacy_rating_periods_pk PRIMARY KEY (id);
ALTER TABLE ow_tp.r1793176531_recon.legacy_rating_periods DROP CONSTRAINT IF EXISTS legacy_rating_periods_uq1;
ALTER TABLE ow_tp.r1793176531_recon.legacy_rating_periods ADD CONSTRAINT legacy_rating_periods_uq1 UNIQUE (tenant_id, period_start);
ALTER TABLE ow_tp.r1793176531_recon.legacy_rating_periods DROP CONSTRAINT IF EXISTS legacy_rating_periods_fk1;
ALTER TABLE ow_tp.r1793176531_recon.legacy_rating_periods ADD CONSTRAINT legacy_rating_periods_fk1 FOREIGN KEY (tenant_id) REFERENCES ow_tp.r1793176531_recon.legacy_tenants (id);

-- constraint + nullability convergence for ow_tp.r1793176531_recon.legacy_rating_results (idempotent)
ALTER TABLE ow_tp.r1793176531_recon.legacy_rating_results ALTER COLUMN billable_units SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_rating_results ALTER COLUMN created_at SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_rating_results ALTER COLUMN overage_amount SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_rating_results ALTER COLUMN period_id SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_rating_results ALTER COLUMN quota_units SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_rating_results ALTER COLUMN rollover_units SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_rating_results ALTER COLUMN subscription_id SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_rating_results ALTER COLUMN used_units SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_rating_results DROP CONSTRAINT IF EXISTS legacy_rating_results_pk;
ALTER TABLE ow_tp.r1793176531_recon.legacy_rating_results ADD CONSTRAINT legacy_rating_results_pk PRIMARY KEY (id);
ALTER TABLE ow_tp.r1793176531_recon.legacy_rating_results DROP CONSTRAINT IF EXISTS legacy_rating_results_fk1;
ALTER TABLE ow_tp.r1793176531_recon.legacy_rating_results ADD CONSTRAINT legacy_rating_results_fk1 FOREIGN KEY (period_id) REFERENCES ow_tp.r1793176531_recon.legacy_rating_periods (id);
ALTER TABLE ow_tp.r1793176531_recon.legacy_rating_results DROP CONSTRAINT IF EXISTS legacy_rating_results_fk2;
ALTER TABLE ow_tp.r1793176531_recon.legacy_rating_results ADD CONSTRAINT legacy_rating_results_fk2 FOREIGN KEY (subscription_id) REFERENCES ow_tp.r1793176531_recon.legacy_subscriptions (id);

-- constraint + nullability convergence for ow_tp.r1793176531_recon.legacy_invoices (idempotent)
ALTER TABLE ow_tp.r1793176531_recon.legacy_invoices ALTER COLUMN issued_at SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_invoices ALTER COLUMN period_id SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_invoices ALTER COLUMN status_cd SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_invoices ALTER COLUMN subtotal SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_invoices ALTER COLUMN tax SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_invoices ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_invoices ALTER COLUMN total SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_invoices DROP CONSTRAINT IF EXISTS legacy_invoices_pk;
ALTER TABLE ow_tp.r1793176531_recon.legacy_invoices ADD CONSTRAINT legacy_invoices_pk PRIMARY KEY (id);
ALTER TABLE ow_tp.r1793176531_recon.legacy_invoices DROP CONSTRAINT IF EXISTS legacy_invoices_fk1;
ALTER TABLE ow_tp.r1793176531_recon.legacy_invoices ADD CONSTRAINT legacy_invoices_fk1 FOREIGN KEY (period_id) REFERENCES ow_tp.r1793176531_recon.legacy_rating_periods (id);
ALTER TABLE ow_tp.r1793176531_recon.legacy_invoices DROP CONSTRAINT IF EXISTS legacy_invoices_fk2;
ALTER TABLE ow_tp.r1793176531_recon.legacy_invoices ADD CONSTRAINT legacy_invoices_fk2 FOREIGN KEY (tenant_id) REFERENCES ow_tp.r1793176531_recon.legacy_tenants (id);

-- constraint + nullability convergence for ow_tp.r1793176531_recon.legacy_invoice_lines (idempotent)
ALTER TABLE ow_tp.r1793176531_recon.legacy_invoice_lines ALTER COLUMN amount SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_invoice_lines ALTER COLUMN description SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_invoice_lines ALTER COLUMN invoice_id SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_invoice_lines ALTER COLUMN line_no SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_invoice_lines ALTER COLUMN line_type SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_invoice_lines DROP CONSTRAINT IF EXISTS legacy_invoice_lines_pk;
ALTER TABLE ow_tp.r1793176531_recon.legacy_invoice_lines ADD CONSTRAINT legacy_invoice_lines_pk PRIMARY KEY (id);
ALTER TABLE ow_tp.r1793176531_recon.legacy_invoice_lines DROP CONSTRAINT IF EXISTS legacy_invoice_lines_uq1;
ALTER TABLE ow_tp.r1793176531_recon.legacy_invoice_lines ADD CONSTRAINT legacy_invoice_lines_uq1 UNIQUE (invoice_id, line_no);
ALTER TABLE ow_tp.r1793176531_recon.legacy_invoice_lines DROP CONSTRAINT IF EXISTS legacy_invoice_lines_fk1;
ALTER TABLE ow_tp.r1793176531_recon.legacy_invoice_lines ADD CONSTRAINT legacy_invoice_lines_fk1 FOREIGN KEY (invoice_id) REFERENCES ow_tp.r1793176531_recon.legacy_invoices (id);

-- constraint + nullability convergence for ow_tp.r1793176531_recon.legacy_credit_notes (idempotent)
ALTER TABLE ow_tp.r1793176531_recon.legacy_credit_notes ALTER COLUMN amount SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_credit_notes ALTER COLUMN issued_on SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_credit_notes ALTER COLUMN remaining_amount SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_credit_notes ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_credit_notes DROP CONSTRAINT IF EXISTS legacy_credit_notes_pk;
ALTER TABLE ow_tp.r1793176531_recon.legacy_credit_notes ADD CONSTRAINT legacy_credit_notes_pk PRIMARY KEY (id);
ALTER TABLE ow_tp.r1793176531_recon.legacy_credit_notes DROP CONSTRAINT IF EXISTS legacy_credit_notes_fk1;
ALTER TABLE ow_tp.r1793176531_recon.legacy_credit_notes ADD CONSTRAINT legacy_credit_notes_fk1 FOREIGN KEY (tenant_id) REFERENCES ow_tp.r1793176531_recon.legacy_tenants (id);

-- constraint + nullability convergence for ow_tp.r1793176531_recon.legacy_dunning_attempts (idempotent)
ALTER TABLE ow_tp.r1793176531_recon.legacy_dunning_attempts ALTER COLUMN attempt_no SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_dunning_attempts ALTER COLUMN invoice_id SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_dunning_attempts ALTER COLUMN scheduled_for SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_dunning_attempts ALTER COLUMN status_cd SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_dunning_attempts ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_dunning_attempts DROP CONSTRAINT IF EXISTS legacy_dunning_attempts_pk;
ALTER TABLE ow_tp.r1793176531_recon.legacy_dunning_attempts ADD CONSTRAINT legacy_dunning_attempts_pk PRIMARY KEY (id);
ALTER TABLE ow_tp.r1793176531_recon.legacy_dunning_attempts DROP CONSTRAINT IF EXISTS legacy_dunning_attempts_uq1;
ALTER TABLE ow_tp.r1793176531_recon.legacy_dunning_attempts ADD CONSTRAINT legacy_dunning_attempts_uq1 UNIQUE (invoice_id, attempt_no);
ALTER TABLE ow_tp.r1793176531_recon.legacy_dunning_attempts DROP CONSTRAINT IF EXISTS legacy_dunning_attempts_fk1;
ALTER TABLE ow_tp.r1793176531_recon.legacy_dunning_attempts ADD CONSTRAINT legacy_dunning_attempts_fk1 FOREIGN KEY (invoice_id) REFERENCES ow_tp.r1793176531_recon.legacy_invoices (id);
ALTER TABLE ow_tp.r1793176531_recon.legacy_dunning_attempts DROP CONSTRAINT IF EXISTS legacy_dunning_attempts_fk2;
ALTER TABLE ow_tp.r1793176531_recon.legacy_dunning_attempts ADD CONSTRAINT legacy_dunning_attempts_fk2 FOREIGN KEY (tenant_id) REFERENCES ow_tp.r1793176531_recon.legacy_tenants (id);

-- constraint + nullability convergence for ow_tp.r1793176531_recon.legacy_notifications (idempotent)
ALTER TABLE ow_tp.r1793176531_recon.legacy_notifications ALTER COLUMN kind_cd SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_notifications ALTER COLUMN sent_at SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_notifications ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_notifications DROP CONSTRAINT IF EXISTS legacy_notifications_pk;
ALTER TABLE ow_tp.r1793176531_recon.legacy_notifications ADD CONSTRAINT legacy_notifications_pk PRIMARY KEY (id);
ALTER TABLE ow_tp.r1793176531_recon.legacy_notifications DROP CONSTRAINT IF EXISTS legacy_notifications_uq1;
ALTER TABLE ow_tp.r1793176531_recon.legacy_notifications ADD CONSTRAINT legacy_notifications_uq1 UNIQUE (tenant_id, kind_cd, sent_at);
ALTER TABLE ow_tp.r1793176531_recon.legacy_notifications DROP CONSTRAINT IF EXISTS legacy_notifications_fk1;
ALTER TABLE ow_tp.r1793176531_recon.legacy_notifications ADD CONSTRAINT legacy_notifications_fk1 FOREIGN KEY (tenant_id) REFERENCES ow_tp.r1793176531_recon.legacy_tenants (id);

-- constraint + nullability convergence for ow_tp.r1793176531_recon.legacy_billing_audit_log (idempotent)
ALTER TABLE ow_tp.r1793176531_recon.legacy_billing_audit_log ALTER COLUMN logged_at SET NOT NULL;
ALTER TABLE ow_tp.r1793176531_recon.legacy_billing_audit_log DROP CONSTRAINT IF EXISTS legacy_billing_audit_log_pk;
ALTER TABLE ow_tp.r1793176531_recon.legacy_billing_audit_log ADD CONSTRAINT legacy_billing_audit_log_pk PRIMARY KEY (log_id);

-- constraint + nullability convergence for ow_tp.r1793176531_recon.legacy_subscriptions_hist (idempotent)
ALTER TABLE ow_tp.r1793176531_recon.legacy_subscriptions_hist DROP CONSTRAINT IF EXISTS legacy_subscriptions_hist_pk;
ALTER TABLE ow_tp.r1793176531_recon.legacy_subscriptions_hist ADD CONSTRAINT legacy_subscriptions_hist_pk PRIMARY KEY (hist_id);
