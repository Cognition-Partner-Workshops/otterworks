CREATE OR REPLACE TASK ${PREFIX}.OPS.UBW_BUILD_FACTS
    WAREHOUSE = ${PREFIX}_WH
    AFTER ${PREFIX}.OPS.UBW_BUILD_DIMS
AS
    CALL ${PREFIX}.OPS.UBW_RUN_MODELS(ARRAY_CONSTRUCT(
        'rollup_storage_daily',
        'rollup_usage_events',
        'rollup_seats',
        'rollup_collab_daily',
        'rollup_audit',
        'rollup_document_status',
        'rollup_retention',
        'build_invoice_lines'
    ));
