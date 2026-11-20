-- Read-only migration source user for OW_BILLING (local seeded fixture, PDB FREEPDB1).
-- Run inside the fixture container as SYSDBA: sed "s/&RO_PASSWORD/<password>/" <this file> | sqlplus -s / as sysdba
-- Ran: 2026-11-20 by the migration session on the local fixture (source is a seeded fixture, approved by the run owner).
WHENEVER SQLERROR EXIT SQL.SQLCODE
ALTER SESSION SET CONTAINER = FREEPDB1;
CREATE USER ow_billing_ro IDENTIFIED BY "&RO_PASSWORD";
GRANT CREATE SESSION TO ow_billing_ro;
BEGIN
  FOR t IN (SELECT table_name FROM all_tables WHERE owner = 'OW_BILLING') LOOP
    EXECUTE IMMEDIATE 'GRANT SELECT ON OW_BILLING."' || t.table_name || '" TO ow_billing_ro';
  END LOOP;
END;
/
EXIT;
