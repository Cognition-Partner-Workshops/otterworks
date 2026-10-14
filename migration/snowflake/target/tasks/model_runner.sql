CREATE OR REPLACE PROCEDURE ${PREFIX}.OPS.UBW_RUN_MODELS(MODEL_NAMES ARRAY)
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS OWNER
AS
$$$$
DECLARE
    model_name VARCHAR;
BEGIN
    FOR model_index IN 0 TO ARRAY_SIZE(MODEL_NAMES) - 1 DO
        model_name := GET(MODEL_NAMES, model_index)::STRING;
        CASE (model_name)
${MODEL_BRANCHES}
            ELSE
                INSERT INTO ${PREFIX}.OPS.ETL_RUN_LOG (
                    RUN_TOKEN, BUSINESS_DATE, JOB_NAME, STEP_NAME, STATUS,
                    ROW_COUNT, MESSAGE, STARTED_AT, COMPLETED_AT
                )
                VALUES (
                    '${RUN}', CURRENT_DATE(), 'UBW_TASK', :model_name, 'SKIPPED',
                    0, 'No published SQL file is available', CURRENT_TIMESTAMP(),
                    CURRENT_TIMESTAMP()
                );
        END CASE;
    END FOR;
    RETURN 'Model task complete';
END;
$$$$;
