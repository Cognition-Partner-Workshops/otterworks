CREATE OR REPLACE TASK ${PREFIX}.OPS.UBW_MONTHLY_OVERAGE
    WAREHOUSE = ${PREFIX}_WH
    SCHEDULE = '${SCHEDULE}'
    COMMENT = 'Replaces SQL Agent job UBW Monthly Overage: usp_rate_overage, usp_build_mart_overage, usp_build_invoice_lines'
AS
    CALL ${PREFIX}.OPS.UBW_RUN_MODELS(ARRAY_CONSTRUCT('rate_overage', 'build_mart_overage', 'build_invoice_lines'));
