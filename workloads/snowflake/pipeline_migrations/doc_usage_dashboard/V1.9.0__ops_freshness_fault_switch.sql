CREATE SCHEMA IF NOT EXISTS {{ ops_schema_doc_usage_dashboard }}
 COMMENT = 'doc_usage_dashboard operations: refresh log, freshness, drill fault switch';

CREATE TABLE IF NOT EXISTS {{ ops_schema_doc_usage_dashboard }}.REFRESH_LOG (
 TASK_NAME VARCHAR,
 TABLE_NAME VARCHAR COMMENT 'Fully qualified table name',
 REFRESHED_AT TIMESTAMP_TZ,
 QUERY_ID VARCHAR
);

CREATE TABLE IF NOT EXISTS {{ ops_schema_doc_usage_dashboard }}.REFRESH_TABLES (
 TABLE_NAME VARCHAR,
 TASK_NAME VARCHAR,
 MAX_AGE_MINUTES NUMBER
);

MERGE INTO {{ ops_schema_doc_usage_dashboard }}.REFRESH_TABLES AS target
USING (
 SELECT '{{ db_doc_usage_dashboard }}.RAW.ADMIN_STORAGE_QUOTAS' AS TABLE_NAME,
        '{{ db_doc_usage_dashboard }}.ANALYTICS.REFRESH_DOC_USAGE_DASHBOARD' AS TASK_NAME,
        90 AS MAX_AGE_MINUTES
 UNION ALL
 SELECT '{{ db_doc_usage_dashboard }}.RAW.ADMIN_ADMIN_USERS',
        '{{ db_doc_usage_dashboard }}.ANALYTICS.REFRESH_DOC_USAGE_DASHBOARD',
        90
 UNION ALL
 SELECT '{{ db_doc_usage_dashboard }}.RAW.DOCUMENT_DOCUMENTS',
        '{{ db_doc_usage_dashboard }}.ANALYTICS.REFRESH_DOC_USAGE_DASHBOARD',
        90
 UNION ALL
 SELECT '{{ db_doc_usage_dashboard }}.ANALYTICS.DOC_USAGE_DASHBOARD_SNAPSHOT',
        '{{ db_doc_usage_dashboard }}.ANALYTICS.REFRESH_DOC_USAGE_DASHBOARD',
        90
) AS source
ON target.TABLE_NAME = source.TABLE_NAME
WHEN MATCHED THEN UPDATE SET
 TASK_NAME = source.TASK_NAME,
 MAX_AGE_MINUTES = source.MAX_AGE_MINUTES
WHEN NOT MATCHED THEN INSERT (TABLE_NAME, TASK_NAME, MAX_AGE_MINUTES)
 VALUES (source.TABLE_NAME, source.TASK_NAME, source.MAX_AGE_MINUTES);

CREATE TABLE IF NOT EXISTS {{ ops_schema_doc_usage_dashboard }}.FAULT_SWITCH (
 SWITCH_NAME VARCHAR PRIMARY KEY,
 ARMED BOOLEAN,
 NOTE VARCHAR,
 CHANGED_AT TIMESTAMP_TZ,
 CHANGED_BY VARCHAR COMMENT 'Devin session URL or Snowflake user'
);

MERGE INTO {{ ops_schema_doc_usage_dashboard }}.FAULT_SWITCH AS target
USING (
 SELECT 'REFRESH_DOC_USAGE_DASHBOARD' AS SWITCH_NAME,
        FALSE AS ARMED,
        CURRENT_TIMESTAMP() AS CHANGED_AT,
        CURRENT_USER() AS CHANGED_BY
) AS source
ON target.SWITCH_NAME = source.SWITCH_NAME
WHEN NOT MATCHED THEN INSERT (SWITCH_NAME, ARMED, NOTE, CHANGED_AT, CHANGED_BY)
 VALUES (source.SWITCH_NAME, source.ARMED, NULL, source.CHANGED_AT, source.CHANGED_BY);

CREATE OR REPLACE VIEW {{ ops_schema_doc_usage_dashboard }}.WORKLOAD_FRESHNESS AS
WITH latest_refresh AS (
 SELECT TABLE_NAME, MAX(REFRESHED_AT) AS LAST_REFRESHED_AT
 FROM {{ ops_schema_doc_usage_dashboard }}.REFRESH_LOG
 GROUP BY TABLE_NAME
), freshness AS (
 SELECT expected.TABLE_NAME,
        expected.TASK_NAME,
        latest.LAST_REFRESHED_AT,
        DATEDIFF('second', latest.LAST_REFRESHED_AT, CURRENT_TIMESTAMP()) / 60.0 AS AGE_MINUTES,
        expected.MAX_AGE_MINUTES,
        CURRENT_TIMESTAMP() AS CHECKED_AT
 FROM {{ ops_schema_doc_usage_dashboard }}.REFRESH_TABLES AS expected
 LEFT JOIN latest_refresh AS latest ON latest.TABLE_NAME = expected.TABLE_NAME
)
SELECT TABLE_NAME,
       TASK_NAME,
       LAST_REFRESHED_AT,
       AGE_MINUTES,
       MAX_AGE_MINUTES,
       LAST_REFRESHED_AT IS NULL OR AGE_MINUTES > MAX_AGE_MINUTES AS IS_STALE,
       CHECKED_AT
FROM freshness;

CREATE OR REPLACE PROCEDURE {{ ops_schema_doc_usage_dashboard }}.CHECK_FAULT_SWITCH(SWITCH_NAME VARCHAR)
 RETURNS VARCHAR
 LANGUAGE SQL
 EXECUTE AS OWNER
 AS
$$
DECLARE
  fault_armed EXCEPTION (-20042, 'OPS.FAULT_SWITCH REFRESH_DOC_USAGE_DASHBOARD is armed: refresh aborted before LOAD_RAW (incident drill)');
  is_armed BOOLEAN;
BEGIN
  SELECT ARMED INTO :is_armed
  FROM {{ ops_schema_doc_usage_dashboard }}.FAULT_SWITCH
  WHERE SWITCH_NAME = :SWITCH_NAME;
  IF (COALESCE(is_armed, FALSE)) THEN
    RAISE fault_armed;
  END IF;
  RETURN 'fault switch disarmed';
END;
$$;

CREATE OR REPLACE PROCEDURE {{ ops_schema_doc_usage_dashboard }}.RECORD_REFRESH(TASK_NAME VARCHAR)
 RETURNS VARCHAR
 LANGUAGE SQL
 EXECUTE AS OWNER
 AS
$$
BEGIN
  INSERT INTO {{ ops_schema_doc_usage_dashboard }}.REFRESH_LOG (TASK_NAME, TABLE_NAME, REFRESHED_AT)
  SELECT :TASK_NAME, TABLE_NAME, CURRENT_TIMESTAMP()
  FROM {{ ops_schema_doc_usage_dashboard }}.REFRESH_TABLES
  WHERE TASK_NAME = :TASK_NAME;
  RETURN 'refresh recorded';
END;
$$;

GRANT USAGE ON SCHEMA {{ ops_schema_doc_usage_dashboard }} TO ROLE {{ analyst_role }};
GRANT SELECT ON VIEW {{ ops_schema_doc_usage_dashboard }}.WORKLOAD_FRESHNESS TO ROLE {{ analyst_role }};
GRANT SELECT ON TABLE {{ ops_schema_doc_usage_dashboard }}.REFRESH_LOG TO ROLE {{ analyst_role }};
GRANT SELECT ON TABLE {{ ops_schema_doc_usage_dashboard }}.REFRESH_TABLES TO ROLE {{ analyst_role }};
GRANT SELECT ON TABLE {{ ops_schema_doc_usage_dashboard }}.FAULT_SWITCH TO ROLE {{ analyst_role }};
