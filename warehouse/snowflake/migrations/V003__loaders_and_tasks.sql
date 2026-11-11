CREATE OR REPLACE PROCEDURE RAW_BILLING.LOAD_BILLING(LOAD_DATE VARCHAR)
RETURNS VARIANT
LANGUAGE SQL
COMMENT='sfx-d1110 copy loader'
EXECUTE AS CALLER
AS
$$
DECLARE
    summary ARRAY DEFAULT ARRAY_CONSTRUCT();
    tables ARRAY DEFAULT ARRAY_CONSTRUCT('CUSTOMER_ACCOUNT', 'PLAN_CATALOG', 'SUBSCRIPTION', 'INVOICE_HDR', 'INVOICE_LINE', 'PAYMENT', 'CREDIT_NOTE', 'TAX_RATE', 'USAGE_DAILY', 'BILLING_ADJ', 'GL_ACCOUNT', 'GL_JOURNAL_LINE');
    table_name VARCHAR;
    command VARCHAR;
    copied RESULTSET;
    loaded INTEGER;
BEGIN
    IF (LOAD_DATE IS NOT NULL AND NOT REGEXP_LIKE(LOAD_DATE, '^[0-9]{8}$')) THEN
        RETURN OBJECT_CONSTRUCT('error', 'LOAD_DATE must be yyyymmdd');
    END IF;
    FOR i IN 0 TO ARRAY_SIZE(tables) - 1 DO
        table_name := tables[i]::VARCHAR;
        command := 'COPY INTO RAW_BILLING.' || table_name ||
            ' FROM @LANDING.LANDING_STAGE/billing/' || table_name || '/' ||
            ' FILE_FORMAT=(FORMAT_NAME=LANDING.PSV_HEADER)' ||
            ' MATCH_BY_COLUMN_NAME=CASE_INSENSITIVE' ||
            ' INCLUDE_METADATA=(_SRC_FILE=METADATA$FILENAME,_LOADED_AT=METADATA$START_SCAN_TIME)' ||
            ' ON_ERROR=ABORT_STATEMENT';
        IF (LOAD_DATE IS NOT NULL) THEN
            command := command || ' FILES=(\'' || LOAD_DATE || '.psv\')';
        END IF;
        copied := (EXECUTE IMMEDIATE :command);
        SELECT COALESCE(SUM(TRY_TO_NUMBER(
            GET_IGNORE_CASE(OBJECT_CONSTRUCT(*), 'rows_loaded')::VARCHAR)), 0)
            INTO :loaded
            FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()));
        summary := ARRAY_APPEND(summary, OBJECT_CONSTRUCT('table', table_name, 'rows_loaded', loaded));
    END FOR;
    RETURN summary;
END;
$$;

CREATE OR REPLACE TASK RAW_BILLING.LOAD_BILLING_TASK
WAREHOUSE=SFX_D1110_LOAD_WH
SCHEDULE='USING CRON 0 2 * * * UTC'
QUERY_TAG='{"workload":"load","phase":"task","commit":"{{ commit }}","run_id":"{{ run_id }}","run_token":"{{ run_token }}","executed_by":"{{ executed_by }}","built_with":"{{ built_with }}"}'
COMMENT='sfx-d1110 suspended load task'
AS CALL RAW_BILLING.LOAD_BILLING(NULL);

CREATE OR REPLACE PROCEDURE RAW_DOCUMENTS.LOAD_DOCUMENTS(LOAD_DATE VARCHAR)
RETURNS VARIANT
LANGUAGE SQL
COMMENT='sfx-d1110 copy loader'
EXECUTE AS CALLER
AS
$$
DECLARE
    summary ARRAY DEFAULT ARRAY_CONSTRUCT();
    tables ARRAY DEFAULT ARRAY_CONSTRUCT('FOLDER', 'DOCUMENT', 'DOC_VERSION', 'DOC_SHARE', 'DOC_TAG', 'FILE_OBJECT', 'DOC_COMMENT', 'COLLAB_SESSION', 'STORAGE_USAGE_DAILY', 'SEARCH_INDEX_LOG');
    table_name VARCHAR;
    command VARCHAR;
    copied RESULTSET;
    loaded INTEGER;
BEGIN
    IF (LOAD_DATE IS NOT NULL AND NOT REGEXP_LIKE(LOAD_DATE, '^[0-9]{8}$')) THEN
        RETURN OBJECT_CONSTRUCT('error', 'LOAD_DATE must be yyyymmdd');
    END IF;
    FOR i IN 0 TO ARRAY_SIZE(tables) - 1 DO
        table_name := tables[i]::VARCHAR;
        command := 'COPY INTO RAW_DOCUMENTS.' || table_name ||
            ' FROM @LANDING.LANDING_STAGE/documents/' || table_name || '/' ||
            ' FILE_FORMAT=(FORMAT_NAME=LANDING.PSV_HEADER)' ||
            ' MATCH_BY_COLUMN_NAME=CASE_INSENSITIVE' ||
            ' INCLUDE_METADATA=(_SRC_FILE=METADATA$FILENAME,_LOADED_AT=METADATA$START_SCAN_TIME)' ||
            ' ON_ERROR=ABORT_STATEMENT';
        IF (LOAD_DATE IS NOT NULL) THEN
            command := command || ' FILES=(\'' || LOAD_DATE || '.psv\')';
        END IF;
        copied := (EXECUTE IMMEDIATE :command);
        SELECT COALESCE(SUM(TRY_TO_NUMBER(
            GET_IGNORE_CASE(OBJECT_CONSTRUCT(*), 'rows_loaded')::VARCHAR)), 0)
            INTO :loaded
            FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()));
        summary := ARRAY_APPEND(summary, OBJECT_CONSTRUCT('table', table_name, 'rows_loaded', loaded));
    END FOR;
    RETURN summary;
END;
$$;

CREATE OR REPLACE TASK RAW_DOCUMENTS.LOAD_DOCUMENTS_TASK
WAREHOUSE=SFX_D1110_LOAD_WH
SCHEDULE='USING CRON 0 2 * * * UTC'
QUERY_TAG='{"workload":"load","phase":"task","commit":"{{ commit }}","run_id":"{{ run_id }}","run_token":"{{ run_token }}","executed_by":"{{ executed_by }}","built_with":"{{ built_with }}"}'
COMMENT='sfx-d1110 suspended load task'
AS CALL RAW_DOCUMENTS.LOAD_DOCUMENTS(NULL);

CREATE OR REPLACE PROCEDURE RAW_USERS.LOAD_USERS(LOAD_DATE VARCHAR)
RETURNS VARIANT
LANGUAGE SQL
COMMENT='sfx-d1110 copy loader'
EXECUTE AS CALLER
AS
$$
DECLARE
    summary ARRAY DEFAULT ARRAY_CONSTRUCT();
    tables ARRAY DEFAULT ARRAY_CONSTRUCT('APP_USER', 'USER_PROFILE', 'TEAM', 'TEAM_MEMBER', 'ROLE_GRANT', 'SSO_IDENTITY', 'LOGIN_EVENT', 'USER_ACTIVITY_DAILY', 'USER_PREF', 'USER_STATUS_HIST');
    table_name VARCHAR;
    command VARCHAR;
    copied RESULTSET;
    loaded INTEGER;
BEGIN
    IF (LOAD_DATE IS NOT NULL AND NOT REGEXP_LIKE(LOAD_DATE, '^[0-9]{8}$')) THEN
        RETURN OBJECT_CONSTRUCT('error', 'LOAD_DATE must be yyyymmdd');
    END IF;
    FOR i IN 0 TO ARRAY_SIZE(tables) - 1 DO
        table_name := tables[i]::VARCHAR;
        command := 'COPY INTO RAW_USERS.' || table_name ||
            ' FROM @LANDING.LANDING_STAGE/users/' || table_name || '/' ||
            ' FILE_FORMAT=(FORMAT_NAME=LANDING.PSV_HEADER)' ||
            ' MATCH_BY_COLUMN_NAME=CASE_INSENSITIVE' ||
            ' INCLUDE_METADATA=(_SRC_FILE=METADATA$FILENAME,_LOADED_AT=METADATA$START_SCAN_TIME)' ||
            ' ON_ERROR=ABORT_STATEMENT';
        IF (LOAD_DATE IS NOT NULL) THEN
            command := command || ' FILES=(\'' || LOAD_DATE || '.psv\')';
        END IF;
        copied := (EXECUTE IMMEDIATE :command);
        SELECT COALESCE(SUM(TRY_TO_NUMBER(
            GET_IGNORE_CASE(OBJECT_CONSTRUCT(*), 'rows_loaded')::VARCHAR)), 0)
            INTO :loaded
            FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()));
        summary := ARRAY_APPEND(summary, OBJECT_CONSTRUCT('table', table_name, 'rows_loaded', loaded));
    END FOR;
    RETURN summary;
END;
$$;

CREATE OR REPLACE TASK RAW_USERS.LOAD_USERS_TASK
WAREHOUSE=SFX_D1110_LOAD_WH
SCHEDULE='USING CRON 0 2 * * * UTC'
QUERY_TAG='{"workload":"load","phase":"task","commit":"{{ commit }}","run_id":"{{ run_id }}","run_token":"{{ run_token }}","executed_by":"{{ executed_by }}","built_with":"{{ built_with }}"}'
COMMENT='sfx-d1110 suspended load task'
AS CALL RAW_USERS.LOAD_USERS(NULL);

CREATE OR REPLACE PROCEDURE RAW_AUDIT.LOAD_AUDIT(LOAD_DATE VARCHAR)
RETURNS VARIANT
LANGUAGE SQL
COMMENT='sfx-d1110 copy loader'
EXECUTE AS CALLER
AS
$$
DECLARE
    summary ARRAY DEFAULT ARRAY_CONSTRUCT();
    tables ARRAY DEFAULT ARRAY_CONSTRUCT('AUDIT_EVENT', 'AUDIT_EVENT_ARCHIVE', 'ACCESS_REVIEW', 'RETENTION_POLICY', 'DATA_EXPORT_REQ', 'COMPLIANCE_FLAG', 'SECURITY_ALERT', 'LEGAL_HOLD', 'AUDIT_DAILY_SUMMARY', 'AUDIT_RECON');
    table_name VARCHAR;
    command VARCHAR;
    copied RESULTSET;
    loaded INTEGER;
BEGIN
    IF (LOAD_DATE IS NOT NULL AND NOT REGEXP_LIKE(LOAD_DATE, '^[0-9]{8}$')) THEN
        RETURN OBJECT_CONSTRUCT('error', 'LOAD_DATE must be yyyymmdd');
    END IF;
    FOR i IN 0 TO ARRAY_SIZE(tables) - 1 DO
        table_name := tables[i]::VARCHAR;
        command := 'COPY INTO RAW_AUDIT.' || table_name ||
            ' FROM @LANDING.LANDING_STAGE/audit/' || table_name || '/' ||
            ' FILE_FORMAT=(FORMAT_NAME=LANDING.PSV_HEADER)' ||
            ' MATCH_BY_COLUMN_NAME=CASE_INSENSITIVE' ||
            ' INCLUDE_METADATA=(_SRC_FILE=METADATA$FILENAME,_LOADED_AT=METADATA$START_SCAN_TIME)' ||
            ' ON_ERROR=ABORT_STATEMENT';
        IF (LOAD_DATE IS NOT NULL) THEN
            command := command || ' FILES=(\'' || LOAD_DATE || '.psv\')';
        END IF;
        copied := (EXECUTE IMMEDIATE :command);
        SELECT COALESCE(SUM(TRY_TO_NUMBER(
            GET_IGNORE_CASE(OBJECT_CONSTRUCT(*), 'rows_loaded')::VARCHAR)), 0)
            INTO :loaded
            FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()));
        summary := ARRAY_APPEND(summary, OBJECT_CONSTRUCT('table', table_name, 'rows_loaded', loaded));
    END FOR;
    RETURN summary;
END;
$$;

CREATE OR REPLACE TASK RAW_AUDIT.LOAD_AUDIT_TASK
WAREHOUSE=SFX_D1110_LOAD_WH
SCHEDULE='USING CRON 0 2 * * * UTC'
QUERY_TAG='{"workload":"load","phase":"task","commit":"{{ commit }}","run_id":"{{ run_id }}","run_token":"{{ run_token }}","executed_by":"{{ executed_by }}","built_with":"{{ built_with }}"}'
COMMENT='sfx-d1110 suspended load task'
AS CALL RAW_AUDIT.LOAD_AUDIT(NULL);
