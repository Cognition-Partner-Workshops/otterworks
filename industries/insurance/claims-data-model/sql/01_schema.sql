-- PostgreSQL 16 target. Two schemas:
--   commission  verbatim copies of the COMMISSION_PAY tables (Oracle), money numeric(12,2) as in Oracle
--   claims      the claims and policy data model: policyholders, policies, claims, claim_payments,
--               adjuster_assignments, seeded from the claims hub corpus and the Commission Pay policies
-- dbt builds staging (stg) and marts (marts) over both. Re-running drops and recreates everything.
DROP SCHEMA IF EXISTS marts CASCADE;
DROP SCHEMA IF EXISTS stg CASCADE;
DROP SCHEMA IF EXISTS claims CASCADE;
DROP SCHEMA IF EXISTS commission CASCADE;
CREATE SCHEMA commission;
CREATE SCHEMA claims;

CREATE TABLE commission.agents (
    agent_id    integer      PRIMARY KEY,
    agent_code  varchar(16)  NOT NULL UNIQUE,
    full_name   varchar(120) NOT NULL,
    license_no  varchar(32)  NOT NULL UNIQUE,
    status      varchar(12)  NOT NULL CHECK (status IN ('ACTIVE', 'SUSPENDED', 'TERMINATED')),
    hired_date  date         NOT NULL
);

CREATE TABLE commission.products (
    product_code     varchar(16)  PRIMARY KEY,
    product_name     varchar(120) NOT NULL,
    line_of_business varchar(24)  NOT NULL CHECK (line_of_business IN ('AUTO', 'HOME', 'LIFE', 'COMMERCIAL'))
);

CREATE TABLE commission.policies (
    policy_id      integer       PRIMARY KEY,
    policy_no      varchar(24)   NOT NULL UNIQUE,
    product_code   varchar(16)   NOT NULL REFERENCES commission.products (product_code),
    holder_name    varchar(120)  NOT NULL,
    annual_premium numeric(12,2) NOT NULL CHECK (annual_premium > 0),
    issued_date    date          NOT NULL,
    status         varchar(12)   NOT NULL CHECK (status IN ('IN_FORCE', 'LAPSED', 'CANCELLED'))
);

CREATE TABLE commission.commission_rates (
    rate_id        integer      PRIMARY KEY,
    product_code   varchar(16)  NOT NULL REFERENCES commission.products (product_code),
    agent_id       integer      REFERENCES commission.agents (agent_id),
    rate_pct       numeric(5,2) NOT NULL,
    effective_from date         NOT NULL,
    effective_to   date,
    created_by     varchar(64)  NOT NULL
);

CREATE TABLE commission.commission_splits (
    split_id  integer      PRIMARY KEY,
    policy_id integer      NOT NULL REFERENCES commission.policies (policy_id),
    agent_id  integer      NOT NULL REFERENCES commission.agents (agent_id),
    split_pct numeric(5,2) NOT NULL,
    UNIQUE (policy_id, agent_id)
);

CREATE TABLE commission.commission_ledger (
    ledger_id      integer       PRIMARY KEY,
    policy_id      integer       NOT NULL REFERENCES commission.policies (policy_id),
    agent_id       integer       NOT NULL REFERENCES commission.agents (agent_id),
    period_month   char(7)       NOT NULL CHECK (period_month ~ '^[0-9]{4}-[0-9]{2}$'),
    rate_id        integer       NOT NULL REFERENCES commission.commission_rates (rate_id),
    split_pct      numeric(5,2)  NOT NULL,
    base_premium   numeric(12,2) NOT NULL,
    commission_amt numeric(12,2) NOT NULL,
    UNIQUE (policy_id, agent_id, period_month)
);

-- One row per insured party. CP-nnnnnn for Commission Pay holders (keyed by policy_id, the fixture has no
-- party table), the policy system's InsuredPartyId (PTY-nnnnnn) for claims hub policies.
CREATE TABLE claims.policyholders (
    policyholder_id varchar(16)  PRIMARY KEY,
    source_system   varchar(16)  NOT NULL CHECK (source_system IN ('COMMISSION_PAY', 'CLAIMS_HUB')),
    full_name       varchar(120) NOT NULL,
    tax_id_masked   varchar(16)
);

-- Commission Pay policies carry premium and product; claims hub policies carry deductible, limit and
-- expiry (the policy inquiry stubs). Neither source has the other's columns.
CREATE TABLE claims.policies (
    policy_no        varchar(24)   PRIMARY KEY,
    source_system    varchar(16)   NOT NULL CHECK (source_system IN ('COMMISSION_PAY', 'CLAIMS_HUB')),
    policyholder_id  varchar(16)   NOT NULL REFERENCES claims.policyholders (policyholder_id),
    line_of_business varchar(24)   NOT NULL,
    product_code     varchar(16)   REFERENCES commission.products (product_code),
    status           varchar(12)   NOT NULL CHECK (status IN ('IN_FORCE', 'LAPSED', 'CANCELLED')),
    effective_date   date          NOT NULL,
    expiration_date  date,
    annual_premium   numeric(12,2),
    deductible       numeric(12,2),
    coverage_limit   numeric(12,2)
);

CREATE TABLE claims.claims (
    claim_number            varchar(20)   PRIMARY KEY,
    policy_no               varchar(24)   NOT NULL REFERENCES claims.policies (policy_no),
    policyholder_id         varchar(16)   NOT NULL REFERENCES claims.policyholders (policyholder_id),
    agency_id               varchar(16)   NOT NULL,
    line_of_business        varchar(24)   NOT NULL,
    loss_cause              varchar(8)    NOT NULL,
    loss_date               date          NOT NULL,
    reported_date           date          NOT NULL,
    report_delay_days       integer       NOT NULL,
    policy_age_days_at_loss integer       NOT NULL,
    injury_flag             boolean       NOT NULL,
    police_report_flag      boolean       NOT NULL,
    prior_fraud_flag        boolean       NOT NULL,
    in_force_at_loss        boolean       NOT NULL,
    estimated_amount        numeric(12,2) NOT NULL,
    net_exposure            numeric(12,2) NOT NULL,
    reserve_estimate        numeric(12,2) NOT NULL,
    triage_outcome          varchar(24)   NOT NULL
        CHECK (triage_outcome IN ('DECLINE_NOT_IN_FORCE', 'FRAUD_REVIEW', 'FAST_TRACK', 'LARGE_LOSS', 'STANDARD')),
    entered_claims_system   boolean       NOT NULL
);

-- One row per payment instruction. The ledger columns are what usp_PostClaimPayment receives (summed per
-- line type, then rounded half to even, .NET Math.Round); the vendor columns are what the remittance file
-- carries (each line rounded half up on its absolute value, XSLT round(), then summed). The ledger is the book
-- of record (decided 2026-10-20); vendor_rounding_difference is the vendor file's net less net_amount, shown
-- rather than allocated (non-zero only for PI-2026-880107: 0.01).
CREATE TABLE claims.claim_payments (
    instruction_id        varchar(20)   PRIMARY KEY,
    claim_number          varchar(20)   NOT NULL REFERENCES claims.claims (claim_number),
    instruction_policy_no varchar(24)   NOT NULL,
    vendor_code           varchar(8)    NOT NULL,
    payee_name            varchar(120)  NOT NULL,
    payee_type            varchar(2)    NOT NULL,
    value_date            date          NOT NULL,
    currency              char(3)       NOT NULL,
    line_count            integer       NOT NULL,
    indemnity_amount      numeric(12,2) NOT NULL,
    expense_amount        numeric(12,2) NOT NULL,
    salvage_credit        numeric(12,2) NOT NULL,
    net_amount            numeric(12,2) NOT NULL,
    vendor_debit_total    numeric(12,2) NOT NULL,
    vendor_credit_total   numeric(12,2) NOT NULL,
    vendor_rounding_difference numeric(12,2) NOT NULL,
    CHECK (vendor_rounding_difference = vendor_debit_total - vendor_credit_total - net_amount)
);

CREATE TABLE claims.adjuster_assignments (
    request_id       varchar(16)   PRIMARY KEY,
    claim_number     varchar(20)   NOT NULL REFERENCES claims.claims (claim_number),
    line_of_business varchar(24)   NOT NULL,
    loss_cause       varchar(8)    NOT NULL,
    region           varchar(16)   NOT NULL,
    severity         varchar(4)    NOT NULL CHECK (severity IN ('HIGH', 'MED', 'LOW')),
    required_skill   varchar(16)   NOT NULL,
    requested_date   date          NOT NULL,
    estimated_amount numeric(12,2) NOT NULL,
    adjuster_id      varchar(16),
    adjuster_name    varchar(120),
    adjuster_email   varchar(120),
    sla_days         integer       NOT NULL,
    sla_due_date     date          NOT NULL,
    escalated        boolean       NOT NULL,
    CHECK (escalated = (adjuster_id IS NULL))
);
