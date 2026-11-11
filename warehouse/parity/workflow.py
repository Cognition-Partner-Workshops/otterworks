"""Run wf_SFX_AUDIT_DAILY as scoped dbt sessions with PowerCenter link semantics."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from .inventory import ESTATE, ROOT

FOLDER = 'SFX_AUDIT'
WORKFLOW = 'wf_SFX_AUDIT_DAILY'
SCHEMAS = ('PC_AUDIT', 'PC_FX_UNT9_AUDIT_WF')
SESSIONS = {
    's_m_SFX_STG_AUDIT_EVENT': 'pc_audit__stg_audit_event',
    's_m_SFX_AUDIT_EVENT': 'pc_audit__audit_event',
    's_m_SFX_AUDIT_DAILY_SUMMARY': 'pc_audit__audit_daily_summary',
    's_m_SFX_AUDIT_EVENT_ARCHIVE': 'pc_audit__audit_event_archive',
    's_m_SFX_SECURITY_ALERT': 'pc_audit__security_alert',
}
LINK = re.compile(r'^\$(\w+)\.Status\s*=\s*SUCCEEDED$')


def graph(repository=None):
    """Tasks and links of the canonical workflow, read from the exported XML."""
    sys.path.insert(0, str(ESTATE))
    from runner.repo import Repository
    flow = Repository(str(repository or ESTATE / 'repository')).workflows[(FOLDER, WORKFLOW)]
    tasks = {}
    for name, task in flow.tasks.items():
        if task.tasktype == 'Start':
            tasks[name] = {'type': 'Start', 'enabled': True, 'after': []}
            continue
        if task.tasktype != 'Session' or task.taskname not in SESSIONS or not task.fail_parent \
                or not task.treat_input_as_and:
            raise ValueError('Unsupported workflow task: ' + name)
        tasks[name] = {'type': 'Session', 'enabled': task.enabled, 'model': SESSIONS[task.taskname], 'after': []}
    for link in flow.links:
        condition = (link.condition or '').strip()
        if condition:
            match = LINK.match(condition)
            if not match or match.group(1) != link.from_task:
                raise ValueError('Unsupported link condition: ' + condition)
        elif tasks[link.from_task]['type'] != 'Start':
            raise ValueError('Unconditional link from a session: ' + link.from_task)
        tasks[link.to_task]['after'].append(link.from_task)
    return tasks


def selector(tasks):
    """dbt models of the enabled sessions, in dependency order."""
    return [t['model'] for t in order(tasks) if t['type'] == 'Session' and t['enabled']]


def order(tasks):
    done, result = set(), []
    while len(done) < len(tasks):
        ready = [n for n in tasks if n not in done and set(tasks[n]['after']) <= done]
        if not ready:
            raise ValueError('Workflow graph has a cycle')
        for name in sorted(ready):
            done.add(name)
            result.append(dict(tasks[name], name=name))
    return result


def run(tasks, execute):
    """Execute enabled sessions whose every input link fired; never stamp success after a failure."""
    state = {}
    for task in order(tasks):
        name = task['name']
        if task['type'] == 'Start':
            state[name] = 'SUCCEEDED'
        elif any(state[p] != 'SUCCEEDED' for p in task['after']):
            state[name] = 'NOTSTARTED'
        elif not task['enabled']:
            state[name] = 'DISABLED'
        else:
            state[name] = 'SUCCEEDED' if execute(name, task['model']) == 0 else 'FAILED'
    enabled = [n for n, t in tasks.items() if t['type'] == 'Session' and t['enabled']]
    status = 'SUCCEEDED' if all(state[n] == 'SUCCEEDED' for n in enabled) else 'FAILED'
    return {'workflow': WORKFLOW, 'status': status, 'sessions': state}


def dbt_command(model, schema, phase='dbt'):
    project = ROOT / 'warehouse/dbt'
    return [str(Path(sys.executable).with_name('dbt')), 'build', '--project-dir', str(project),
            '--profiles-dir', str(project), '--select', model,
            '--vars', json.dumps({'phase': phase, 'pc_audit_schema': schema})]


def dbt_executor(schema, step, out=None, fail=()):
    sys.path.insert(0, str(ROOT / 'warehouse/snowflake'))
    from sfx_conn import query_tag

    def execute(session, model):
        if session in fail:
            return 1
        env = os.environ.copy()
        env['DBT_ENV_SECRET_SNOWFLAKE_PRIVATE_KEY'] = env['SNOWFLAKE_PRIVATE_KEY']
        env['DBT_SEND_ANONYMOUS_USAGE_STATS'] = 'false'
        tag = json.loads(query_tag('transform', 'dbt', {'run': 'sfx-d1110', 'act': 'scale', 'step': step,
                                                        'workflow': WORKFLOW, 'session': session}))
        env['SFX_QUERY_TAG'] = json.dumps(tag, separators=(',', ':'))
        command = dbt_command(model, schema)
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
        if out:
            dest = Path(out) / session
            dest.mkdir(parents=True, exist_ok=False)
            (dest / 'stdout_stderr.log').write_text(result.stdout + result.stderr)
            (dest / 'execution.json').write_text(json.dumps({'argv': command, 'returncode': result.returncode},
                                                            indent=2))
            target = ROOT / 'warehouse/dbt/target'
            for kind in ('compiled', 'run'):
                for path in (target / kind).rglob(model + '.sql'):
                    (dest / f'{kind}.sql').write_text(path.read_text())
            if (target / 'run_results.json').exists():
                (dest / 'run_results.json').write_text((target / 'run_results.json').read_text())
        return result.returncode
    return execute


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description='Run ' + WORKFLOW + ' with dbt')
    parser.add_argument('--schema', default='PC_AUDIT', choices=SCHEMAS)
    parser.add_argument('--step', required=True)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--select-only', action='store_true', help='print the enabled-session dbt selector')
    args = parser.parse_args(argv)
    tasks = graph()
    if args.select_only:
        print(' '.join(selector(tasks)))
        return 0
    if os.environ.get('SNOWFLAKE_DATABASE') != 'SFX_D1110_AFTER':
        parser.error('SNOWFLAKE_DATABASE must be SFX_D1110_AFTER')
    result = run(tasks, dbt_executor(args.schema, args.step, args.out))
    print(json.dumps(result, indent=2))
    if args.out:
        (args.out / 'workflow_result.json').write_text(json.dumps(result, indent=2))
    return 0 if result['status'] == 'SUCCEEDED' else 1


if __name__ == '__main__':
    sys.exit(main())
