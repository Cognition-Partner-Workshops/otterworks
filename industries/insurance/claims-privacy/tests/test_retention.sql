-- Retention tests: run as the database owner after sql/01..04. Everything
-- runs in one transaction that is rolled back, so the seed is left as loaded.
\set ON_ERROR_STOP on
\o /dev/null
SET client_min_messages = notice;
BEGIN;

CREATE FUNCTION pg_temp.check_case(name text, ok boolean, detail text DEFAULT '') RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
    IF ok THEN RAISE NOTICE 'PASS %', name; ELSE RAISE EXCEPTION 'FAIL % %', name, detail; END IF;
END $$;

-- A  CLM-2026-100403  closed 2026-10-10, last payment 2026-10-02 (CL payee) -> clock 2026-10-10
-- B  CLM-2026-100407  closed 2026-10-01, last payment 2026-10-14 (CL payee) -> clock 2026-10-14
-- C  CLM-2026-100410  closed 2026-09-01, on legal hold                      -> never
-- D  CLM-2026-100413  reopened                                              -> never
-- the other twelve claims stay OPEN                                         -> never
UPDATE claims.claim SET status = 'CLOSED', closed_at = DATE '2026-10-10' WHERE claim_number = 'CLM-2026-100403';
UPDATE claims.claim SET status = 'CLOSED', closed_at = DATE '2026-10-01' WHERE claim_number = 'CLM-2026-100407';
UPDATE claims.claim SET status = 'CLOSED', closed_at = DATE '2026-09-01', legal_hold = true WHERE claim_number = 'CLM-2026-100410';
UPDATE claims.claim SET status = 'REOPENED' WHERE claim_number = 'CLM-2026-100413';

CREATE TEMP TABLE subj AS
SELECT c.claim_number, c.claimant_id, k.tax_id FROM claims.claim c JOIN claims.claimant k USING (claimant_id)
 WHERE c.claim_number IN ('CLM-2026-100403', 'CLM-2026-100407');
SELECT count(*) AS runs_before FROM compliance.retention_run \gset

SELECT pg_temp.check_case('C1 default period is seven years: A eligible exactly 7y after its clock',
       claims.purge_closed_claim_pii(DATE '2033-10-10') = 1);
SELECT pg_temp.check_case('C2 one day earlier nothing is eligible',
       claims.purge_closed_claim_pii(DATE '2033-10-09') = 0);
SELECT pg_temp.check_case('C3 a payment after closure restarts the clock (B waits until 2033-10-14)',
       claims.purge_closed_claim_pii(DATE '2033-10-13') = 1 AND claims.purge_closed_claim_pii(DATE '2033-10-14') = 2);
SELECT pg_temp.check_case('C4 legal hold, reopened and open claims never qualify',
       claims.purge_closed_claim_pii(DATE '2099-01-01') = 2);
SELECT pg_temp.check_case('C5 the period is a parameter (3 years -> both eligible by 2030)',
       claims.purge_closed_claim_pii(DATE '2030-01-01', 3) = 2
       AND claims.purge_closed_claim_pii(DATE '2030-01-01', 7) = 0);
SELECT pg_temp.check_case('C6 loss_state narrows the run to one state',
       claims.purge_closed_claim_pii(DATE '2099-01-01', 7, true, 'ZZ') = 0);
SELECT pg_temp.check_case('C7 dry runs change nothing and each writes three retention_run rows',
       (SELECT bool_and(k.tax_id = s.tax_id AND k.pii_purged_at IS NULL)
          FROM subj s JOIN claims.claimant k USING (claimant_id))
       AND (SELECT count(*) FROM compliance.retention_run) = :runs_before + 3 * 8
       AND (SELECT bool_and(dry_run AND rows_purged = 0)
              FROM (SELECT * FROM compliance.retention_run ORDER BY run_id OFFSET :runs_before) r));

DO $$ BEGIN
    PERFORM claims.purge_closed_claim_pii(DATE '2033-10-10', 0);
    RAISE EXCEPTION 'no error';
EXCEPTION WHEN raise_exception THEN
    IF SQLERRM = 'no error' THEN RAISE EXCEPTION 'FAIL C8 zero-year retention accepted'; END IF;
END $$;
SELECT pg_temp.check_case('C8 retention below one year refused', true);

SELECT claims.purge_closed_claim_pii(DATE '2033-10-10', 7, false) AS purged \gset
SELECT pg_temp.check_case('C9 real run clears claimant A PII and stamps pii_purged_at',
       :purged = 1 AND (SELECT given_name IS NULL AND surname IS NULL AND tax_id IS NULL AND date_of_birth IS NULL
                               AND phone IS NULL AND email IS NULL AND street IS NULL AND bank_account IS NULL
                               AND postal_code IS NULL AND pii_purged_at IS NOT NULL
                          FROM claims.claimant WHERE claimant_id = (SELECT claimant_id FROM subj WHERE claim_number = 'CLM-2026-100403')));
SELECT pg_temp.check_case('C10 claimant payee and assignment names on claim A cleared',
       (SELECT bool_and(payee_name IS NULL AND bank_account_masked IS NULL) FROM claims.payment
         WHERE claim_number = 'CLM-2026-100403' AND payee_type = 'CL')
       AND (SELECT bool_and(claimant_name IS NULL) FROM claims.assignment WHERE claim_number = 'CLM-2026-100403'));
SELECT pg_temp.check_case('C11 claim, payment amounts and B are untouched',
       (SELECT estimated_loss IS NOT NULL AND loss_date IS NOT NULL FROM claims.claim WHERE claim_number = 'CLM-2026-100403')
       AND (SELECT count(*) FROM claims.payment_line l JOIN claims.payment p USING (instruction_id)
             WHERE p.claim_number = 'CLM-2026-100403') > 0
       AND (SELECT k.tax_id = s.tax_id FROM subj s JOIN claims.claimant k USING (claimant_id)
             WHERE s.claim_number = 'CLM-2026-100407'));
SELECT pg_temp.check_case('C12 real run logged with the purged keys',
       (SELECT count(*) FROM compliance.retention_run
         WHERE NOT dry_run AND table_name = 'claims.claimant' AND rows_purged = 1
           AND row_keys = ARRAY[(SELECT claimant_id::text FROM subj WHERE claim_number = 'CLM-2026-100403')]) = 1);
SELECT pg_temp.check_case('C13 a second run finds nothing left to purge for A',
       claims.purge_closed_claim_pii(DATE '2033-10-10', 7, false) = 0);
SELECT pg_temp.check_case('C14 the audit trail of the purge holds no PII',
       (SELECT count(*) FROM compliance.audit_row_change
         WHERE table_name = 'claims.claimant' AND operation = 'UPDATE'
           AND row_key = (SELECT claimant_id::text FROM subj WHERE claim_number = 'CLM-2026-100403')
           AND old_values->>'tax_id' = '[redacted]') >= 1
       AND NOT EXISTS (SELECT 1 FROM compliance.audit_row_change a, subj s
                        WHERE a.old_values::text LIKE '%' || s.tax_id || '%'));

SELECT claimant_id AS a_id FROM subj WHERE claim_number = 'CLM-2026-100403' \gset
SET ROLE adjuster_demo;
SELECT pg_temp.check_case('C15 adjusters see NULL where purged PII was',
       (SELECT tax_id IS NULL AND date_of_birth IS NULL FROM claims_api.claimant WHERE claimant_id = :a_id));
RESET ROLE;

ROLLBACK;
\o
\echo 'RETENTION TESTS: ALL PASS'
