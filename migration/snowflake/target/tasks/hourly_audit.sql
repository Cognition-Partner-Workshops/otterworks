CREATE OR REPLACE TASK ${PREFIX}.OPS.UBW_HOURLY_AUDIT
    WAREHOUSE = ${PREFIX}_WH
    SCHEDULE = '${SCHEDULE}'
    COMMENT = 'Replaces SQL Agent job UBW Hourly Audit: usp_rollup_audit, usp_build_mart_audit'
AS
    CALL ${PREFIX}.OPS.UBW_RUN_MODELS(ARRAY_CONSTRUCT('rollup_audit', 'build_mart_audit'));
