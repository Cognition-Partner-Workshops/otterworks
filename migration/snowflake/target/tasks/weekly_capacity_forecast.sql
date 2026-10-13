CREATE OR REPLACE TASK ${PREFIX}.OPS.UBW_WEEKLY_CAPACITY_FORECAST
    WAREHOUSE = ${PREFIX}_WH
    SCHEDULE = '${SCHEDULE}'
    COMMENT = 'Replaces cron 15 6 * * 1 capacity_forecast_weekly.py: rebuild the input, then the Snowpark forecast'
AS
BEGIN
    CALL ${PREFIX}.OPS.UBW_RUN_MODELS(ARRAY_CONSTRUCT('build_capacity_forecast_input'));
    CALL ${PREFIX}.OPS.UBW_CAPACITY_FORECAST_WEEKLY(NULL);
END;
