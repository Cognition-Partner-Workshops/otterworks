"""Deploy and optionally execute a suspended, folder-scoped PowerCenter DAG."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import yaml

from ledger import records
from sfx_conn import ROOT, WORKLOADS, connect, query_tag

COMMENT = 'run_token=sfx-d1110 expires=2026-11-24'


def folder_name(value):
    value = value.upper().removeprefix('SFX_').removeprefix('PC_')
    if value not in ('BILLING', 'CONTENT', 'AUDIT'):
        raise ValueError('Folder must be BILLING, CONTENT, or AUDIT')
    return value


def load(folder, path=None):
    folder = folder_name(folder)
    doc = yaml.safe_load((path or ROOT / 'pc_dag' / (folder.lower() + '.yml')).read_text())
    if not isinstance(doc, dict) or set(doc) - {'root', 'tasks'}:
        raise ValueError('Expected root and tasks')
    tasks = doc.get('tasks')
    if not isinstance(tasks, dict) or not tasks or doc.get('root') not in tasks:
        raise ValueError('Missing DAG root/tasks')
    prefix = f'SFX_D1110_PC_{folder}_'
    ordered = {}
    pending = dict(tasks)
    for name, task in tasks.items():
        if not re.fullmatch(r'[A-Z][A-Z0-9_]*', name):
            raise ValueError('Invalid task name')
        if not isinstance(task, dict) or set(task) - {'after', 'sql', 'warehouse'}:
            raise ValueError('Invalid task fields')
        if task.get('warehouse', WORKLOADS['transform']) != 'SFX_D1110_TRANSFORM_WH':
            raise ValueError('Invalid task warehouse')
        deps = task.get('after', [])
        if not isinstance(deps, list) or not set(deps) <= tasks.keys():
            raise ValueError('Unknown dependencies')
        if not isinstance(task.get('sql'), str) or not task['sql'].strip():
            raise ValueError('Task SQL is required')
        if (name == doc['root']) != (not deps):
            raise ValueError('Only root may have no dependencies')
    while pending:
        ready = [n for n, t in pending.items() if set(t.get('after', [])) <= ordered.keys()]
        if not ready:
            raise ValueError('Cyclic DAG')
        for name in ready:
            ordered[name] = dict(pending.pop(name), task=prefix + name)
    return folder, doc['root'], ordered


def task_tag(folder):
    return query_tag('transform', 'pc_dag', dict(run='sfx-d1110', act='scale', step='dag', folder=folder))


def create_sql(folder, step, tasks):
    schema = 'SFX_D1110_AFTER.PC_' + folder
    after = step.get('after', [])
    deps = (' AFTER ' + ', '.join(schema + '.' + tasks[n]['task'] for n in after)) if after else ''
    tag = task_tag(folder).replace("'", "''")
    return (f"CREATE TASK IF NOT EXISTS {schema}.{step['task']} WAREHOUSE=SFX_D1110_TRANSFORM_WH"
            f" COMMENT='{COMMENT}' QUERY_TAG='{tag}'{deps} AS {step['sql']}")


def suspend(cursor, folder, tasks):
    schema = 'SFX_D1110_AFTER.PC_' + folder
    errors = []
    for step in tasks.values():
        try:
            cursor.execute(f"ALTER TASK {schema}.{step['task']} SUSPEND")
        except Exception as error:
            errors.append(str(error))
    states = records(cursor, f'SHOW TASKS IN SCHEMA {schema}')
    expected = {s['task'] for s in tasks.values()}
    actual = {r['name']: r['state'].lower() for r in states if r['name'] in expected}
    for name, state in sorted(actual.items()):
        print(f'{name}: {state}')
    if errors or set(actual) != expected or any(s != 'suspended' for s in actual.values()):
        raise RuntimeError('DAG suspension verification failed: ' + '; '.join(errors))


def deploy(cursor, folder, tasks):
    schema = 'SFX_D1110_AFTER.PC_' + folder
    cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema} COMMENT='{COMMENT}'")
    # Suspend existing graph before altering root or dependency relationships.
    existing = records(cursor, f'SHOW TASKS IN SCHEMA {schema}')
    names = {t['task'] for t in tasks.values()}
    for row in existing:
        if row['name'] in names:
            cursor.execute(f"ALTER TASK {schema}.{row['name']} SUSPEND")
    try:
        for step in tasks.values():
            cursor.execute(create_sql(folder, step, tasks))
            cursor.execute(f"ALTER TASK {schema}.{step['task']} MODIFY AS {step['sql']}")
            cursor.execute(f"ALTER TASK {schema}.{step['task']} SET WAREHOUSE=SFX_D1110_TRANSFORM_WH COMMENT='{COMMENT}' QUERY_TAG=%s", (task_tag(folder),))
            current = records(cursor, f"SHOW TASKS LIKE '{step['task']}' IN SCHEMA {schema}")
            predecessors = json.loads(next(r['predecessors'] for r in current if r['name'] == step['task']))
            for predecessor in predecessors:
                cursor.execute(f"ALTER TASK {schema}.{step['task']} REMOVE AFTER {predecessor}")
            if step.get('after'):
                cursor.execute(f"ALTER TASK {schema}.{step['task']} ADD AFTER " + ', '.join(schema + '.' + tasks[n]['task'] for n in step['after']))
    finally:
        suspend(cursor, folder, tasks)


def run_once(cursor, folder, root, tasks, timeout=180, load_date=None, build=None):
    schema = 'SFX_D1110_AFTER.PC_' + folder
    names = {t['task'] for t in tasks.values()}
    complete = False
    try:
        suspend(cursor, folder, tasks)
        if build:
            build()
        if load_date:
            cursor.execute("ALTER TASK IDENTIFIER(%s) SET CONFIG=%s",
                           (f"{schema}.{tasks[root]['task']}", json.dumps({'load_date': load_date})))
        for name, step in reversed(list(tasks.items())):
            if name != root:
                cursor.execute(f"ALTER TASK {schema}.{step['task']} RESUME")
        cursor.execute('SELECT CURRENT_TIMESTAMP()')
        since = cursor.fetchone()[0]
        cursor.execute(f"EXECUTE TASK {schema}.{tasks[root]['task']}")
        deadline = time.monotonic() + timeout
        while True:
            history = records(cursor, '''SELECT NAME,STATE,ERROR_MESSAGE,GRAPH_RUN_GROUP_ID
                FROM TABLE(SFX_D1110_AFTER.INFORMATION_SCHEMA.TASK_HISTORY(
                SCHEDULED_TIME_RANGE_START=>TO_TIMESTAMP_LTZ(%s), RESULT_LIMIT=>10000))
                WHERE DATABASE_NAME='SFX_D1110_AFTER' AND SCHEMA_NAME=%s
                ORDER BY SCHEDULED_TIME DESC''', (since, 'PC_' + folder))
            roots = [r for r in history if r['name'] == tasks[root]['task']]
            if roots:
                graph = roots[0]['graph_run_group_id']
                history = [r for r in history if r['graph_run_group_id'] == graph and r['name'] in names]
                if any(r['state'] in ('FAILED', 'CANCELLED', 'SKIPPED', 'FAILED_AND_AUTO_SUSPENDED') for r in history):
                    raise RuntimeError('DAG failed: ' + json.dumps(history, default=str))
                if {r['name'] for r in history if r['state'] == 'SUCCEEDED'} == names:
                    complete = True
                    print(json.dumps(history, default=str))
                    return
            if time.monotonic() >= deadline:
                raise TimeoutError('DAG timed out')
            time.sleep(2)
    finally:
        if not complete:
            for step in tasks.values():
                try:
                    cursor.execute('SELECT SYSTEM$USER_TASK_CANCEL_ONGOING_EXECUTIONS(%s)', (schema + '.' + step['task'],))
                except Exception as error:
                    print(f'Cancellation failed: {error}')
        suspend(cursor, folder, tasks)


def build_folder(folder, load_date):
    subprocess.run([sys.executable, str(Path(__file__).with_name('run_dbt.py')), 'build',
                    '--select', 'path:models/pc/' + folder.lower(), '--step', 'dbt',
                    '--load-date', load_date], check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--folder', required=True)
    parser.add_argument('--run-once', action='store_true')
    parser.add_argument('--timeout', type=int, default=180)
    parser.add_argument('--load-date', default='20261109')
    args = parser.parse_args()
    if not re.fullmatch(r'[0-9]{8}', args.load_date):
        parser.error('--load-date must be YYYYMMDD')
    if not 1 <= args.timeout <= 600:
        parser.error('--timeout must be 1..600')
    if os.environ.get('SNOWFLAKE_DATABASE') != 'SFX_D1110_AFTER':
        parser.error('SNOWFLAKE_DATABASE must be SFX_D1110_AFTER')
    folder, root, tasks = load(args.folder)
    with connect('transform', 'pc_dag', extra_tag=dict(run='sfx-d1110', act='scale', step='dag', folder=folder)) as conn, conn.cursor() as cur:
        deploy(cur, folder, tasks)
        if args.run_once:
            run_once(cur, folder, root, tasks, args.timeout, args.load_date,
                     lambda: build_folder(folder, args.load_date))


if __name__ == '__main__':
    main()
