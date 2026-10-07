-- Read-only source principal for the mmp_rt_b3_oracle migration run
-- (plan decision d-source-principal = ro-user). Run as SYSTEM against FREEPDB1
-- inside the fixture container; idempotent. Grants SELECT on every OW_BILLING
-- table and view plus SELECT_CATALOG_ROLE so the census can read ALL_*/DBA_*
-- dictionary views (tables, columns, constraints, PL/SQL source, jobs).
-- The password is a fixture default, not a secret.
WHENEVER SQLERROR EXIT SQL.SQLCODE
SET SERVEROUTPUT ON

DECLARE
  n NUMBER;
BEGIN
  SELECT COUNT(*) INTO n FROM all_users WHERE username = 'OW_BILLING_RO';
  IF n = 0 THEN
    EXECUTE IMMEDIATE 'CREATE USER ow_billing_ro IDENTIFIED BY ow_billing_ro';
  END IF;
  EXECUTE IMMEDIATE 'GRANT CREATE SESSION, SELECT_CATALOG_ROLE TO ow_billing_ro';
  FOR o IN (SELECT object_name, object_type FROM all_objects
             WHERE owner = 'OW_BILLING'
               AND object_type IN ('TABLE', 'VIEW')
             ORDER BY object_name) LOOP
    EXECUTE IMMEDIATE 'GRANT SELECT ON ow_billing.' || o.object_name || ' TO ow_billing_ro';
  END LOOP;
  DBMS_OUTPUT.PUT_LINE('ow_billing_ro ready');
END;
/
-- UNT7-14 (finding F60): the recon harness queries bare table names and has no
-- schema option, so a principal other than the owner sees ORA-00942 on every
-- table. Default the ro session's name resolution to OW_BILLING without granting
-- anything: a logon trigger in the ro user's own schema (no new privilege).
CREATE OR REPLACE TRIGGER ow_billing_ro.trg_mmp_rt_ro_logon
  AFTER LOGON ON ow_billing_ro.SCHEMA
BEGIN
  EXECUTE IMMEDIATE 'ALTER SESSION SET CURRENT_SCHEMA = OW_BILLING';
END;
/
EXIT;
