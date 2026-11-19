-- warehouse/teradata/macros/storage_totals.sql
-- Reads STORAGE_USAGE_DAILY, so its totals carry the open SET-table dedupe decision.
CREATE OR REPLACE PROCEDURE __RUN_DATABASE__.OPS.SFX_DOCUMENTS_M_STORAGE_TOTALS(P_START DATE, P_END DATE)
RETURNS TABLE (CUSTOMER_ID BIGINT, BYTES_USED BIGINT, OBJECT_COUNT BIGINT)
LANGUAGE SQL
COMMENT = 'run_token=__RUN_TOKEN__ expires=2026-11-24'
EXECUTE AS CALLER
AS
$$
BEGIN
    LET res RESULTSET := (
        SELECT CUSTOMER_ID, SUM(BYTES_USED) AS BYTES_USED, SUM(OBJECT_COUNT) AS OBJECT_COUNT
        FROM __RUN_DATABASE__.DOCUMENTS.STORAGE_USAGE_DAILY
        WHERE USAGE_DT >= :P_START AND USAGE_DT < :P_END
        GROUP BY CUSTOMER_ID
    );
    RETURN TABLE(res);
END;
$$;

-- warehouse/teradata/scripts/documents/10_storage_monthly.bteq
-- The USAGE_DAILY and INVOICE_LINE statements are the billing-boundary SQL in ../billing/15_storage.sql, which the
-- billing deploy runs; this procedure is the remaining storage_monthly.psv export of M_STORAGE_TOTALS.
CREATE OR REPLACE PROCEDURE __RUN_DATABASE__.OPS."10_STORAGE_MONTHLY"(P_DAY VARCHAR)
RETURNS VARCHAR
LANGUAGE SQL
COMMENT = 'run_token=__RUN_TOKEN__ expires=2026-11-24'
EXECUTE AS CALLER
AS
$$
DECLARE
    month_start DATE;
    month_end DATE;
BEGIN
    month_start := DATE_TRUNC(month, TO_DATE(P_DAY, 'YYYYMMDD'));
    month_end := DATEADD(month, 1, month_start);
    CALL __RUN_DATABASE__.OPS.SFX_DOCUMENTS_M_STORAGE_TOTALS(:month_start, :month_end);
    COPY INTO @__RUN_DATABASE__.LANDING.LANDING_STAGE/export/storage_monthly.psv
    FROM (SELECT * FROM TABLE(RESULT_SCAN(LAST_QUERY_ID())))
    FILE_FORMAT = (TYPE = CSV FIELD_DELIMITER = '|' COMPRESSION = NONE)
    SINGLE = TRUE OVERWRITE = TRUE;
    RETURN 'OK';
END;
$$;
