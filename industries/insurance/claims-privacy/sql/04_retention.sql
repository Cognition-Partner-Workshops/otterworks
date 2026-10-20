-- Claims PII retention (RETENTION-POLICY.md, rule CP-1).
-- A claimant's PII is purged once every claim they have is CLOSED, none is
-- on legal hold, and retention_years (default 7) have passed since the later
-- of closed_at and the last payment value date on each claim. REOPENED and
-- OPEN claims never qualify. The claim, payment and assignment records stay
-- (amounts, dates, causes); only the personal fields are set to NULL.
-- loss_state lets the carrier run a different period per state; a claimant
-- with claims in more than one state is left to a run without loss_state.

-- clock_start is NULL unless the claim is closed.
CREATE VIEW claims.v_claim_retention AS
SELECT c.claim_number, c.claimant_id, c.loss_state, c.status, c.legal_hold, c.closed_at,
       p.last_payment_date,
       CASE WHEN c.status = 'CLOSED' THEN greatest(c.closed_at, p.last_payment_date) END AS clock_start
  FROM claims.claim c
  LEFT JOIN (SELECT claim_number, max(value_date) AS last_payment_date
               FROM claims.payment GROUP BY claim_number) p USING (claim_number);

CREATE FUNCTION claims.purge_closed_claim_pii(
    as_of           date    DEFAULT current_date,
    retention_years int     DEFAULT 7,
    dry_run         boolean DEFAULT true,
    loss_state      char(2) DEFAULT NULL
) RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE
    policy    constant text := 'claims-pii-closed';
    eligible  text;
    claimants bigint;
    ids       int[];
BEGIN
    IF retention_years IS NULL OR retention_years < 1 THEN
        RAISE EXCEPTION 'retention_years must be at least 1, got %', retention_years;
    END IF;

    -- Claimant ids whose PII may go; $1 is as_of.
    eligible := format(
        'SELECT k.claimant_id FROM claims.claimant k'
        || ' WHERE k.pii_purged_at IS NULL'
        || '   AND EXISTS (SELECT 1 FROM claims.claim c WHERE c.claimant_id = k.claimant_id)%s'
        || '   AND NOT EXISTS (SELECT 1 FROM claims.v_claim_retention r WHERE r.claimant_id = k.claimant_id'
        || '        AND (r.clock_start IS NULL OR r.legal_hold'
        || '             OR r.clock_start + make_interval(years => %s) > $1))',
        CASE WHEN loss_state IS NULL THEN '' ELSE format(
            ' AND NOT EXISTS (SELECT 1 FROM claims.claim o WHERE o.claimant_id = k.claimant_id'
            || ' AND o.loss_state IS DISTINCT FROM %L)', loss_state) END,
        retention_years);

    IF NOT dry_run THEN
        -- Hold eligibility still while the four statements below run.
        LOCK TABLE claims.claim, claims.payment IN SHARE MODE;
        EXECUTE format('SELECT array_agg(claimant_id) FROM (%s) e', eligible) INTO ids USING as_of;
    END IF;

    PERFORM compliance.purge(policy, 'claims.payment',
        format('payee_type = ''CL'' AND (payee_name IS NOT NULL OR bank_account_masked IS NOT NULL)'
               || ' AND claim_number IN (SELECT claim_number FROM claims.claim WHERE claimant_id IN (%s))', eligible),
        as_of, dry_run, 'NULLIFY', ARRAY['payee_name', 'bank_account_masked'], 'instruction_id');

    PERFORM compliance.purge(policy, 'claims.assignment',
        format('claimant_name IS NOT NULL'
               || ' AND claim_number IN (SELECT claim_number FROM claims.claim WHERE claimant_id IN (%s))', eligible),
        as_of, dry_run, 'NULLIFY', ARRAY['claimant_name'], 'request_id');

    claimants := compliance.purge(policy, 'claims.claimant',
        format('claimant_id IN (%s)', eligible),
        as_of, dry_run, 'NULLIFY',
        ARRAY['given_name', 'surname', 'tax_id', 'date_of_birth', 'phone', 'email',
              'street', 'city', 'postal_code', 'bank_account'],
        'claimant_id');

    IF NOT dry_run AND ids IS NOT NULL THEN
        UPDATE claims.claimant SET pii_purged_at = clock_timestamp() WHERE claimant_id = ANY (ids);
    END IF;
    RETURN claimants;
END
$$;

REVOKE ALL ON FUNCTION claims.purge_closed_claim_pii(date, int, boolean, char) FROM PUBLIC;
