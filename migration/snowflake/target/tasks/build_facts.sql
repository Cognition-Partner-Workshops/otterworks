CREATE OR REPLACE TASK ${PREFIX}.OPS.UBW_BUILD_FACTS
    WAREHOUSE = ${PREFIX}_WH
    TIMEZONE = 'America/New_York'
    COMMENT = 'Also carries the steps of SQL Agent job UBW Hourly Audit (rollup_audit): audit data only changes with the nightly RAW load'
    AFTER ${PREFIX}.OPS.UBW_BUILD_DIMS
AS
    CALL ${PREFIX}.OPS.UBW_RUN_MODELS(ARRAY_CONSTRUCT(
        'rollup_usage_events',
        'rollup_seats',
        'rollup_collab_daily',
        'rollup_audit',
        'rollup_document_status',
        'rollup_retention',
        'build_invoice_lines'
    ));
