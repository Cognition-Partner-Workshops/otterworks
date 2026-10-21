#!/bin/bash
# Object grants for the migration login ($APP_USER, created by the image entrypoint before this runs).
# The same account seeds the estate, extracts, and purges - like the Db2 stand-in's db2inst1.
# Runs last (name order) as a new shell process inside the container on first start, after every
# ARCHIVE/MIGAUDIT object in 010-100 exists.
set -Eeuo pipefail
: "${APP_USER:?APP_USER must be set (the migration login)}"
sqlplus -s / as sysdba <<SQL
WHENEVER SQLERROR EXIT SQL.SQLCODE
ALTER SESSION SET CONTAINER = FREEPDB1;
-- Tables the engine extracts from and purges (CONTRACTS.md §9).
GRANT SELECT, INSERT, DELETE ON ARCHIVE.RETNPLCY TO ${APP_USER};
GRANT SELECT, INSERT, DELETE ON ARCHIVE.DOCARCH  TO ${APP_USER};
GRANT UPDATE (LEGAL_HOLD_FLAG) ON ARCHIVE.DOCARCH TO ${APP_USER};
GRANT SELECT, INSERT, DELETE ON ARCHIVE.FILEAUD  TO ${APP_USER};
GRANT SELECT, INSERT         ON MIGAUDIT.PURGE_AUDIT TO ${APP_USER};
GRANT SELECT                 ON MIGAUDIT.PURGE_LOG   TO ${APP_USER};
-- Legacy retention logic: readable and callable so it can be assessed and ported.
GRANT EXECUTE ON ARCHIVE.RETENTION_PKG      TO ${APP_USER};
GRANT SELECT  ON ARCHIVE.V_POLICY_LINEAGE   TO ${APP_USER};
GRANT SELECT  ON ARCHIVE.V_ELIGIBLE_DOCS    TO ${APP_USER};
GRANT SELECT  ON ARCHIVE.V_CLASS_TOTALS     TO ${APP_USER};
GRANT SELECT  ON ARCHIVE.V_LEGAL_HOLDS      TO ${APP_USER};
GRANT SELECT  ON ARCHIVE.CLASS_TOTAL_SNAP   TO ${APP_USER};
-- Catalog access for the assessment: DBA_OBJECTS/DBA_SOURCE/DBA_TRIGGERS/DBA_SCHEDULER_JOBS and
-- DBMS_METADATA.GET_DDL on objects of other schemas.
GRANT SELECT_CATALOG_ROLE TO ${APP_USER};
EXIT
SQL
