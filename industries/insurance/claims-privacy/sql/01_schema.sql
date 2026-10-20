-- Claims privacy module: claims and claimants seeded from the BizTalk
-- claims hub corpus. Base tables live in schema claims and are granted to
-- nobody; readers and adjusters query the views in claims_api (03_access.sql).
\set ON_ERROR_STOP on

CREATE SCHEMA claims;

CREATE TABLE claims.claimant (
    claimant_id      int PRIMARY KEY,
    given_name       text,
    surname          text,
    tax_id           text,
    date_of_birth    date,
    phone            text,
    email            text,
    street           text,
    city             text,
    state            char(2),
    postal_code      text,
    bank_account     text,
    synthetic_fields text[] NOT NULL DEFAULT '{}',
    pii_purged_at    timestamptz,
    source_message   text NOT NULL
);

CREATE TABLE claims.claim (
    claim_number     text PRIMARY KEY,
    claimant_id      int  NOT NULL REFERENCES claims.claimant,
    policy_number    text NOT NULL,
    lob              text NOT NULL,
    producer_id      text,
    loss_cause       text NOT NULL,
    loss_date        date NOT NULL,
    reported_date    date NOT NULL,
    loss_city        text,
    loss_state       char(2),
    loss_postal_code text,
    estimated_loss   numeric(12, 2) NOT NULL,
    injury           boolean NOT NULL,
    police_report    boolean,
    incident_desc    text,
    status           text NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'CLOSED', 'REOPENED')),
    closed_at        date,
    legal_hold       boolean NOT NULL DEFAULT false,
    source_message   text NOT NULL,
    CONSTRAINT ck_claim_closed CHECK ((status = 'CLOSED') = (closed_at IS NOT NULL))
);

CREATE TABLE claims.payment (
    instruction_id      text PRIMARY KEY,
    claim_number        text NOT NULL REFERENCES claims.claim,
    payee_name          text,
    payee_type          text NOT NULL,
    bank_account_masked text,
    value_date          date NOT NULL,
    currency            char(3) NOT NULL,
    source_message      text NOT NULL
);

CREATE TABLE claims.payment_line (
    instruction_id text NOT NULL REFERENCES claims.payment,
    line_no        int  NOT NULL,
    line_type      text NOT NULL,
    amount         numeric(12, 2) NOT NULL,
    gl_account     text,
    memo           text,
    PRIMARY KEY (instruction_id, line_no)
);

CREATE TABLE claims.assignment (
    request_id       text PRIMARY KEY,
    claim_number     text NOT NULL REFERENCES claims.claim,
    claimant_name    text,
    lob              text,
    loss_cause       text,
    region           text,
    severity         text,
    required_skill   text,
    requested_date   date NOT NULL,
    estimated_amount numeric(12, 2),
    source_message   text NOT NULL
);

-- Row audit from the compliance kit; PII columns are stored as [redacted]
-- so the trail is not a second copy of the data it guards.
CREATE TRIGGER trg_aud_claimant AFTER INSERT OR UPDATE OR DELETE ON claims.claimant
    FOR EACH ROW EXECUTE FUNCTION compliance.audit_row_change_trg(
        'claimant_id', 'given_name', 'surname', 'tax_id', 'date_of_birth', 'phone', 'email', 'street', 'bank_account');
CREATE TRIGGER trg_aud_claim AFTER INSERT OR UPDATE OR DELETE ON claims.claim
    FOR EACH ROW EXECUTE FUNCTION compliance.audit_row_change_trg('claim_number');
CREATE TRIGGER trg_aud_payment AFTER INSERT OR UPDATE OR DELETE ON claims.payment
    FOR EACH ROW EXECUTE FUNCTION compliance.audit_row_change_trg('instruction_id', 'payee_name');
CREATE TRIGGER trg_aud_assignment AFTER INSERT OR UPDATE OR DELETE ON claims.assignment
    FOR EACH ROW EXECUTE FUNCTION compliance.audit_row_change_trg('request_id', 'claimant_name');
