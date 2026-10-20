-- Access model. claims_reader and claims_adjuster are group roles with no
-- privilege on schema claims; both read the same views in claims_api, which
-- return PII in clear only when the querying role is a member of
-- claims_adjuster and masked (shared/compliance-kit/postgres/01_masking.sql)
-- otherwise. Login roles reader_demo and adjuster_demo exist for the
-- side-by-side run; production logins are granted one of the two groups.
\set ON_ERROR_STOP on

CREATE ROLE claims_reader NOLOGIN;
CREATE ROLE claims_adjuster NOLOGIN;
CREATE ROLE reader_demo LOGIN PASSWORD 'reader_demo' IN ROLE claims_reader;
CREATE ROLE adjuster_demo LOGIN PASSWORD 'adjuster_demo' IN ROLE claims_adjuster;

REVOKE ALL ON SCHEMA claims FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA claims FROM PUBLIC;
REVOKE ALL ON SCHEMA compliance FROM PUBLIC;

CREATE SCHEMA claims_api;
REVOKE ALL ON SCHEMA claims_api FROM PUBLIC;
GRANT USAGE ON SCHEMA claims_api, compliance TO claims_reader, claims_adjuster;

-- current_user inside a view is the role running the query, not the view
-- owner, so one view serves both roles.
CREATE FUNCTION claims_api.sees_pii() RETURNS boolean
LANGUAGE sql STABLE AS $$ SELECT pg_has_role(current_user, 'claims_adjuster', 'MEMBER') $$;

CREATE VIEW claims_api.claimant WITH (security_barrier) AS
SELECT p.claimant_id,
       CASE WHEN claims_api.sees_pii() THEN concat_ws(' ', p.given_name, p.surname)
            ELSE compliance.mask_name(concat_ws(' ', p.given_name, p.surname)) END AS claimant_name,
       CASE WHEN claims_api.sees_pii() THEN p.tax_id ELSE compliance.mask_tax_id(p.tax_id) END AS tax_id,
       CASE WHEN claims_api.sees_pii() THEN p.date_of_birth::text ELSE compliance.mask_date(p.date_of_birth) END AS date_of_birth,
       CASE WHEN claims_api.sees_pii() THEN p.phone ELSE compliance.mask_phone(p.phone) END AS phone,
       CASE WHEN claims_api.sees_pii() THEN p.email ELSE compliance.mask_keep_last(p.email, 0) END AS email,
       CASE WHEN claims_api.sees_pii() THEN concat_ws(', ', p.street, p.city, p.state || ' ' || p.postal_code)
            ELSE concat_ws(', ', compliance.mask_street(p.street), p.city, p.state || ' ' || p.postal_code) END AS address,
       CASE WHEN claims_api.sees_pii() THEN p.bank_account ELSE compliance.mask_account(p.bank_account) END AS bank_account,
       p.synthetic_fields,
       p.pii_purged_at
  FROM claims.claimant p;

CREATE VIEW claims_api.claim WITH (security_barrier) AS
SELECT claim_number, claimant_id, policy_number, lob, producer_id, loss_cause, loss_date, reported_date,
       loss_city, loss_state, loss_postal_code, estimated_loss, injury, police_report, incident_desc,
       status, closed_at, legal_hold
  FROM claims.claim;

-- Payees of type CL are claimants (individuals); vendors (VN) and salvage
-- yards (SV) are businesses and stay readable.
CREATE VIEW claims_api.payment WITH (security_barrier) AS
SELECT p.instruction_id, p.claim_number,
       CASE WHEN claims_api.sees_pii() OR p.payee_type <> 'CL' THEN p.payee_name
            ELSE compliance.mask_name(p.payee_name) END AS payee_name,
       p.payee_type,
       CASE WHEN claims_api.sees_pii() OR p.payee_type <> 'CL' THEN p.bank_account_masked
            ELSE compliance.mask_account(p.bank_account_masked) END AS bank_account_masked,
       p.value_date, p.currency,
       (SELECT sum(l.amount) FROM claims.payment_line l WHERE l.instruction_id = p.instruction_id) AS net_amount
  FROM claims.payment p;

CREATE VIEW claims_api.assignment WITH (security_barrier) AS
SELECT request_id, claim_number,
       CASE WHEN claims_api.sees_pii() THEN claimant_name ELSE compliance.mask_name(claimant_name) END AS claimant_name,
       lob, loss_cause, region, severity, required_skill, requested_date, estimated_amount
  FROM claims.assignment;

GRANT SELECT ON ALL TABLES IN SCHEMA claims_api TO claims_reader, claims_adjuster;
GRANT EXECUTE ON FUNCTION claims_api.sees_pii() TO claims_reader, claims_adjuster;
