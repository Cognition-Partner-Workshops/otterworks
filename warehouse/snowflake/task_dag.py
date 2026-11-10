"""Execute the placeholder graph once without enabling the root schedule."""
import argparse
import json
import re
import time

import yaml

from ledger import records
from sfx_conn import ROOT, connect, query_tag


def step_map():
    steps = yaml.safe_load((ROOT / 'task_dag.yml').read_text())['steps']
    seen = set()
    for name, step in steps.items():
        if not re.fullmatch(r'[A-Z][A-Z0-9_]*', step['task']):
            raise ValueError('Invalid DAG task identifier')
        if not set(step['after']) <= seen:
            raise ValueError('DAG map must be in predecessor order')
        seen.add(name)
    return steps


def suspend_tasks(cursor, steps):
    errors = []
    for step in steps.values():
        try:
            # Task names are regex-validated by step_map before dispatch.
            # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            cursor.execute(f"ALTER TASK ORCH.{step['task']} SUSPEND")
        except Exception as error:
            errors.append(str(error))
    states = records(cursor, 'SHOW TASKS IN SCHEMA ORCH')
    names = {step['task'] for step in steps.values()}
    actual = {r['name']: r['state'].lower() for r in states if r['name'] in names}
    for name, state in sorted(actual.items()):
        print(f'{name}: {state}')
    if errors or set(actual) != names or any(state != 'suspended' for state in actual.values()):
        raise RuntimeError('DAG suspension verification failed: ' + '; '.join(errors))


def run_once(cursor, timeout=180, poll_seconds=2):
    steps = step_map()
    names = {step['task'] for step in steps.values()}
    root = steps['start']['task']
    tag = query_tag('transform', 'task_dag')
    run_id = json.loads(tag)['run_id']
    complete = False
    try:
        suspend_tasks(cursor, steps)
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        cursor.execute(f'ALTER TASK ORCH.{root} SET CONFIG = %s',
                       (json.dumps({'run_id': run_id}),))
        for step in steps.values():
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            cursor.execute(f"ALTER TASK ORCH.{step['task']} SET QUERY_TAG = %s", (tag,))
        for name, step in reversed(list(steps.items())):
            if name != 'start':
                # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                cursor.execute(f"ALTER TASK ORCH.{step['task']} RESUME")
        cursor.execute('SELECT CURRENT_TIMESTAMP()')
        since = cursor.fetchone()[0]
        # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        cursor.execute(f'EXECUTE TASK ORCH.{root}')
        deadline = time.monotonic() + timeout
        while True:
            history = records(cursor, '''SELECT NAME, STATE, SCHEDULED_TIME,
                QUERY_START_TIME, COMPLETED_TIME, QUERY_ID, ERROR_MESSAGE, GRAPH_RUN_GROUP_ID
                FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY(
                    SCHEDULED_TIME_RANGE_START=>TO_TIMESTAMP_LTZ(%s), RESULT_LIMIT=>10000))
                WHERE DATABASE_NAME='SFX_D1110_AFTER' AND SCHEMA_NAME='ORCH'
                ORDER BY SCHEDULED_TIME''', (since,))
            roots = [r for r in history if r['name'] == root]
            if roots:
                graph = roots[0]['graph_run_group_id']
                history = [r for r in history if r['graph_run_group_id'] == graph and r['name'] in names]
                failed = [r for r in history if r['state'] in ('FAILED', 'FAILED_AND_AUTO_SUSPENDED', 'CANCELLED', 'SKIPPED')]
                if failed:
                    raise RuntimeError('DAG failed: ' + json.dumps(failed, default=str))
                if {r['name'] for r in history if r['state'] == 'SUCCEEDED'} == names:
                    for row in history:
                        print(json.dumps(row, default=str, sort_keys=True))
                    complete = True
                    return history
            if time.monotonic() >= deadline:
                raise TimeoutError('DAG timed out: ' + json.dumps(history, default=str))
            time.sleep(poll_seconds)
    finally:
        if not complete:
            for step in steps.values():
                try:
                    cursor.execute('SELECT SYSTEM$USER_TASK_CANCEL_ONGOING_EXECUTIONS(%s)',
                                   ('SFX_D1110_AFTER.ORCH.' + step['task'],))
                except Exception as error:
                    print(f"Cancellation check for {step['task']}: {error}")
        suspend_tasks(cursor, steps)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-once', action='store_true', required=True)
    parser.add_argument('--timeout', type=int, default=180)
    args = parser.parse_args()
    if not 1 <= args.timeout <= 600:
        parser.error('--timeout must be between 1 and 600 seconds')
    with connect('transform', 'task_dag_control') as conn, conn.cursor() as cursor:
        run_once(cursor, args.timeout)
        run_id = json.loads(query_tag('transform', 'task_dag'))['run_id']
        logs = records(cursor, '''SELECT STEP, TASK_NAME, RUN_ID, STARTED_AT, ENDED_AT
            FROM ORCH.STEP_RUN_LOG WHERE RUN_ID=%s ORDER BY STARTED_AT, STEP''', (run_id,))
        print('STEP_RUN_LOG')
        for row in logs:
            print(json.dumps(row, default=str, sort_keys=True))


if __name__ == '__main__':
    main()
