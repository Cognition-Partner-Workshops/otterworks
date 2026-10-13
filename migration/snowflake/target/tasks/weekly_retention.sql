CREATE OR REPLACE TASK ${PREFIX}.OPS.UBW_WEEKLY_RETENTION
    WAREHOUSE = ${PREFIX}_WH
    SCHEDULE = '${SCHEDULE}'
    COMMENT = 'Replaces SQL Agent job UBW Weekly Retention: usp_rollup_retention, usp_build_mart_retention, usp_purge_expired @retention_days = 400'
AS
BEGIN
    CALL ${PREFIX}.OPS.UBW_RUN_MODELS(ARRAY_CONSTRUCT('rollup_retention', 'build_mart_retention'));
    -- usp_purge_expired: the run log and the usage and audit facts older than 400 days.
    DELETE FROM ${PREFIX}.OPS.ETL_RUN_LOG WHERE STARTED_AT < DATEADD(day, -400, CURRENT_DATE());
    DELETE FROM ${PREFIX}.MARTS.ROLLUP_USAGE_EVENTS WHERE BUSINESS_DATE < DATEADD(day, -400, CURRENT_DATE());
    DELETE FROM ${PREFIX}.MARTS.ROLLUP_AUDIT WHERE BUSINESS_DATE < DATEADD(day, -400, CURRENT_DATE());
    CALL ${PREFIX}.OPS.UBW_RUN_MODELS(ARRAY_CONSTRUCT('purge_expired'));
END;
