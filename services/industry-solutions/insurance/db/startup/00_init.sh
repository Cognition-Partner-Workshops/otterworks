#!/bin/bash
# This directory (db/startup) is mounted into /opt/oracle/scripts/startup,
# which the Oracle Free image runs on every boot once the database is open.
# (The image ships a prebuilt DB, so /opt/oracle/scripts/setup never fires —
# startup is the reliable hook.) Only this orchestrator lives here: anything
# else in the mounted directory would be auto-executed as SYSDBA in the CDB
# root, which is the wrong container for our schemas.
#
# Idempotent and self-repairing: the skip is gated on the FIXTURE_META
# completion marker, written only after every script has run and all objects
# in both schemas compiled VALID. A boot that failed part-way leaves no
# marker, so the next boot re-runs the initialization.
#
# The image *sources* startup scripts, so all work happens in a subshell to
# keep `set -e` and any failure from tearing down the container entrypoint.
(
  set -euo pipefail

  SQL_DIR=/opt/oracle/scripts/insurance

  # Bearer token COMMISSION_PKG presents to commission-service. Written on every
  # boot so it always matches the token compose handed the service this run.
  store_caller_token() {
    local token="${COMMISSION_CALLER_TOKEN:-}"
    if [[ ! "${token}" =~ ^[A-Za-z0-9._~+/=-]*$ ]]; then
      echo "== COMMISSION_CALLER_TOKEN has characters outside [A-Za-z0-9._~+/=-]" >&2
      return 1
    fi
    [ -n "${token}" ] || echo "== COMMISSION_CALLER_TOKEN is empty: commission-service will refuse the delegate" >&2
    sqlplus -s "commission_pay/commission_pay@localhost:1521/FREEPDB1" <<SQL
WHENEVER SQLERROR EXIT SQL.SQLCODE
SET FEEDBACK OFF VERIFY OFF DEFINE OFF
CREATE TABLE IF NOT EXISTS service_caller_token (
    service VARCHAR2(64)  PRIMARY KEY,
    token   VARCHAR2(256)
);
MERGE INTO service_caller_token t
USING (SELECT 'commission-service' AS service, '${token}' AS token FROM dual) s
   ON (t.service = s.service)
 WHEN MATCHED THEN UPDATE SET t.token = s.token
 WHEN NOT MATCHED THEN INSERT (service, token) VALUES (s.service, s.token);
COMMIT;
EXIT;
SQL
  }

  marker=$(sqlplus -s "system/${ORACLE_PWD}@localhost:1521/FREEPDB1" <<'SQL'
WHENEVER SQLERROR EXIT SQL.SQLCODE
SET HEADING OFF FEEDBACK OFF PAGESIZE 0
SELECT COUNT(*) FROM all_tables
 WHERE owner = 'COMMISSION_PAY' AND table_name = 'FIXTURE_META';
EXIT;
SQL
  )
  marker=$(echo "${marker}" | tr -d '[:space:]')
  case "${marker}" in
    0) ;;
    1) echo "== insurance fixture already initialized, skipping"
       sqlplus -s "system/${ORACLE_PWD}@localhost:1521/FREEPDB1" @"${SQL_DIR}/setup/02_service_acl.sql"
       store_caller_token
       exit 0 ;;
    *) echo "== could not determine fixture state: ${marker}" >&2; exit 1 ;;
  esac

  run_sql() {
    local conn="$1" file="$2"
    echo "== ${file} (${conn%%/*})"
    sqlplus -s "${conn}@localhost:1521/FREEPDB1" @"${file}"
  }

  user_exists=$(sqlplus -s "system/${ORACLE_PWD}@localhost:1521/FREEPDB1" <<'SQL'
WHENEVER SQLERROR EXIT SQL.SQLCODE
SET HEADING OFF FEEDBACK OFF PAGESIZE 0
SELECT COUNT(*) FROM all_users WHERE username = 'COMMISSION_PAY';
EXIT;
SQL
  )
  if [ "$(echo "${user_exists}" | tr -d '[:space:]')" = "0" ]; then
    run_sql "system/${ORACLE_PWD}" "${SQL_DIR}/setup/01_users.sql"
  else
    echo "== users exist without completion marker: repairing a partial init"
    sqlplus -s "system/${ORACLE_PWD}@localhost:1521/FREEPDB1" <<'SQL'
WHENEVER SQLERROR EXIT SQL.SQLCODE
DROP USER commission_dw CASCADE;
DROP USER commission_pay CASCADE;
EXIT;
SQL
    run_sql "system/${ORACLE_PWD}" "${SQL_DIR}/setup/01_users.sql"
  fi

  # Network ACE for the delegate's callouts; must exist before the package body
  # that uses UTL_HTTP is compiled against it.
  run_sql "system/${ORACLE_PWD}" "${SQL_DIR}/setup/02_service_acl.sql"

  run_sql "commission_pay/commission_pay" "${SQL_DIR}/oltp/01_tables.sql"
  run_sql "commission_pay/commission_pay" "${SQL_DIR}/oltp/02_seed.sql"
  # The package body reads service_caller_token, so it must exist first.
  store_caller_token
  run_sql "commission_pay/commission_pay" "${SQL_DIR}/oltp/03_commission_pkg.sql"
  run_sql "commission_dw/commission_dw"   "${SQL_DIR}/olap/01_star_schema.sql"
  run_sql "commission_dw/commission_dw"   "${SQL_DIR}/olap/02_etl_pkg.sql"

  # PL/SQL compilation errors do not trip WHENEVER SQLERROR, so assert every
  # object in both schemas is VALID before declaring success.
  invalid=$(sqlplus -s "system/${ORACLE_PWD}@localhost:1521/FREEPDB1" <<'SQL'
WHENEVER SQLERROR EXIT SQL.SQLCODE
SET HEADING OFF FEEDBACK OFF PAGESIZE 0
SELECT COUNT(*) FROM all_objects
 WHERE owner IN ('COMMISSION_PAY', 'COMMISSION_DW') AND status <> 'VALID';
EXIT;
SQL
  )
  invalid=$(echo "${invalid}" | tr -d '[:space:]')
  if [ "${invalid}" != "0" ]; then
    echo "== ${invalid} invalid object(s) after initialization" >&2
    sqlplus -s "system/${ORACLE_PWD}@localhost:1521/FREEPDB1" <<'SQL'
SET HEADING OFF FEEDBACK OFF PAGESIZE 0
SELECT owner || '.' || object_name || ' (' || object_type || ')'
  FROM all_objects
 WHERE owner IN ('COMMISSION_PAY', 'COMMISSION_DW') AND status <> 'VALID';
EXIT;
SQL
    exit 1
  fi

  # Completion marker: written last; the health check and the skip guard
  # both key off it.
  sqlplus -s "commission_pay/commission_pay@localhost:1521/FREEPDB1" <<'SQL'
WHENEVER SQLERROR EXIT SQL.SQLCODE
CREATE TABLE fixture_meta (initialized_at TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL);
INSERT INTO fixture_meta (initialized_at) VALUES (SYSTIMESTAMP);
COMMIT;
EXIT;
SQL

  echo "== insurance fixture ready"
) || echo "== insurance fixture initialization FAILED (will retry on next boot; see errors above)"
