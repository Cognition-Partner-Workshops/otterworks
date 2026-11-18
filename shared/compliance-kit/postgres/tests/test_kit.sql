-- compliance-kit / PostgreSQL self-test. Run on an empty PostgreSQL 16
-- database after 01..03 (shared/compliance-kit/run-pg-tests.sh does both).
\set ON_ERROR_STOP on
SET client_min_messages = notice;
\o /dev/null

CREATE SCHEMA kit_demo;
CREATE TABLE kit_demo.person (id int PRIMARY KEY, name text, tax_id text, closed_on date);
CREATE TRIGGER trg_aud_person AFTER INSERT OR UPDATE OR DELETE ON kit_demo.person
    FOR EACH ROW EXECUTE FUNCTION compliance.audit_row_change_trg('id', 'name', 'tax_id');

CREATE FUNCTION pg_temp.check_case(name text, ok boolean, detail text DEFAULT '') RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
    IF ok THEN RAISE NOTICE 'PASS %', name;
    ELSE RAISE EXCEPTION 'FAIL % %', name, detail; END IF;
END $$;

-- M: masking library.
SELECT pg_temp.check_case('M1 mask_keep_last matches PiiMaskingComponent.Mask',
       compliance.mask_keep_last('123-45-6789', 4) = 'XXX-XX-6789'
       AND compliance.mask_keep_last('AB12', 4) = 'AB12'
       AND compliance.mask_keep_last('', 4) = '' AND compliance.mask_keep_last(NULL, 4) IS NULL);
SELECT pg_temp.check_case('M2 mask_name keeps initials only',
       compliance.mask_name('Imogen Castellanos') = 'I***** C**********', compliance.mask_name('Imogen Castellanos'));
SELECT pg_temp.check_case('M3 phone, account, date, street masks',
       compliance.mask_phone('+1-401-555-0187') = '+X-XXX-XXX-0187'
       AND compliance.mask_account('021000021-000123451000') = 'XXXXXXXXX-XXXXXXXX1000'
       AND compliance.mask_date(DATE '1980-02-29') = 'XXXX-XX-XX'
       AND compliance.mask_street('14 Thames St') = '[redacted]');

-- A: audit trigger.
INSERT INTO kit_demo.person VALUES (1, 'Ada Byron', '123-45-6789', NULL), (2, 'Alan Turing', '987-65-4321', DATE '2015-01-31');
BEGIN;
SET LOCAL compliance.actor = 'adjuster.kim';
UPDATE kit_demo.person SET closed_on = DATE '2016-06-30' WHERE id = 1;
COMMIT;
UPDATE kit_demo.person SET name = 'Ada Lovelace' WHERE id = 1;
SELECT pg_temp.check_case('A1 every change recorded with actor or session user and time',
       (SELECT count(*) FROM compliance.audit_row_change WHERE row_key = '1') = 3
       AND (SELECT app_actor FROM compliance.audit_row_change WHERE row_key = '1' AND operation = 'UPDATE' ORDER BY change_id LIMIT 1) = 'adjuster.kim'
       AND (SELECT app_actor IS NULL AND db_user = session_user FROM compliance.audit_row_change WHERE row_key = '1' ORDER BY change_id DESC LIMIT 1));
SELECT pg_temp.check_case('A2 redacted columns never stored in the trail',
       NOT EXISTS (SELECT 1 FROM compliance.audit_row_change
                    WHERE coalesce(old_values::text, '') || coalesce(new_values::text, '') ~ '(Ada|Alan|6789|4321)'));
DO $$ BEGIN
    UPDATE compliance.audit_row_change SET app_actor = 'forged';
    RAISE EXCEPTION 'FAIL A3 update on trail allowed';
EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'PASS A3 audit trail refuses UPDATE';
END $$;
DO $$ BEGIN
    DELETE FROM compliance.audit_row_change;
    RAISE EXCEPTION 'FAIL A3b delete on trail allowed';
EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'PASS A3b audit trail refuses DELETE outside compliance.purge';
END $$;

-- R: retention purge.
SELECT pg_temp.check_case('R1 dry run counts and changes nothing',
       compliance.purge('demo-pii', 'kit_demo.person', 'closed_on <= $1 - interval ''7 years''', DATE '2023-06-30',
                        dry_run => true, action => 'NULLIFY', columns => ARRAY['name', 'tax_id'], key_column => 'id') = 2
       AND (SELECT count(*) FROM kit_demo.person WHERE name IS NOT NULL) = 2);
SELECT pg_temp.check_case('R2 boundary: closed exactly seven years before as_of is eligible, a day later is not',
       compliance.purge('demo-pii', 'kit_demo.person', 'closed_on <= $1 - interval ''7 years''', DATE '2023-06-29',
                        dry_run => true, action => 'NULLIFY', columns => ARRAY['name', 'tax_id'], key_column => 'id') = 1);
-- A purge and the checks on its effect run as separate statements: a query
-- does not see changes made by a function it calls.
SELECT compliance.purge('demo-pii', 'kit_demo.person', 'closed_on <= $1 - interval ''7 years''', DATE '2023-06-29',
                        dry_run => false, action => 'NULLIFY', columns => ARRAY['name', 'tax_id'], key_column => 'id') AS r3 \gset
SELECT pg_temp.check_case('R3 real run nullifies only matched rows, keeps the record',
       :r3 = 1
       AND (SELECT name IS NULL AND tax_id IS NULL FROM kit_demo.person WHERE id = 2)
       AND (SELECT name = 'Ada Lovelace' FROM kit_demo.person WHERE id = 1));
SELECT pg_temp.check_case('R4 every run leaves a retention_run row with the keys it matched',
       (SELECT count(*) FROM compliance.retention_run) = 3
       AND (SELECT row_keys = ARRAY['2'] AND rows_purged = 1 AND NOT dry_run FROM compliance.retention_run ORDER BY run_id DESC LIMIT 1));
SELECT compliance.purge('demo-trail', 'compliance.audit_row_change', 'table_name = ''kit_demo.person'' AND row_key = ''2''',
                        DATE '2030-01-01', dry_run => false) AS r5 \gset
SELECT pg_temp.check_case('R5 compliance.purge may delete from the protected trail',
       :r5 > 0
       AND NOT EXISTS (SELECT 1 FROM compliance.audit_row_change WHERE row_key = '2'));
DO $$ BEGIN
    DELETE FROM compliance.audit_row_change;
    RAISE EXCEPTION 'FAIL R6 purge gate left open';
EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'PASS R6 gate closes again after the purge';
END $$;

\echo 'KIT TESTS: ALL PASS'
