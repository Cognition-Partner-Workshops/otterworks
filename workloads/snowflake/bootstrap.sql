-- Run by apply.sh before schemachange: schemachange keeps its change history in
-- {{ governance_db }}.SCHEMACHANGE and needs a running warehouse to read and write it,
-- so neither can be created by a versioned migration. Both statements are idempotent.
CREATE DATABASE IF NOT EXISTS {{ governance_db }}
  COMMENT = 'Run SFNFR_20261104: account-wide governance objects (DEVIN_CSID tag, masking policies, schemachange history)';

CREATE WAREHOUSE IF NOT EXISTS {{ migrations_wh }} WITH
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE
  COMMENT = 'Run SFNFR_20261104: runs schemachange only; no workload query runs here';
