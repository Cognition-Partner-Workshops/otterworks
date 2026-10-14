CREATE OR REPLACE TASK ${PREFIX}.OPS.UBW_ROLLUP_STORAGE_DAILY
    WAREHOUSE = ${PREFIX}_WH
    TIMEZONE = 'America/New_York'
    COMMENT = 'Replaces SQL Agent job UBW Nightly Load step 21: EXEC dbo.usp_rollup_storage_daily'
    AFTER ${PREFIX}.OPS.UBW_BUILD_DIMS
AS
    CALL ${PREFIX}.OPS.UBW_RUN_MODELS(ARRAY_CONSTRUCT('rollup_storage_daily'));
