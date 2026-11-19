"""Render the log-only task graph from its step map."""

import sys as _run_sys
from pathlib import Path as _RunPath
_run_sys.path.insert(0, str(_RunPath(__file__).resolve().parents[3]))
from warehouse.run_config import render as _run_render

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'migrations/V005__task_dag.sql'


def render():
    steps = yaml.safe_load(_run_render((ROOT / 'task_dag.yml').read_text()))['steps']
    sql = _run_render("""CREATE SCHEMA IF NOT EXISTS ORCH COMMENT='__RUN_TOKEN__ orchestration';

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

""")
    tag = ('{\"workload\":\"transform\",\"phase\":\"task_dag\",\"commit\":\"{{ commit }}\",'
           '\"run_id\":\"scheduled\",\"run_token\":\"{{ run_token }}\",'
           '\"executed_by\":\"{{ executed_by }}\",\"built_with\":\"{{ built_with }}\"}')
    for name, step in steps.items():
        sql += _run_render(f"CREATE OR REPLACE TASK ORCH.{step['task']}\n    WAREHOUSE=__RUN_DATABASE___TRANSFORM_WH\n")
        if not step['after']:
            sql += "    SCHEDULE='USING CRON 0 3 * * * UTC'\n    CONFIG='{\"run_id\":\"scheduled\"}'\n"
        sql += _run_render(f"    QUERY_TAG='{tag}'\n    COMMENT='__RUN_TOKEN__ log-only {name}'\n")
        if step['after']:
            sql += '    AFTER ' + ', '.join('ORCH.' + steps[p]['task'] for p in step['after']) + '\n'
        if name == 'decision':
            sql += "    WHEN SYSTEM$GET_PREDECESSOR_RETURN_VALUE('DAG_SESSION_D') = 'CONTINUE'\n"
        if name == 'session_d':
            sql += "AS EXECUTE IMMEDIATE $$ BEGIN\n    CALL ORCH.RUN_STEP('session_d');\n    CALL SYSTEM$SET_RETURN_VALUE('CONTINUE');\nEND; $$;\n\n"
        else:
            sql += f"AS CALL ORCH.RUN_STEP('{name}');\n\n"
    return sql.rstrip() + '\n'


if __name__ == '__main__':
    TARGET.write_text(render())
