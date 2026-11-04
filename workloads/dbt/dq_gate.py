"""Snowflake workload data-quality gate: run one workload's dq-tagged dbt tests and record them in provenance.yaml.

  run   --workload W [--phase dev --session-url URL | --phase runtime] [--cause TEST=TEXT ...]
        runs `dbt test --select tag:dq_W` on W's attributed connection, then records the results
  record --workload W [--cause TEST=TEXT ...]   records workloads/dbt/target/run_results.json again
  check --workload W                            exits 1 if the recorded gate is incomplete or not passing
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DBT_DIR = Path(__file__).resolve().parent
PLAYBOOK = 'Snowflake workload data-quality gate'
CHECKS = ('freshness', 'row_count', 'uniqueness', 'accepted_range', 'worked_example')
FAILING = ('fail', 'error')


def provenance_path(workload):
    return ROOT / 'workloads' / workload / 'provenance.yaml'


def run_tests(workload, phase, session_url):
    import snowflake.connector
    from dbt.cli.main import dbtRunner

    sys.path.insert(0, str(ROOT / 'workloads/pipeline'))
    from pipeline import CONSUMERS, attr

    os.environ.pop('SNOWFLAKE_HOST', None)
    endpoint = attr.Endpoint.from_csid(CONSUMERS[workload][0], workload)
    names = attr.names([workload])
    commit = attr.current_commit(str(ROOT))
    run_id = attr.make_run_id(workload, phase)
    url = session_url if phase == 'dev' else None
    tag = attr.query_tag_json(endpoint, phase=phase, commit=commit, run_id=run_id, session_url=url)
    os.environ.update(DBT_DATABASE=names[f'db_{workload}'], DBT_WAREHOUSE=names[f'wh_{workload}'], DBT_QUERY_TAG=tag)
    original_connect = snowflake.connector.connect

    def attributed_connect(**kwargs):
        params = attr.connection_params(
            endpoint, account=os.environ['SNOWFLAKE_ACCOUNT'],
            private_key_file=os.environ['SNOWFLAKE_PRIVATE_KEY_FILE'], phase=phase, commit=commit,
            run_id=run_id, session_url=url, role=os.environ['SNOWFLAKE_ROLE'],
        )
        params['user'] = os.environ['SNOWFLAKE_USER']
        params['session_parameters'].update({'TIMEZONE': 'UTC', 'WEEK_START': 1, 'QUERY_TAG': tag})
        for key in ('client_session_keep_alive', 'autocommit', 'client_prefetch_threads'):
            if key in kwargs:
                params[key] = kwargs[key]
        return original_connect(**params)

    snowflake.connector.connect = attributed_connect
    try:
        dbtRunner().invoke([
            'test', '--project-dir', str(DBT_DIR), '--profiles-dir', str(DBT_DIR), '--target', 'dev',
            '--select', f'tag:dq_{workload}', '--no-partial-parse',
            '--vars', json.dumps({k: names[k] for k in ('reader_role', 'analyst_role', 'email_masking_policy')}),
        ])
    finally:
        snowflake.connector.connect = original_connect
    return {'run_id': run_id, 'phase': phase, 'commit': commit, 'session': url}


def collect(workload):
    target = DBT_DIR / 'target'
    manifest = json.loads((target / 'manifest.json').read_text())
    nodes = {**manifest.get('nodes', {}), **manifest.get('unit_tests', {})}
    tests = []
    for result in json.loads((target / 'run_results.json').read_text())['results']:
        node = nodes.get(result['unique_id'], {})
        tags = node.get('tags') or node.get('config', {}).get('tags', [])
        if f'dq_{workload}' not in tags:
            continue
        checks = [c for c in CHECKS if f'dq_{c}' in tags]
        if len(checks) != 1:
            raise SystemExit(f"{result['unique_id']} needs exactly one of {['dq_' + c for c in CHECKS]}, has {tags}")
        tests.append({
            'name': node.get('name', result['unique_id'].split('.')[-1]),
            'check': checks[0],
            'status': result['status'],
            'failures': int(result.get('failures') or 0),
        })
    return sorted(tests, key=lambda t: (CHECKS.index(t['check']), t['name']))


def record(workload, run, causes):
    tests = collect(workload)
    for test in tests:
        if test['status'] in FAILING:
            if test['name'] not in causes:
                raise SystemExit(f"{test['name']} is {test['status']}: name its cause with --cause {test['name']}=...")
            test['cause'] = causes[test['name']]
    summary = {s: sum(t['status'] == s for t in tests) for s in ('pass', 'fail', 'error', 'warn', 'skipped')}
    block = {'playbook': PLAYBOOK, **{k: v for k, v in run.items() if v is not None},
             'ran_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
             'status': 'fail' if summary['fail'] or summary['error'] else 'pass',
             'summary': summary, 'tests': tests}
    path = provenance_path(workload)
    doc = yaml.safe_load(path.read_text())
    doc['data_quality'] = block
    path.write_text(yaml.safe_dump(doc, sort_keys=False, width=1000))
    return block


def check(workload):
    block = yaml.safe_load(provenance_path(workload).read_text()).get('data_quality')
    if not block:
        print(f'::error::{workload}: provenance.yaml has no data_quality results')
        return 1
    problems = [f'no {c} test recorded' for c in CHECKS if not any(t['check'] == c for t in block['tests'])]
    for test in block['tests']:
        line = f"{test['status'].upper():7} {test['check']:14} {test['name']}"
        print(line + (f"  ({test['failures']} rows) cause: {test['cause']}" if test['status'] in FAILING else ''))
        if test['status'] in FAILING:
            problems.append(f"{test['name']} {test['status']}: {test['cause']}")
    for problem in problems:
        print(f'::error::{workload}: {problem}')
    print(f"{workload}: data-quality gate {'FAILED' if problems else 'passed'} (run {block.get('run_id')}, {block['ran_at']})")
    return 1 if problems else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('action', choices=['run', 'record', 'check'])
    parser.add_argument('--workload', required=True)
    parser.add_argument('--phase', choices=['dev', 'runtime'], default='dev')
    parser.add_argument('--session-url')
    parser.add_argument('--cause', action='append', default=[], metavar='TEST=TEXT')
    args = parser.parse_args()
    if not provenance_path(args.workload).exists():
        parser.error(f'no workloads/{args.workload}/provenance.yaml')
    causes = dict(c.split('=', 1) for c in args.cause)
    if args.action == 'check':
        return check(args.workload)
    if args.action == 'run':
        run = run_tests(args.workload, args.phase, args.session_url)
    else:
        previous = yaml.safe_load(provenance_path(args.workload).read_text()).get('data_quality') or {}
        run = {k: previous.get(k) for k in ('run_id', 'phase', 'commit', 'session')}
    block = record(args.workload, run, causes)
    print(json.dumps(block['summary']))
    return check(args.workload)


if __name__ == '__main__':
    raise SystemExit(main())
