CREATE SCHEMA IF NOT EXISTS {{ database }}.OPS COMMENT = {{ comment }};

CREATE VIEW IF NOT EXISTS {{ database }}.OPS.WORKLOAD_TABLE_FRESHNESS
COMMENT = {{ comment }} AS
WITH clock AS (
  SELECT CONVERT_TIMEZONE('UTC', CURRENT_TIMESTAMP())::TIMESTAMP_NTZ AS now_utc
), expected AS (
  SELECT DATEADD(minute, 10, DATE_TRUNC('hour', DATEADD(minute, -10, now_utc))) AS expected_scheduled_time
  FROM clock
), audit AS (
  SELECT MAX(REFRESHED_AT) AS newest_refresh FROM {{ database }}.APP.PIPELINE_REFRESH_RUNS
), freshness AS (
  SELECT 'ACCOUNT_STORAGE_USAGE' AS table_name, newest_refresh,
    'PIPELINE_REFRESH_RUNS.REFRESHED_AT (transaction-audit proxy)' AS freshness_source,
    (SELECT MAX(SNAPSHOT_DATE) FROM {{ database }}.APP.ACCOUNT_STORAGE_USAGE) AS newest_snapshot_date
  FROM audit
  UNION ALL
  SELECT 'PIPELINE_REFRESH_RUNS', newest_refresh, 'PIPELINE_REFRESH_RUNS.REFRESHED_AT (own timestamp)', NULL::DATE
  FROM audit
)
SELECT table_name, newest_refresh, freshness_source, newest_snapshot_date, expected_scheduled_time,
  newest_refresh IS NULL OR CONVERT_TIMEZONE('UTC', newest_refresh)::TIMESTAMP_NTZ < expected_scheduled_time AS stale
FROM freshness CROSS JOIN expected;

CREATE TABLE IF NOT EXISTS {{ database }}.OPS.DASHBOARD_FAULT_CONTROL (
  FAULT_ID VARCHAR NOT NULL,
  TARGET_TASK VARCHAR NOT NULL,
  TARGET_SCHEDULED_TIME TIMESTAMP_NTZ NOT NULL,
  MODE VARCHAR NOT NULL,
  PRIOR_PARAMETER_VALUE VARCHAR,
  PRIOR_PARAMETER_LEVEL VARCHAR,
  ARMED_AT TIMESTAMP_LTZ NOT NULL,
  ARMED_BY VARCHAR NOT NULL,
  FIRED BOOLEAN DEFAULT FALSE,
  OBSERVED_AT TIMESTAMP_LTZ,
  CLEARED_AT TIMESTAMP_LTZ,
  CLEARED_BY VARCHAR,
  RECOVERY_QUERY_IDS ARRAY
) COMMENT = {{ comment }};

CREATE PROCEDURE IF NOT EXISTS {{ database }}.OPS.ARM_DASHBOARD_FAULT()
RETURNS VARIANT LANGUAGE SQL COMMENT = {{ comment }} EXECUTE AS OWNER AS
$$
DECLARE
  invalid_state EXCEPTION (-20001, 'Dashboard task must be suspended with no active fault and no task-level timeout override');
  active_count INTEGER;
  task_state VARCHAR;
  prior_value VARCHAR;
  prior_level VARCHAR;
  fault_id VARCHAR DEFAULT UUID_STRING();
  next_run TIMESTAMP_NTZ;
BEGIN
  SELECT COUNT(*) INTO :active_count FROM {{ database }}.OPS.DASHBOARD_FAULT_CONTROL WHERE CLEARED_AT IS NULL;
  SHOW TASKS LIKE 'REFRESH_DOC_USAGE_DASHBOARD' IN SCHEMA {{ database }}.APP;
  SELECT "state" INTO :task_state FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()));
  SHOW PARAMETERS LIKE 'USER_TASK_TIMEOUT_MS' IN TASK {{ database }}.APP.REFRESH_DOC_USAGE_DASHBOARD;
  SELECT "value", "level" INTO :prior_value, :prior_level FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()));
  IF (active_count <> 0 OR task_state <> 'suspended' OR prior_level = 'TASK') THEN
    RAISE invalid_state;
  END IF;
  next_run := DATEADD(hour, 1, DATEADD(minute, 10,
    DATE_TRUNC('hour', DATEADD(minute, -10, CONVERT_TIMEZONE('UTC', CURRENT_TIMESTAMP())::TIMESTAMP_NTZ))));
  INSERT INTO {{ database }}.OPS.DASHBOARD_FAULT_CONTROL
    (FAULT_ID, TARGET_TASK, TARGET_SCHEDULED_TIME, MODE, PRIOR_PARAMETER_VALUE, PRIOR_PARAMETER_LEVEL, ARMED_AT, ARMED_BY)
  VALUES (:fault_id, '{{ database }}.APP.REFRESH_DOC_USAGE_DASHBOARD', :next_run,
    'user_task_timeout_ms', :prior_value, :prior_level, CURRENT_TIMESTAMP(), CURRENT_USER());
  ALTER TASK {{ database }}.APP.REFRESH_DOC_USAGE_DASHBOARD SET USER_TASK_TIMEOUT_MS = 1000;
  RETURN OBJECT_CONSTRUCT('fault_id', fault_id, 'target_scheduled_time', next_run, 'state', 'armed_task_still_suspended');
END;
$$;

CREATE PROCEDURE IF NOT EXISTS {{ database }}.OPS.RECOVER_DASHBOARD_TASK()
RETURNS VARIANT LANGUAGE SQL COMMENT = {{ comment }} EXECUTE AS OWNER AS
$$
DECLARE
  invalid_target EXCEPTION (-20002, 'Recovery requires exactly one active dashboard user_task_timeout_ms fault; other targets are forbidden');
  active_count INTEGER;
  invalid_count INTEGER;
  recovery_started_at TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP();
  suspend_id VARCHAR;
  unset_id VARCHAR;
  resume_id VARCHAR;
  execute_id VARCHAR;
  failed_runs INTEGER;
BEGIN
  SELECT COUNT(*), COUNT_IF(TARGET_TASK <> '{{ database }}.APP.REFRESH_DOC_USAGE_DASHBOARD' OR MODE <> 'user_task_timeout_ms')
    INTO :active_count, :invalid_count
    FROM {{ database }}.OPS.DASHBOARD_FAULT_CONTROL WHERE CLEARED_AT IS NULL;
  IF (active_count <> 1 OR invalid_count <> 0) THEN
    RAISE invalid_target;
  END IF;
  SELECT COUNT(*) INTO :failed_runs
  FROM TABLE({{ database }}.INFORMATION_SCHEMA.TASK_HISTORY(
    TASK_NAME => 'REFRESH_DOC_USAGE_DASHBOARD', SCHEDULED_TIME_RANGE_END => CURRENT_TIMESTAMP(), RESULT_LIMIT => 100)) h
  JOIN {{ database }}.OPS.DASHBOARD_FAULT_CONTROL f
    ON CONVERT_TIMEZONE('UTC', h.SCHEDULED_TIME)::TIMESTAMP_NTZ = f.TARGET_SCHEDULED_TIME
  WHERE f.CLEARED_AT IS NULL AND h.STATE = 'FAILED';
  ALTER TASK {{ database }}.APP.REFRESH_DOC_USAGE_DASHBOARD SUSPEND;
  suspend_id := SQLID;
  ALTER TASK {{ database }}.APP.REFRESH_DOC_USAGE_DASHBOARD UNSET USER_TASK_TIMEOUT_MS;
  unset_id := SQLID;
  ALTER TASK {{ database }}.APP.REFRESH_DOC_USAGE_DASHBOARD RESUME;
  resume_id := SQLID;
  UPDATE {{ database }}.OPS.DASHBOARD_FAULT_CONTROL
    SET CLEARED_AT = CURRENT_TIMESTAMP(), CLEARED_BY = CURRENT_USER(),
      FIRED = (:failed_runs > 0), OBSERVED_AT = CURRENT_TIMESTAMP(),
      RECOVERY_QUERY_IDS = ARRAY_CONSTRUCT(:suspend_id, :unset_id, :resume_id)
    WHERE CLEARED_AT IS NULL;
  EXECUTE TASK {{ database }}.APP.REFRESH_DOC_USAGE_DASHBOARD;
  execute_id := SQLID;
  UPDATE {{ database }}.OPS.DASHBOARD_FAULT_CONTROL
    SET RECOVERY_QUERY_IDS = ARRAY_APPEND(RECOVERY_QUERY_IDS, :execute_id)
    WHERE CLEARED_AT >= :recovery_started_at AND TARGET_TASK = '{{ database }}.APP.REFRESH_DOC_USAGE_DASHBOARD';
  RETURN OBJECT_CONSTRUCT('target_task', '{{ database }}.APP.REFRESH_DOC_USAGE_DASHBOARD',
    'recovery_started_at', recovery_started_at, 'timeout', 'unset', 'state', 'resumed',
    'query_ids', ARRAY_CONSTRUCT(suspend_id, unset_id, resume_id, execute_id));
END;
$$;

GRANT USAGE ON SCHEMA {{ database }}.OPS TO ROLE ROLE_CS_DOC_USAGE_DASHBOARD_FRESHNESS_RESPONDER;
GRANT SELECT ON VIEW {{ database }}.OPS.WORKLOAD_TABLE_FRESHNESS TO ROLE ROLE_CS_DOC_USAGE_DASHBOARD_FRESHNESS_RESPONDER;
GRANT SELECT ON TABLE {{ database }}.OPS.DASHBOARD_FAULT_CONTROL TO ROLE ROLE_CS_DOC_USAGE_DASHBOARD_FRESHNESS_RESPONDER;
GRANT USAGE ON PROCEDURE {{ database }}.OPS.RECOVER_DASHBOARD_TASK() TO ROLE ROLE_CS_DOC_USAGE_DASHBOARD_FRESHNESS_RESPONDER;
GRANT MONITOR ON TASK {{ database }}.APP.REFRESH_DOC_USAGE_DASHBOARD TO ROLE ROLE_CS_DOC_USAGE_DASHBOARD_FRESHNESS_RESPONDER;

ALTER DATABASE {{ database }} SET TAG {{ tag }} = {{ tag_value }};
ALTER WAREHOUSE {{ warehouse }} SET TAG {{ tag }} = {{ tag_value }};
ALTER TASK {{ database }}.APP.REFRESH_DOC_USAGE_DASHBOARD SET TAG {{ tag }} = {{ tag_value }};
ALTER STREAMLIT {{ database }}.APP.DOC_USAGE_DASHBOARD_APP SET TAG {{ tag }} = {{ tag_value }};
