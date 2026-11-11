"""UNT-9 evidence: wf_SFX_AUDIT_DAILY PowerCenter oracle, two dbt workflow replays, one Task DAG run."""
import argparse
import csv
from datetime import datetime, timezone
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

from . import evidence_live
from .evidence import BOOTSTRAP, ESTATE, OUT, cell, dump, full_compare, sha, snapshot
from .evidence_live import fetched
from .evidence_unt3 import control_snapshot, load, queries, target_state
from .inventory import ROOT

DEST = OUT / 'unt9'
ACCEPTED = Path(os.environ.get('UNT9_ACCEPTED_ORACLE', Path.home() / 'unt9/ev/unt2p2/out/evidence'))
MANIFEST = Path(os.environ.get('UNT9_MANIFEST', Path.home() / 'attachments/1c299b4d-6dde-4108-8946-1d68e128b511/manifest.json'))
SCHEMA = 'PC_FX_UNT9_AUDIT_WF'
FQ_SCHEMA = 'SFX_D1110_AFTER.' + SCHEMA
LANDING = ('AUDIT_EVENT', 'SECURITY_ALERT')
# Enabled wf_SFX_AUDIT_DAILY sessions: mapping, PostgreSQL target, Snowflake table, business key.
TARGETS = {
    's_m_SFX_STG_AUDIT_EVENT': ('m_SFX_STG_AUDIT_EVENT', 'sfx_audit.stg_audit_event', 'STG_AUDIT_EVENT', ['EVENT_ID']),
    's_m_SFX_AUDIT_EVENT': ('m_SFX_AUDIT_EVENT', 'sfx_audit.audit_event', 'AUDIT_EVENT', ['EVENT_ID']),
    's_m_SFX_AUDIT_DAILY_SUMMARY': ('m_SFX_AUDIT_DAILY_SUMMARY', 'sfx_audit.audit_daily_summary', 'AUDIT_DAILY_SUMMARY',
                                    ['SUMMARY_ID']),
    's_m_SFX_SECURITY_ALERT': ('m_SFX_SECURITY_ALERT', 'sfx_audit.security_alert', 'SECURITY_ALERT', ['ALERT_ID']),
}
ARCHIVE_PG = 'sfx_audit.audit_event_archive'


def binding():
    dirty = subprocess.check_output(['git', 'status', '--porcelain', '--', 'warehouse', 'etl/informatica'],
                                    cwd=ROOT, text=True)
    if dirty:
        raise ValueError('Refusing execution with a dirty tree')
    paths = subprocess.check_output(['git', 'ls-files', 'warehouse', 'etl/informatica'], cwd=ROOT, text=True).splitlines()
    return {'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            'sha256': {p: sha(ROOT / p) for p in paths if (ROOT / p).is_file()}}


def fresh(path):
    if path.exists():
        raise ValueError('Refusing to overwrite evidence: ' + str(path))
    path.mkdir(parents=True)
    dump(path / 'implementation.json', binding())


def utc():
    return datetime.now(timezone.utc).isoformat()


def frozen_inputs():
    manifest = json.loads(MANIFEST.read_text())
    files = {Path(f['path']).parent.name: f for f in manifest['landing'] if Path(f['path']).parts[-3] == 'audit'}
    checks = {'bootstrap': manifest['bootstrap_sha256'] == sha(BOOTSTRAP),
              'parameter_file': manifest['parameter_file']['sha256'] == sha(Path(manifest['parameter_file']['path'])),
              'runner_commit_unchanged': not subprocess.run(
                  ['git', 'diff', '--quiet', manifest['runner_git_commit'], 'HEAD', '--', 'etl/informatica'],
                  cwd=ROOT).returncode}
    for name in LANDING:
        path = ESTATE / 'tests/fixture/landing/audit' / name / '20261109.psv'
        checks[name] = files[name]['sha256'] == sha(path) and \
            files[name]['row_count'] == len(path.read_text().splitlines())
    if not all(checks.values()):
        raise ValueError('Frozen input manifest mismatch: ' + json.dumps(checks))
    return {'manifest_sha256': sha(MANIFEST), 'business_date': manifest['business_date'], 'checks': checks,
            'initial_tables': {k: len(v['rows']) for k, v in manifest['initial_tables'].items() if k.startswith('SFX_AUDIT.')}}


def sessions(root, run_id=None):
    with (root / 'REP_SESS_LOG.psv').open() as stream:
        rows = [r for r in csv.DictReader(stream, delimiter='|') if r['WORKFLOW_NAME'] == 'wf_SFX_AUDIT_DAILY']
    last = run_id or max(r['WORKFLOW_RUN_ID'] for r in rows)
    return [r for r in rows if r['WORKFLOW_RUN_ID'] == last]


def oracle():
    """Run the PowerCenter emulator's wf_SFX_AUDIT_DAILY twice on a fresh PostgreSQL database."""
    import psycopg
    path = DEST / 'oracle'
    fresh(path)
    dump(path / 'frozen_inputs.json', frozen_inputs())
    db = 'unt9_wf_' + uuid.uuid4().hex[:12]
    params = dict(host='127.0.0.1', port=int(os.environ.get('UNT9_PG_PORT', '56042')), user='postgres')
    root = (path / db).resolve()
    for name in LANDING:
        staged = root / 'landing/audit' / name
        staged.mkdir(parents=True)
        shutil.copy2(ESTATE / 'tests/fixture/landing/audit' / name / '20261109.psv', staged / '20261109.psv')
    command = [sys.executable, '-m', 'runner', 'startworkflow', '-f', 'SFX_AUDIT', 'wf_SFX_AUDIT_DAILY']
    env = {k: v for k, v in os.environ.items() if not k.startswith(('SNOWFLAKE_', 'TD_'))}
    env.update(TD_HOST=params['host'], TD_PORT=str(params['port']), TD_USER='postgres', TD_PASSWORD='',
               TD_DB=db, PMROOTDIR=str(root), LANDING_DIR=str(root / 'landing'))
    with psycopg.connect(dbname='postgres', autocommit=True, **params) as admin:
        admin.execute('CREATE DATABASE ' + db)
    with psycopg.connect(dbname=db, autocommit=True, **params) as pg:
        pg.execute(BOOTSTRAP.read_text())
        initial = {s: snapshot(pg, t[1]) for s, t in TARGETS.items()}
        initial['archive'] = snapshot(pg, ARCHIVE_PG)
        dump(path / 'initial_targets.json', initial)
        if any(s['rows'] for s in initial.values()):
            raise ValueError('Oracle initial state is not empty')
        dump(path / 'lineage.json', {'command': command, 'database': db, 'cwd': str(ESTATE)})
        for number in (1, 2):
            dest = path / f'run{number}'
            dest.mkdir()
            start = utc()
            result = subprocess.run(command, cwd=ESTATE, env=env, capture_output=True, text=True)
            (dest / 'stdout_stderr.log').write_text(result.stdout + result.stderr)
            for folder in ('SessLogs', 'BadFiles', 'WorkflowLogs'):
                if (root / folder).exists():
                    shutil.copytree(root / folder, dest / folder)
            shutil.copy2(root / 'REP_SESS_LOG.psv', dest / 'REP_SESS_LOG.psv')
            runs = sessions(root)
            dump(dest / 'session_results.json', runs)
            targets = {s: snapshot(pg, t[1]) for s, t in TARGETS.items()}
            targets['archive'] = snapshot(pg, ARCHIVE_PG)
            dump(dest / 'targets.json', targets)
            rejects = {f.name: f.read_text().splitlines() for f in sorted((root / 'BadFiles').glob('*.bad'))}
            dump(dest / 'rejects.json', rejects)
            dump(dest / 'execution.json', {'argv': command, 'returncode': result.returncode,
                                           'start_utc': start, 'end_utc': utc()})
            if result.returncode:
                raise ValueError('Oracle workflow failed')
    run1 = load(path / 'run1/targets.json')
    accepted = {}
    for session, (mapping, _, _, keys) in TARGETS.items():
        template = load(ACCEPTED / mapping / 'oracle1/target.json')
        compare = full_compare(template, run1[session], keys)
        accepted[session] = {'equal': compare['equal'], 'rows': compare['after_rows'],
                             'accepted_rows': compare['before_rows']}
    status = {r['SESSION_INSTANCE_NAME']: r['RUN_STATUS'] for r in load(path / 'run1/session_results.json')}
    summary = {'accepted_oracle_equal': accepted, 'run1_sessions': status,
               'archive_rows': len(run1['archive']['rows']),
               'archive_ran': 's_m_SFX_AUDIT_EVENT_ARCHIVE' in status}
    dump(path / 'summary.json', summary)
    print(json.dumps(summary, indent=2))
    if not all(a['equal'] for a in accepted.values()) or summary['archive_ran'] or \
            set(status) != set(TARGETS) or set(status.values()) != {'SUCCEEDED'}:
        raise ValueError('Oracle does not match the accepted UNT-2 workflow oracle')



WRITE_TYPES = ('SELECT', 'SHOW', 'DESCRIBE', 'USE', 'ALTER_SESSION', 'BEGIN_TRANSACTION', 'COMMIT', 'ROLLBACK')
TASK_PREFIX = 'SFX_D1110_PC_AUDIT_'


def controls(q, path):
    result = control_snapshot(q, path)
    if result['row_count'] != 20:
        raise ValueError('Expected 20 control rows')
    dump(path / 'control_sha256.json', result)
    return result


def protected(q, path):
    _, relations = q.run("SELECT TABLE_SCHEMA,TABLE_NAME FROM SFX_D1110_AFTER.INFORMATION_SCHEMA.TABLES "
                         "WHERE TABLE_SCHEMA IN ('PC_CONTENT','PC_AUDIT','PC_BILLING') "
                         "OR (STARTSWITH(TABLE_SCHEMA,'PC_FX_') AND TABLE_SCHEMA<>'" + SCHEMA + "') "
                         "OR TABLE_SCHEMA LIKE '%FIXTURE%' "
                         "OR (TABLE_SCHEMA IN ('PC_SRC','PC_BEFORE') AND TABLE_NAME IN "
                         "('AUDIT_EVENT','SECURITY_ALERT','STG_AUDIT_EVENT','AUDIT_DAILY_SUMMARY','AUDIT_EVENT_ARCHIVE'))")
    values = {}
    for schema, name in sorted(relations):
        if not (schema + name).replace('_', '').isalnum():
            raise ValueError('Unsafe protected identifier')
        relation = 'SFX_D1110_AFTER.' + schema + '.' + name
        columns, rows = q.run('SELECT * FROM ' + relation)
        _, types = q.run('DESCRIBE TABLE ' + relation)
        values[relation] = {'columns': columns, 'types': [[cell(v) for v in r] for r in types],
                            'rows': sorted([[cell(v) for v in r] for r in rows], key=json.dumps)}
    names, meta = q.run("SELECT TABLE_SCHEMA,TABLE_NAME,TABLE_TYPE,ROW_COUNT,BYTES,LAST_ALTERED "
                        "FROM SFX_D1110_AFTER.INFORMATION_SCHEMA.TABLES "
                        "WHERE TABLE_SCHEMA IN ('PC_SRC','PC_BEFORE','MIGRATION_CONTROL') ORDER BY 1,2")
    metadata = [dict(zip(names, [cell(v) for v in r])) for r in meta]
    dump(path / 'protected.json', values)
    dump(path / 'protected_metadata.json', metadata)
    result = {'sha256': sha(path / 'protected.json'), 'metadata_sha256': sha(path / 'protected_metadata.json'),
              'relations': list(values)}
    dump(path / 'protected_sha256.json', result)
    return result


def isolation(q):
    _, schemas = q.run(f"SHOW SCHEMAS LIKE '{SCHEMA}' IN DATABASE SFX_D1110_AFTER")
    names, tasks = q.run(f"SHOW TASKS LIKE '{TASK_PREFIX}%' IN DATABASE SFX_D1110_AFTER")
    return {'schema_exists': bool(schemas), 'tasks': [dict(zip(names, [cell(v) for v in r])) for r in tasks],
            'show_tasks_qid': q.records[-1]['qid']}


def sources(q, path):
    """Identity/read-order preconditions: frozen PC_SRC rows match the landing files key-for-key."""
    result = {}
    for name, key in (('AUDIT_EVENT', 'EVENT_ID'), ('SECURITY_ALERT', 'ALERT_ID')):
        columns, rows = q.run(f'SELECT * FROM SFX_D1110_AFTER.PC_SRC.{name}')
        landing = ESTATE / 'tests/fixture/landing/audit' / name / '20261109.psv'
        expected = sorted(int(line.split('|')[0]) for line in landing.read_text().splitlines())
        actual = sorted(int(r[columns.index(key)]) for r in rows)
        result[name] = {'rows': len(rows), 'qid': q.records[-1]['qid'], 'keys_match_landing': actual == expected,
                        'distinct_keys': len(set(actual)) == len(actual)}
        dump(path / f'source_{name}.json', {'columns': columns,
                                             'rows': sorted([[cell(v) for v in r] for r in rows], key=json.dumps)})
    if not all(v['keys_match_landing'] and v['distinct_keys'] for v in result.values()):
        raise ValueError('PC_SRC does not match the frozen landing keys')
    return result


def preflight():
    path = DEST / 'preflight'
    fresh(path)
    with queries(path, 'unt9-preflight') as q:
        state = {'control': controls(q, path), 'protected': protected(q, path), 'sources': sources(q, path),
                 'isolation': isolation(q)}
    dump(path / 'summary.json', state)
    print(json.dumps({k: state[k] for k in ('control', 'sources', 'isolation')}, indent=2))
    if state['isolation']['schema_exists'] or state['isolation']['tasks']:
        raise ValueError('Isolated workflow schema or audit tasks already exist')


def targets(q, template):
    # Stage/event/summary keep source timestamp precision (UNT-3/UNT-4); security alert is TIMESTAMP_NTZ(9) (UNT-5).
    return {s: fetched(q, f'{FQ_SCHEMA}.{t[2]}', template[s], source_loading=s != 's_m_SFX_SECURITY_ALERT')
            for s, t in TARGETS.items()}


def history(q, start, path):
    names, rows = q.run(
        "SELECT QUERY_ID,QUERY_TEXT,QUERY_TYPE,QUERY_TAG,START_TIME,END_TIME,EXECUTION_STATUS,ROWS_INSERTED,"
        "ROWS_PRODUCED,SESSION_ID FROM TABLE(SFX_D1110_AFTER.INFORMATION_SCHEMA.QUERY_HISTORY_BY_USER("
        f"USER_NAME=>CURRENT_USER(), END_TIME_RANGE_START=>TO_TIMESTAMP_LTZ('{start}'), RESULT_LIMIT=>10000)) "
        "ORDER BY START_TIME")
    dump(path / 'query_history.json', {'columns': names, 'rows': [[cell(v) for v in r] for r in rows],
                                        'qid': q.records[-1]['qid']})
    return rows


def write_scope(rows):
    writes, failed, unparsed = [], [], []
    for row in rows:
        if row[6] != 'SUCCESS':
            failed.append(row)
            continue
        if row[2] in WRITE_TYPES:
            continue
        sql = re.sub(r'/\*.*?\*/', ' ', row[1] or '', flags=re.S).replace('"', '')
        sql = ' '.join(sql.split()).upper()
        if re.match(r'^(USE |ALTER SESSION |BEGIN|COMMIT|ROLLBACK|SELECT |SHOW |DESCRIBE |WITH )', sql):
            continue
        match = re.match(r'(?:MERGE INTO|INSERT INTO|UPDATE|DELETE FROM|COMMENT ON (?:TABLE|VIEW)|'
                         r'(?:CREATE(?: OR REPLACE)?(?: TEMPORARY| TEMP| TRANSIENT)?|ALTER|DROP) (?:TABLE|VIEW|SCHEMA))'
                         r'\s+(?:IF (?:NOT )?EXISTS\s+)?([A-Z0-9_.]+)', sql)
        if not match:
            unparsed.append(row)
            continue
        relation = match.group(1)
        writes.append({'qid': row[0], 'relation': relation,
                       'allowed': relation == FQ_SCHEMA or relation.startswith(FQ_SCHEMA + '.')})
    return {'writes': writes, 'failed_statements': [[cell(v) for v in r] for r in failed],
            'unparsed_successful_statements': [[cell(v) for v in r] for r in unparsed],
            'passed': not unparsed and all(r['allowed'] for r in writes),
            'limitation': 'Current-user unfiltered history since run start; not an account-wide audit'}


def replay(number):
    """One unchanged-input dbt workflow run into the isolated schema: no reset, no --full-refresh."""
    path = DEST / 'dbt' / f'run{number}'
    previous = DEST / 'dbt' / f'run{number - 1}'
    if number == 2 and not (previous / 'execution.json').exists():
        raise ValueError('run1 must complete first')
    fresh(path)
    with queries(path / 'pre', f'unt9-run{number}-pre') as q:
        before = {'isolation': isolation(q),
                  'targets': {s: target_state(q, f'{FQ_SCHEMA}.{t[2]}') for s, t in TARGETS.items()}}
        _, now = q.run('SELECT CURRENT_TIMESTAMP()::VARCHAR')
        start = now[0][0]
    dump(path / 'pre/state.json', before)
    command = [sys.executable, '-m', 'parity.workflow', '--schema', SCHEMA, '--step', f'unt9-run{number}',
               '--out', str(path / 'sessions')]
    result = subprocess.run(command, cwd=ROOT / 'warehouse', capture_output=True, text=True)
    (path / 'stdout_stderr.log').write_text(result.stdout + result.stderr)
    dump(path / 'execution.json', {'argv': command, 'returncode': result.returncode, 'history_start': start,
                                   'end_utc': utc()})
    collect(number)
    if result.returncode:
        raise ValueError('dbt workflow run failed')


def collect(number):
    """Post-run evidence only; rerunnable without executing dbt again."""
    path = DEST / 'dbt' / f'run{number}'
    execution = load(path / 'execution.json')
    template = load(DEST / 'oracle/run1/targets.json')
    post = path / 'post'
    if post.exists():
        attempts = sorted(path.glob('post_failed_attempt*'))
        post.rename(path / f'post_failed_attempt{len(attempts) + 1}')
    post.mkdir()
    dump(post / 'collector_binding.json', binding())
    with queries(post, f'unt9-run{number}-post') as q:
        after = {'targets': {s: target_state(q, f'{FQ_SCHEMA}.{t[2]}') for s, t in TARGETS.items()}}
        dump(post / 'state.json', after)
        dump(path / 'targets.json', targets(q, template))
        dump(path / 'write_scope.json', write_scope(history(q, execution['history_start'], post)))
    print(json.dumps({'returncode': execution['returncode'],
                      'write_scope_passed': load(path / 'write_scope.json')['passed'],
                      'rows': {s: len(v['rows']) for s, v in load(path / 'targets.json').items()}}, indent=2))


def compare():
    path = DEST / 'compare'
    fresh(path)
    oracle1 = load(DEST / 'oracle/run1/targets.json')
    oracle2 = load(DEST / 'oracle/run2/targets.json')
    runs = {n: load(DEST / f'dbt/run{n}/targets.json') for n in (1, 2)}
    tables = {}
    for session, (mapping, _, _, keys) in TARGETS.items():
        checks = {'oracle_dbt_run1': full_compare(oracle1[session], runs[1][session], keys),
                  'dbt_run1_run2': full_compare(runs[1][session], runs[2][session], keys),
                  'oracle_run2_dbt_run2': full_compare(oracle2[session], runs[2][session], keys)}
        dump(path / f'{mapping}.json', checks)
        tables[session] = {
            'first_load_parity': checks['oracle_dbt_run1']['equal'],
            'replay_stable': checks['dbt_run1_run2']['equal'],
            'rows': [checks['oracle_dbt_run1']['before_rows'], runs[1][session] and len(runs[1][session]['rows']),
                     len(runs[2][session]['rows'])],
            'duplicate_keys_run1': len(checks['oracle_dbt_run1']['duplicate_keys_after']),
            'duplicate_keys_run2': len(checks['dbt_run1_run2']['duplicate_keys_after']),
            'legacy_run2_equal_dbt_run2': checks['oracle_run2_dbt_run2']['equal'],
            'legacy_run2_rows': len(oracle2[session]['rows'])}
    oracle_sessions = {r['SESSION_INSTANCE_NAME']: r for r in load(DEST / 'oracle/run1/session_results.json')}
    dbt_sessions = {n: load(DEST / f'dbt/run{n}/sessions/workflow_result.json') for n in (1, 2)}
    alert_source = load(DEST / 'preflight/source_SECURITY_ALERT.json')
    severity = alert_source['columns'].index('SEVERITY_CD')
    key = alert_source['columns'].index('ALERT_ID')
    written = {r[0][1] for r in runs[2]['s_m_SFX_SECURITY_ALERT']['rows']}
    unrouted = [r for r in alert_source['rows'] if r[key][1] not in written]
    rejects = {'oracle_failed_rows': int(oracle_sessions['s_m_SFX_SECURITY_ALERT']['FAILED_ROWS']),
               'oracle_bad_lines': sum(len(v) for v in load(DEST / 'oracle/run1/rejects.json').values()),
               'dbt_unwritten_source_rows': len(unrouted),
               'dbt_unwritten_severities': sorted({r[severity][1] for r in unrouted})}
    scopes = {n: load(DEST / f'dbt/run{n}/write_scope.json')['passed'] for n in (1, 2)}
    summary = {'tables': tables, 'rejects': rejects, 'write_scope_passed': scopes,
               'oracle_sessions': {k: [v['RUN_STATUS'], v['SUCCESSFUL_ROWS'], v['FAILED_ROWS']]
                                   for k, v in oracle_sessions.items()},
               'dbt_sessions': {n: v['sessions'] for n, v in dbt_sessions.items()},
               'summary_replay_contract': 'd-summary-replay: first-load legacy parity plus approved idempotent '
                                          'replay; legacy second run appends and is not claimed',
               'archive': 'excluded: disabled in the canonical PowerCenter workflow, so daily enablement is not '
                          'authorized'}
    passed = (all(t['first_load_parity'] and t['replay_stable'] and not t['duplicate_keys_run1']
                  and not t['duplicate_keys_run2'] for t in tables.values())
              and rejects['oracle_failed_rows'] == rejects['dbt_unwritten_source_rows'] == 3
              and all(scopes.values())
              and all(v['status'] == 'SUCCEEDED' for v in dbt_sessions.values()))
    summary['passed'] = passed
    dump(path / 'summary.json', summary)
    print(json.dumps(summary, indent=2))
    if not passed:
        raise ValueError('Workflow parity/replay gate failed')


def task_history(q, since):
    names, rows = q.run(
        "SELECT NAME,STATE,QUERY_ID,GRAPH_RUN_GROUP_ID,RUN_ID,ROOT_TASK_ID,ATTEMPT_NUMBER,SCHEDULED_TIME,"
        "QUERY_START_TIME,COMPLETED_TIME,ERROR_CODE,ERROR_MESSAGE FROM TABLE(SFX_D1110_AFTER.INFORMATION_SCHEMA."
        f"TASK_HISTORY(SCHEDULED_TIME_RANGE_START=>TO_TIMESTAMP_LTZ('{since}'), RESULT_LIMIT=>10000)) "
        f"WHERE DATABASE_NAME='SFX_D1110_AFTER' AND SCHEMA_NAME='PC_AUDIT' AND STARTSWITH(NAME,'{TASK_PREFIX}') "
        "ORDER BY SCHEDULED_TIME")
    return [dict(zip(names, [cell(v) for v in r])) for r in rows]


def task_state(q, tasks, path, label):
    names, rows = q.run(f"SHOW TASKS LIKE '{TASK_PREFIX}%' IN SCHEMA SFX_D1110_AFTER.PC_AUDIT")
    shown = [dict(zip(names, [cell(v) for v in r])) for r in rows]
    described = {}
    for step in tasks.values():
        columns, desc = q.run('DESCRIBE TASK SFX_D1110_AFTER.PC_AUDIT.' + step['task'])
        described[step['task']] = [dict(zip(columns, [cell(v) for v in r])) for r in desc]
    dump(path / f'show_tasks_{label}.json', shown)
    dump(path / f'describe_tasks_{label}.json', described)
    return {r['NAME'][1]: r['STATE'][1] for r in shown}


def dag():
    """The single authorised live execution of the suspended audit Task DAG, then suspension."""
    import contextlib
    import io
    import yaml
    sys.path.insert(0, str(ROOT / 'warehouse/snowflake'))
    import pc_dag
    from sfx_conn import connect
    path = DEST / 'dag'
    fresh(path)
    cert = DEST / 'dag_generate/audit_unt9.yml'
    committed = yaml.safe_load((ROOT / 'warehouse/snowflake/pc_dag/audit.yml').read_text())
    if yaml.safe_load(cert.read_text().replace(SCHEMA, 'PC_AUDIT')) != committed:
        raise ValueError('Certification DAG differs from the committed audit.yml beyond the target schema')
    shutil.copy2(cert, path / 'audit_unt9.yml')
    folder, root, tasks = pc_dag.load('audit', cert)
    if set(tasks) != {'START', 'STG_AUDIT_EVENT', 'AUDIT_EVENT', 'AUDIT_DAILY_SUMMARY', 'SECURITY_ALERT'}:
        raise ValueError('Unexpected audit DAG tasks')
    (path / 'ddl.sql').write_text('\n\n'.join(pc_dag.create_sql(folder, t, tasks) + ';' for t in tasks.values()))
    template = load(DEST / 'oracle/run1/targets.json')
    evidence_live.LIVE = path
    result = {'run_once': None}
    with connect('transform', 'pc_dag', extra_tag=dict(run='sfx-d1110', act='scale', step='unt9-dag',
                                                        folder=folder)) as conn, conn.cursor() as cur:
        q = evidence_live.Queries(cur)
        _, now = q.run('SELECT CURRENT_TIMESTAMP()::VARCHAR')
        since = now[0][0]
        prior = task_history(q, '2026-11-01 00:00:00 Z')
        if prior:
            raise ValueError('Audit tasks already have history; refusing a second DAG run')
        try:
            pc_dag.deploy(cur, folder, tasks)
            result['deployed_states'] = task_state(q, tasks, path, 'deployed')
            (path / 'EXECUTING').write_text(utc())
            output = io.StringIO()
            try:
                with contextlib.redirect_stdout(output):
                    pc_dag.run_once(cur, folder, root, tasks, timeout=600)
                result['run_once'] = 'SUCCEEDED'
            except Exception as error:
                result['run_once'] = 'FAILED: ' + str(error)
            (path / 'run_once_stdout.log').write_text(output.getvalue())
        finally:
            pc_dag.suspend(cur, folder, tasks)
            history = task_history(q, since)
            dump(path / 'task_history.json', history)
            result['final_states'] = task_state(q, tasks, path, 'final')
    names = {t['task'] for t in tasks.values()}
    graphs = {h['GRAPH_RUN_GROUP_ID'][1] for h in history}
    with queries(path / 'post', 'unt9-dag-post') as q:
        after = targets(q, template)
    dump(path / 'targets.json', after)
    run2 = load(DEST / 'dbt/run2/targets.json')
    checks = {s: full_compare(run2[s], after[s], TARGETS[s][3]) for s in TARGETS}
    dump(path / 'run2_vs_dag.json', checks)
    summary = {**result, 'graph_run_group_ids': sorted(graphs),
               'history': [[h['NAME'][1], h['STATE'][1], h['QUERY_ID'][1], h['RUN_ID'][1]] for h in history],
               'all_succeeded_once': sorted(h['NAME'][1] for h in history if h['STATE'][1] == 'SUCCEEDED') == sorted(names)
               and len(history) == len(names) and len(graphs) == 1,
               'all_suspended': set(result['final_states'].values()) == {'suspended'}
               and set(result['final_states']) == names,
               'targets_unchanged_vs_run2': {s: c['equal'] for s, c in checks.items()},
               'duplicate_keys': {s: len(c['duplicate_keys_after']) for s, c in checks.items()},
               'archive_task_present': any('ARCHIVE' in n for n in result['final_states'])}
    dump(path / 'summary.json', summary)
    print(json.dumps(summary, indent=2))
    if not (summary['run_once'] == 'SUCCEEDED' and summary['all_succeeded_once'] and summary['all_suspended']
            and all(summary['targets_unchanged_vs_run2'].values()) and not summary['archive_task_present']):
        raise ValueError('Task DAG certification failed')


def postflight():
    path = DEST / 'postflight'
    fresh(path)
    with queries(path, 'unt9-postflight') as q:
        state = {'control': controls(q, path), 'protected': protected(q, path), 'sources': sources(q, path)}
    pre = load(DEST / 'preflight/summary.json')
    state['unchanged'] = {'control': pre['control']['sha256'] == state['control']['sha256'],
                          'protected': pre['protected']['sha256'] == state['protected']['sha256'],
                          'protected_metadata': pre['protected']['metadata_sha256'] == state['protected']['metadata_sha256'],
                          'sources': pre['sources'] == {k: {**v, 'qid': pre['sources'][k]['qid']}
                                                        for k, v in state['sources'].items()}}
    dump(path / 'summary.json', state)
    print(json.dumps(state['unchanged'], indent=2))
    if not all(state['unchanged'].values()):
        raise ValueError('Protected state changed')


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('step', choices=['oracle', 'preflight', 'run1', 'run2', 'collect1', 'collect2', 'compare', 'dag', 'postflight'])
    args = parser.parse_args(argv)
    {'oracle': oracle, 'preflight': preflight, 'run1': lambda: replay(1), 'run2': lambda: replay(2),
     'collect1': lambda: collect(1), 'collect2': lambda: collect(2), 'compare': compare, 'dag': dag, 'postflight': postflight}[args.step]()


if __name__ == '__main__':
    main()
