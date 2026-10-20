-- Access tests: run as the database owner after sql/01..03.
\set ON_ERROR_STOP on
\o /dev/null
SET client_min_messages = notice;

CREATE FUNCTION pg_temp.check_case(name text, ok boolean, detail text DEFAULT '') RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
    IF ok THEN RAISE NOTICE 'PASS %', name; ELSE RAISE EXCEPTION 'FAIL % %', name, detail; END IF;
END $$;

-- S: seed reconciles with the corpus (16 FNOL + 14 payment + 10 assignment).
SELECT pg_temp.check_case('S1 16 claimants and 16 claims from 16 FNOL messages',
       (SELECT count(*) FROM claims.claimant) = 16 AND (SELECT count(*) FROM claims.claim) = 16);
SELECT pg_temp.check_case('S2 14 payments and 10 assignments attached to their claims',
       (SELECT count(*) FROM claims.payment) = 14 AND (SELECT count(*) FROM claims.assignment) = 10);
SELECT pg_temp.check_case('S3 all 40 corpus messages loaded exactly once',
       (SELECT count(DISTINCT source_message) FROM (
            SELECT source_message FROM claims.claim UNION ALL SELECT source_message FROM claims.payment
            UNION ALL SELECT source_message FROM claims.assignment) m) = 40);

-- P: the six PII columns.
CREATE TEMP TABLE plain AS
SELECT claimant_id, concat_ws(' ', given_name, surname) AS claimant_name, tax_id, date_of_birth::text AS date_of_birth,
       phone, concat_ws(', ', street, city, state || ' ' || postal_code) AS address, bank_account
  FROM claims.claimant;
GRANT SELECT ON plain TO claims_reader, claims_adjuster;

SET ROLE reader_demo;
CREATE TEMP TABLE seen_by_reader AS SELECT * FROM claims_api.claimant;
RESET ROLE;
SET ROLE adjuster_demo;
CREATE TEMP TABLE seen_by_adjuster AS SELECT * FROM claims_api.claimant;
RESET ROLE;

SELECT pg_temp.check_case('P1 claims_reader sees no PII value in clear (6 columns x 16 claimants)',
       (SELECT count(*) FROM plain p JOIN seen_by_reader r USING (claimant_id)
         WHERE r.claimant_name IS DISTINCT FROM p.claimant_name
           AND r.tax_id IS DISTINCT FROM p.tax_id
           AND r.date_of_birth IS DISTINCT FROM p.date_of_birth
           AND (p.phone IS NULL OR r.phone IS DISTINCT FROM p.phone)
           AND r.address IS DISTINCT FROM p.address
           AND r.bank_account IS DISTINCT FROM p.bank_account) = 16);
SELECT pg_temp.check_case('P2 claims_adjuster sees every PII value in clear',
       (SELECT count(*) FROM plain p JOIN seen_by_adjuster a USING (claimant_id)
         WHERE (a.claimant_name, a.tax_id, a.date_of_birth, a.phone, a.address, a.bank_account)
               IS NOT DISTINCT FROM (p.claimant_name, p.tax_id, p.date_of_birth, p.phone, p.address, p.bank_account)) = 16);
SELECT pg_temp.check_case('P3 reader masks keep only the last four of tax id, phone and account',
       (SELECT bool_and(right(r.tax_id, 4) = right(p.tax_id, 4) AND r.tax_id ~ '^X{3}-X{2}-[0-9]{4}$'
                        AND right(r.bank_account, 4) = right(p.bank_account, 4))
          FROM plain p JOIN seen_by_reader r USING (claimant_id)));

DO $$ BEGIN
    SET LOCAL ROLE reader_demo;
    PERFORM * FROM claims.claimant;
    RAISE EXCEPTION 'FAIL P4 reader read the base table';
EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'PASS P4 claims_reader cannot read claims.claimant directly';
END $$;
DO $$ BEGIN
    SET LOCAL ROLE reader_demo;
    PERFORM tax_id FROM claims.claimant;
    RAISE EXCEPTION 'FAIL P4b';
EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'PASS P4b claims_reader cannot read claims.claimant.tax_id by column';
END $$;
DO $$ BEGIN
    SET LOCAL ROLE adjuster_demo;
    UPDATE claims.claimant SET tax_id = NULL;
    RAISE EXCEPTION 'FAIL P5 adjuster wrote the base table';
EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'PASS P5 claims_adjuster cannot change claimant rows';
END $$;

SET ROLE reader_demo;
SELECT pg_temp.check_case('P6 reader: claimant payees and assignment names masked, vendor payees readable',
       (SELECT bool_and(payee_name !~ '^[A-Z][a-z]+ [A-Z][a-z]+$') FROM claims_api.payment WHERE payee_type = 'CL')
       AND (SELECT bool_and(payee_name ~ '[a-z]{2}') FROM claims_api.payment WHERE payee_type <> 'CL')
       AND (SELECT bool_and(claimant_name ~ '\*') FROM claims_api.assignment));
RESET ROLE;

SELECT pg_temp.check_case('P7 audit trail of claimant rows holds no PII value',
       NOT EXISTS (SELECT 1 FROM compliance.audit_row_change a JOIN plain p ON a.table_name = 'claims.claimant'
                    AND a.row_key = p.claimant_id::text
                    WHERE a.new_values::text LIKE '%' || p.tax_id || '%'
                       OR a.new_values::text LIKE '%' || p.bank_account || '%'
                       OR a.new_values::text LIKE '%' || split_part(p.claimant_name, ' ', 2) || '%'));

\echo 'ACCESS TESTS: ALL PASS'
