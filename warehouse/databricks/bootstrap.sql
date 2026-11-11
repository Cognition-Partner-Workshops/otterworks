/* run=dbx-d1111 act=bootstrap step=after-schema consumer=platform */
CREATE SCHEMA IF NOT EXISTS cpw.dbx_d1111_after COMMENT 'run_token=dbx-d1111 expires=2026-11-24';
/* run=dbx-d1111 act=bootstrap step=parity-schema consumer=platform */
CREATE SCHEMA IF NOT EXISTS cpw.dbx_d1111_parity COMMENT 'run_token=dbx-d1111 expires=2026-11-24';
/* run=dbx-d1111 act=bootstrap step=control-schema consumer=platform */
CREATE SCHEMA IF NOT EXISTS cpw.dbx_d1111_control COMMENT 'run_token=dbx-d1111 expires=2026-11-24';
/* run=dbx-d1111 act=bootstrap step=control-table consumer=platform */
CREATE TABLE IF NOT EXISTS cpw.dbx_d1111_control.migration_control (
  source STRING, target STRING, subject_area STRING, wave INT, owner STRING,
  status STRING, parity_status STRING, idempotence_status STRING,
  evidence_statement_id STRING, updated_at TIMESTAMP
) USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24';
