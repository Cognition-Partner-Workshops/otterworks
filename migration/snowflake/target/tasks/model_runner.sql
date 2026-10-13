CREATE OR REPLACE PROCEDURE ${PREFIX}.OPS.UBW_RUN_MODELS(MODEL_NAMES ARRAY)
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS OWNER
AS
$$$$
DECLARE
    model_name VARCHAR;
BEGIN
    FOR model_record IN (
        SELECT VALUE::STRING AS MODEL_NAME
        FROM TABLE(FLATTEN(INPUT => MODEL_NAMES))
    ) DO
        model_name := model_record.MODEL_NAME;
        CASE (model_name)
${MODEL_BRANCHES}
            ELSE
                INSERT INTO ${PREFIX}.OPS.ETL_RUN_LOG (
                    RUN_TOKEN, BUSINESS_DATE, JOB_NAME, STEP_NAME, STATUS,
                    ROW_COUNT, MESSAGE, STARTED_AT, COMPLETED_AT
                )
                VALUES (
                    '${RUN}', CURRENT_DATE(), 'UBW_TASK', model_name, 'SKIPPED',
                    0, 'No published SQL file is available', CURRENT_TIMESTAMP(),
                    CURRENT_TIMESTAMP()
                );
        END CASE;
    END FOR;
    RETURN 'Model task complete';
END;
$$$$;
