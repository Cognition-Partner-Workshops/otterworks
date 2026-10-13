CREATE OR REPLACE TASK ${PREFIX}.OPS.UBW_BUILD_MARTS
    WAREHOUSE = ${PREFIX}_WH
    AFTER ${PREFIX}.OPS.UBW_BUILD_FACTS
AS
    CALL ${PREFIX}.OPS.UBW_RUN_MODELS(ARRAY_CONSTRUCT(
        'rate_overage',
        'apply_plan_limits',
        'build_capacity_forecast_input',
        'build_mart_tenant_usage',
        'build_mart_plan_seat_summary',
        'build_mart_overage',
        'build_mart_retention',
        'build_mart_audit'
    ));
