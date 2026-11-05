-- READER: reads workload outputs. ANALYST: reads landed inputs as well and is the only
-- role that sees customer email in clear (V1.5.0). ANALYST is deliberately kept out of the
-- SYSADMIN hierarchy so that admin roles do not inherit unmasked email; grant it to people.
CREATE ROLE IF NOT EXISTS {{ reader_role }}
  COMMENT = 'Run SFNFR_20261104: read-only access to workload outputs; customer email masked';
CREATE ROLE IF NOT EXISTS {{ analyst_role }}
  COMMENT = 'Run SFNFR_20261104: reads landed inputs and outputs; sees customer email unmasked';

GRANT ROLE {{ reader_role }} TO ROLE SYSADMIN;
