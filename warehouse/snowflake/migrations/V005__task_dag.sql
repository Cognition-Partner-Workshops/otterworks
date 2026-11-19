CREATE SCHEMA IF NOT EXISTS ORCH COMMENT='__RUN_TOKEN__ orchestration';

CREATE TABLE IF NOT EXISTS ORCH.STEP_RUN_LOG (
    STEP_RUN_LOG_ID BIGINT IDENTITY,
    STEP VARCHAR(80), TASK_NAME VARCHAR(255), RUN_ID VARCHAR(120),
    STARTED_AT TIMESTAMP_LTZ, ENDED_AT TIMESTAMP_LTZ
) COMMENT='__RUN_TOKEN__ placeholder step execution log';

CREATE OR REPLACE PROCEDURE ORCH.RUN_STEP(STEP VARCHAR)
RETURNS VARCHAR
LANGUAGE SQL
COMMENT='__RUN_TOKEN__ log-only step placeholder'
EXECUTE AS OWNER
AS
$$
DECLARE
    started TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP();
BEGIN
    INSERT INTO ORCH.STEP_RUN_LOG (STEP, TASK_NAME, RUN_ID, STARTED_AT, ENDED_AT)
    SELECT :STEP, SYSTEM$TASK_RUNTIME_INFO('CURRENT_TASK_NAME'),
           SYSTEM$GET_TASK_GRAPH_CONFIG('run_id')::VARCHAR, :started, CURRENT_TIMESTAMP();
    RETURN 'CONTINUE';
END;
$$;

CREATE OR REPLACE TASK ORCH.DAG_START
    WAREHOUSE=__RUN_DATABASE___TRANSFORM_WH
    SCHEDULE='USING CRON 0 3 * * * UTC'
    CONFIG='{"run_id":"scheduled"}'
    QUERY_TAG='{"workload":"transform","phase":"task_dag","commit":"{{ commit }}","run_id":"scheduled","run_token":"{{ run_token }}","executed_by":"{{ executed_by }}","built_with":"{{ built_with }}"}'
    COMMENT='__RUN_TOKEN__ log-only start'
AS CALL ORCH.RUN_STEP('start');

CREATE OR REPLACE TASK ORCH.DAG_WORKLET_A
    WAREHOUSE=__RUN_DATABASE___TRANSFORM_WH
    QUERY_TAG='{"workload":"transform","phase":"task_dag","commit":"{{ commit }}","run_id":"scheduled","run_token":"{{ run_token }}","executed_by":"{{ executed_by }}","built_with":"{{ built_with }}"}'
    COMMENT='__RUN_TOKEN__ log-only worklet_a'
    AFTER ORCH.DAG_START
AS CALL ORCH.RUN_STEP('worklet_a');

CREATE OR REPLACE TASK ORCH.DAG_SESSION_B
    WAREHOUSE=__RUN_DATABASE___TRANSFORM_WH
    QUERY_TAG='{"workload":"transform","phase":"task_dag","commit":"{{ commit }}","run_id":"scheduled","run_token":"{{ run_token }}","executed_by":"{{ executed_by }}","built_with":"{{ built_with }}"}'
    COMMENT='__RUN_TOKEN__ log-only session_b'
    AFTER ORCH.DAG_WORKLET_A
AS CALL ORCH.RUN_STEP('session_b');

CREATE OR REPLACE TASK ORCH.DAG_SESSION_C
    WAREHOUSE=__RUN_DATABASE___TRANSFORM_WH
    QUERY_TAG='{"workload":"transform","phase":"task_dag","commit":"{{ commit }}","run_id":"scheduled","run_token":"{{ run_token }}","executed_by":"{{ executed_by }}","built_with":"{{ built_with }}"}'
    COMMENT='__RUN_TOKEN__ log-only session_c'
    AFTER ORCH.DAG_WORKLET_A
AS CALL ORCH.RUN_STEP('session_c');

CREATE OR REPLACE TASK ORCH.DAG_SESSION_D
    WAREHOUSE=__RUN_DATABASE___TRANSFORM_WH
    QUERY_TAG='{"workload":"transform","phase":"task_dag","commit":"{{ commit }}","run_id":"scheduled","run_token":"{{ run_token }}","executed_by":"{{ executed_by }}","built_with":"{{ built_with }}"}'
    COMMENT='__RUN_TOKEN__ log-only session_d'
    AFTER ORCH.DAG_SESSION_B, ORCH.DAG_SESSION_C
AS EXECUTE IMMEDIATE $$ BEGIN
    CALL ORCH.RUN_STEP('session_d');
    CALL SYSTEM$SET_RETURN_VALUE('CONTINUE');
END; $$;

CREATE OR REPLACE TASK ORCH.DAG_DECISION
    WAREHOUSE=__RUN_DATABASE___TRANSFORM_WH
    QUERY_TAG='{"workload":"transform","phase":"task_dag","commit":"{{ commit }}","run_id":"scheduled","run_token":"{{ run_token }}","executed_by":"{{ executed_by }}","built_with":"{{ built_with }}"}'
    COMMENT='__RUN_TOKEN__ log-only decision'
    AFTER ORCH.DAG_SESSION_D
    WHEN SYSTEM$GET_PREDECESSOR_RETURN_VALUE('DAG_SESSION_D') = 'CONTINUE'
AS CALL ORCH.RUN_STEP('decision');
