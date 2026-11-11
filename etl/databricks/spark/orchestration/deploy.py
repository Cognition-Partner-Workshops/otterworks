"""run_token=dbx-d1111 expires=2026-11-24; stdlib Jobs/SQL client."""
import argparse
import json
import os
import re
from pathlib import Path
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent


def api(method, path, body=None):
    request = urllib.request.Request(
        os.environ['DATABRICKS_HOST'].rstrip('/') + '/api/' + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Authorization': 'Bearer ' + os.environ['DATABRICKS_TOKEN'],
                 'Content-Type': 'application/json'}, method=method)
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def save(name, value):
    (ROOT / name).write_text(json.dumps(value, indent=2) + '\n')


def deploy():
    result = {}
    for kind in ('daily', 'hourly'):
        settings = json.loads((ROOT / (kind + '.json')).read_text())
        jobs, token = [], None
        while True:
            query = {'limit': 100}
            if token:
                query['page_token'] = token
            page = api('GET', '2.1/jobs/list?' + urllib.parse.urlencode(query))
            jobs.extend(j for j in page.get('jobs', [])
                        if j['settings']['name'] == settings['name'])
            token = page.get('next_page_token')
            if not token:
                break
        if len(jobs) > 1:
            raise RuntimeError('Duplicate orchestration job name')
        if jobs:
            job_id = jobs[0]['job_id']
            tags = jobs[0]['settings'].get('tags', {})
            if tags.get('act') != 'spark' or tags.get('run_token') != 'dbx-d1111':
                raise RuntimeError('Refusing to reset a job outside this run/act')
            api('POST', '2.1/jobs/reset', {'job_id': job_id, 'new_settings': settings})
        else:
            job_id = api('POST', '2.1/jobs/create', settings)['job_id']
        live = api('GET', f'2.1/jobs/get?job_id={job_id}')['settings']
        assert live['schedule']['pause_status'] == 'PAUSED'
        result[kind] = {'job_id': job_id, 'schedule': live['schedule']}
    save('deployment.json', result)
    return result


def sql(statement):
    assert statement.startswith('/* run=dbx-d1111 act=spark step=')
    response = api('POST', '2.0/sql/statements', {
        'warehouse_id': os.environ['DATABRICKS_WAREHOUSE_ID'],
        'statement': statement, 'wait_timeout': '50s', 'row_limit': 10000})
    while response['status']['state'] in ('PENDING', 'RUNNING'):
        time.sleep(2)
        response = api('GET', '2.0/sql/statements/' + response['statement_id'])
    if response['status']['state'] != 'SUCCEEDED':
        raise RuntimeError(json.dumps(response))
    if response.get('manifest', {}).get('truncated'):
        raise RuntimeError('Truncated SQL evidence')
    return response


CONTROL = 'cpw.dbx_d1111_control.migration_control'


def control(path):
    statement = Path(path).read_text()
    insert_cols = re.search(r'INSERT \(([^)]*)\)', statement).group(1)
    wanted = [c.strip() for c in insert_cols.split(',')]
    rows = sql('/* run=dbx-d1111 act=spark step=control-describe consumer=orchestration */ '
               f'DESCRIBE TABLE {CONTROL}')['result'].get('data_array', [])
    existing = {r[0].lower() for r in rows if r[0] and not r[0].startswith('#')}
    missing = [c for c in wanted if c.lower() not in existing]
    result = {'added_columns': missing}
    if missing:
        types = ', '.join(c + (' TIMESTAMP' if c == 'updated_at' else ' STRING') for c in missing)
        result['alter'] = sql('/* run=dbx-d1111 act=spark step=control-ddl consumer=orchestration */ '
                              f'ALTER TABLE {CONTROL} ADD COLUMNS ({types})')['statement_id']
    result['merge'] = sql(statement)['statement_id']
    return result


def status(run_id):
    return api('GET', f'2.1/jobs/runs/get?run_id={run_id}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['deploy', 'run-now', 'status', 'sql', 'control'])
    parser.add_argument('value', nargs='?')
    args = parser.parse_args()
    if args.command == 'deploy':
        result = deploy()
    elif args.command == 'run-now':
        job_id = json.loads((ROOT / 'deployment.json').read_text())['daily']['job_id']
        marker = ROOT / 'daily-run.json'
        if marker.exists() and json.loads(marker.read_text()).get('job_id') == job_id:
            raise RuntimeError('Daily run already recorded for this job; refusing a second trigger')
        result = api('POST', '2.1/jobs/run-now', {
            'job_id': job_id,
            'idempotency_token': f'dbx-d1111-spark-orchestration-daily-once-{job_id}'})
        save('daily-run.json', {'job_id': job_id, **result})
    elif args.command == 'status':
        result = status(int(args.value))
    elif args.command == 'control':
        result = control(args.value)
    else:
        result = sql(Path(args.value).read_text())
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
