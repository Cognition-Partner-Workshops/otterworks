"""Isolated security-alert oracle and explicitly scoped live evidence commands."""
import argparse
from collections import Counter
from contextlib import contextmanager
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import uuid

from . import evidence_live
from .evidence import BOOTSTRAP, ESTATE, OUT, cell, dump, full_compare, local_params, sha, snapshot
from .evidence_live import fetched, sf_type
from .evidence_unt3 import ReadOnlyQueries, adapter_query_ids, control_snapshot, load, target_state
from .harness import COMMENT, connection
from .inventory import ROOT

DEST = OUT / 'unt5'
FIXTURES = Path(__file__).parent / 'fixtures/unt5'
MAPPING = 'm_SFX_SECURITY_ALERT'
SCHEMA = 'SFX_D1110_AFTER.PC_AUDIT_UNT5_FIXTURE'
TARGET = 'SFX_D1110_AFTER.PC_AUDIT.SECURITY_ALERT'
COLUMNS = ['ALERT_ID', 'ACTOR_USER_ID', 'DOCUMENT_ID', 'ALERT_TS', 'SEVERITY_CD', 'STATUS_CD']
FROZEN_SHA = '508c54217e1b5019ec2c8876d407f268ec0c56aaa5b1ab50790eef74a44727ab'
SCENARIOS = ('frozen', 'seeded', 'dup_within_route')
SUBJECTS = ('production', 'seeded', 'dup_within_route')
HISTORY_COLUMNS = 'QUERY_ID,QUERY_TEXT,QUERY_TYPE,QUERY_TAG,START_TIME,END_TIME,EXECUTION_STATUS,ERROR_CODE,ROWS_PRODUCED,WAREHOUSE_NAME,ROLE_NAME,SESSION_ID'


def implementation_hashes(values):
    return {k: v for k, v in values.items() if k != 'warehouse/parity/evidence_unt5.py'}


def history_capture(q, step):
    _, rows = q.run(f'SELECT {HISTORY_COLUMNS} FROM TABLE(SFX_D1110_AFTER.INFORMATION_SCHEMA.'
                    f"QUERY_HISTORY_BY_USER(RESULT_LIMIT=>10000)) WHERE TRY_PARSE_JSON(QUERY_TAG):step::string='{step}' ORDER BY START_TIME")
    if len(rows) >= 10000:
        raise ValueError('History truncated')
    return rows


def collect_target(q, subject, path):
    template = load(DEST / 'oracle' / scenario(subject) / 'initial_target.json')
    dump(path / 'target.json', fetched(q, target(subject), template))
    _, comments = q.run("SELECT COMMENT FROM SFX_D1110_AFTER.INFORMATION_SCHEMA.TABLES "
                       f"WHERE TABLE_SCHEMA='{target(subject).split('.')[1]}' AND TABLE_NAME='{target(subject).split('.')[2]}'")
    dump(path / 'comment.json', comments)
    if comments != [(COMMENT,)]:
        raise ValueError('Object comment mismatch')
    sql = compile_rejects(subject, path)
    names, rows = q.run('SELECT * FROM (' + sql.strip().rstrip(';') + ')')
    dump(path / 'rejects.json', {'columns': names, 'rows': [[cell(v) for v in r] for r in rows]})
    dump(path / 'bad_lines.json', [bad_line(int(r[0]), r[1:]) for r in rows])


def recovery():
    path = DEST / 'production/run1'
    pre = load(DEST / 'preflight/summary.json')
    if implementation_hashes(pre['hashes']) != implementation_hashes(hashes()):
        raise ValueError('Executed implementation changed')
    old = load(path / 'queries.json')
    failed = old[-1]
    step = failed['sql'].split("step::string='")[1].split("'")[0]
    with queries(DEST / 'recovery/production_run1', 'unt5-recovery-run1') as q:
        history = history_capture(q, step)
        model_qid = '01c8539e-030d-21f3-0035-065b001c424a'
        model_row = next(r for r in history if r[0] == model_qid)
        _, all_rows = q.run(f'SELECT {HISTORY_COLUMNS} FROM TABLE(SFX_D1110_AFTER.INFORMATION_SCHEMA.'
                           'QUERY_HISTORY_BY_USER(RESULT_LIMIT=>10000)) ORDER BY START_TIME')
        start = next(r[4] for r in all_rows if r[0] == pre['control']['qid'])
        window = [r for r in all_rows if r[4] >= start]
        foreign = [r for r in window if 'SECURITY_ALERT' in (r[1] or '').upper() and
                   r[2] not in ('SELECT', 'DESCRIBE', 'SHOW') and
                   json.loads(r[3] or '{}').get('step') != step]
        dump(DEST / 'recovery/window.json', {'rows': [[cell(v) for v in r] for r in window],
             'foreign_writes': [[cell(v) for v in r] for r in foreign]})
        if foreign or len(all_rows) >= 10000:
            raise ValueError('Cannot prove uncontaminated run1')
        collect_target(q, 'production', path)
        results = load(path / 'run_results.json')['results']
        execution = {'commit': pre['commit'], 'collected_commit': head(), 'step': step,
                     'start_utc': model_row[4].isoformat(), 'end_utc': max(r[5] for r in history).isoformat(),
                     'returncode': 0, 'recovered_after_collector_failure': failed,
                     'implementation_hashes_equal': True, 'executed_hashes': pre['hashes'], 'collected_hashes': hashes(),
                     'history': [[cell(v) for v in r] for r in history], 'query_ids': [r[0] for r in history],
                     'adapter_responses': [r.get('adapter_response') for r in results]}
        dump(path / 'execution.json', execution)



def head():
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()


def hashes():
    paths = [Path(__file__), *FIXTURES.glob('*.psv'),
             ROOT / 'warehouse/dbt/macros/pc_audit_security_alert.sql',
             ROOT / 'warehouse/dbt/analyses/unt5_security_alert_rejects.sql',
             ROOT / 'warehouse/dbt/models/pc/audit/pc_audit__security_alert.sql',
             ROOT / 'warehouse/dbt/models/pc/audit/unt5_security.yml']
    paths += list((ROOT / 'warehouse/dbt/models/pc/audit/unt5_fixture').glob('*.sql'))
    paths += list((ESTATE / 'runner').glob('*.py'))
    paths += [BOOTSTRAP, ESTATE / 'repository/SFX_AUDIT/mappings/m_SFX_SECURITY_ALERT.XML',
              ESTATE / 'repository/SFX_AUDIT/wf_SFX_AUDIT_DAILY.XML']
    paths += list((ESTATE / 'params').glob('*.par'))
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(paths)}


def landing(scenario):
    if scenario not in SCENARIOS:
        raise ValueError('Unknown scenario')
    if scenario == 'frozen':
        path = ESTATE / 'tests/fixture/landing/audit/SECURITY_ALERT/20261109.psv'
        if sha(path) != FROZEN_SHA:
            raise ValueError('Frozen landing hash changed')
        return path
    return FIXTURES / f'{scenario}.psv'


def read_psv(path):
    result = []
    with path.open(newline='') as stream:
        for row in csv.reader(stream, delimiter='|', quoting=csv.QUOTE_NONE):
            if len(row) != 6:
                raise ValueError('Expected six columns')
            result.append([None if v == '' else (int(v) if i < 3 else
                          datetime.fromisoformat(v) if i == 3 else v) for i, v in enumerate(row)])
    return result


def typed(rows, template):
    return {**template, 'rows': [[cell(v) for v in row] for row in rows]}


def route_rows(rows):
    result = []
    for row in rows:
        values = list(row)
        for i in (4, 5):
            values[i] = None if values[i] is None else values[i][:12].strip(' ').upper()[:12]
        route = ('critical' if values[4] in ('CRITICAL', 'HIGH') else
                 'standard' if values[4] in ('MEDIUM', 'LOW') else 'default')
        if route == 'critical' and values[5] == 'OPEN':
            values[5] = 'ESCALATED'
        result.append({'route': route, 'row_type': 3 if route == 'default' else
                       0 if values[0] is None else 1, 'values': values})
    return result


def bad_line(row_type, values):
    def value(v):
        return '' if v is None else str(v)
    return ','.join([str(row_type)] + ['D,' + value(v) for v in values])


def bad_multiset(lines):
    return dict(sorted(Counter(lines).items()))


def expected_target(initial, rows):
    state = {r[0]: list(r) for r in initial}
    branches = route_rows(rows)
    for route in ('critical', 'standard'):
        for r in branches:
            if r['route'] != route or r['row_type'] != 1:
                continue
            values = list(r['values'])
            for i in (4, 5):
                if values[i] is not None:
                    values[i] = values[i].ljust(12)
            state[values[0]] = values
    return list(state.values())


def expected_stats(initial, rows):
    keys = {r[0] for r in initial}
    stats = {}
    branches = route_rows(rows)
    for route, instance in zip(('critical', 'standard', 'default'),
                               ('SECURITY_ALERT', 'SECURITY_ALERT1', 'SECURITY_ALERT2')):
        counts = {'inserted': 0, 'updated': 0, 'deleted': 0, 'rejected': 0}
        for r in branches:
            if r['route'] != route:
                continue
            key = r['values'][0]
            if r['row_type'] != 1:
                counts['rejected'] += 1
            else:
                counts['updated' if key in keys else 'inserted'] += 1
                keys.add(key)
        stats[instance] = counts
    return stats


def native(c):
    kind, value = c
    if kind == 'null':
        return None
    if kind in ('number', 'decimal'):
        return int(value)
    if kind == 'timestamp':
        return datetime.fromisoformat(value)
    return value


def target(subject):
    if subject not in SUBJECTS:
        raise ValueError('Unknown subject')
    return TARGET if subject == 'production' else f'{SCHEMA}.UNT5_FIXTURE_{subject.upper()}'


def source(subject):
    return 'SFX_D1110_AFTER.PC_SRC.SECURITY_ALERT' if subject == 'production' else f'{SCHEMA}.{subject.upper()}_SOURCE'


def scenario(subject):
    return 'frozen' if subject == 'production' else subject


def model(subject):
    return 'pc_audit__security_alert' if subject == 'production' else 'pc_audit__unt5_fixture_' + subject


def fresh(path):
    if path.exists():
        raise ValueError('Never overwrite an evidence capture: ' + str(path))
    path.mkdir(parents=True)


def oracle(name):
    import psycopg
    path = DEST / 'oracle' / name
    fresh(path)
    params = local_params()
    db = 'unt5_' + name + '_' + uuid.uuid4().hex[:12]
    runroot = (path / db).resolve()
    runroot.mkdir()
    staged = runroot / 'landing/audit/SECURITY_ALERT'
    staged.mkdir(parents=True)
    shutil.copy2(landing(name), staged / '20261109.psv')
    command = [sys.executable, '-m', 'runner', 'startsession', '-f', 'SFX_AUDIT',
               '-w', 'wf_SFX_AUDIT_DAILY', 's_m_SFX_SECURITY_ALERT']
    env = {k: v for k, v in os.environ.items() if not k.startswith(('SNOWFLAKE_', 'TD_'))}
    env.update(TD_HOST=params['host'], TD_PORT=str(params['port']), TD_USER=params['user'],
               TD_PASSWORD=params['password'], TD_DB=db, PMROOTDIR=str(runroot),
               LANDING_DIR=str(runroot / 'landing'))
    with psycopg.connect(dbname='postgres', **params) as admin:
        admin.execute(f'CREATE DATABASE {db}')
        try:
            with psycopg.connect(dbname=db, **params) as pg:
                pg.execute(BOOTSTRAP.read_text())
                if name != 'frozen':
                    with pg.cursor() as cursor:
                        cursor.executemany('INSERT INTO sfx_audit.security_alert VALUES (%s,%s,%s,%s,%s,%s)',
                                           read_psv(FIXTURES / f'{name}_target.psv'))
                initial = snapshot(pg, 'SFX_AUDIT.SECURITY_ALERT')
                source_template = snapshot(pg, 'SFX_AUDIT.STG_SECURITY_ALERT')
                dump(path / 'initial_target.json', initial)
                dump(path / 'input.json', typed(read_psv(landing(name)), source_template))
                dump(path / 'lineage.json', {'commit': head(), 'hashes': hashes(), 'landing': str(landing(name)),
                     'landing_sha256': sha(landing(name)), 'command': command,
                     'env_overrides': {k: v for k, v in env.items() if k in
                                       ('TD_HOST', 'TD_PORT', 'TD_DB', 'PMROOTDIR', 'LANDING_DIR')}})
                for number in (1, 2):
                    dest = path / f'run{number}'
                    dest.mkdir()
                    with (dest / 'stdout_stderr.log').open('w') as output:
                        rc = subprocess.run(command, cwd=ESTATE, env=env, stdout=output,
                                            stderr=subprocess.STDOUT).returncode
                    dump(dest / 'target.json', snapshot(pg, 'SFX_AUDIT.SECURITY_ALERT'))
                    rejects = []
                    for bad in sorted((runroot / 'BadFiles').glob('*.bad')):
                        shutil.copy2(bad, dest / bad.name)
                        rejects.append({'name': bad.name, 'rows': bad.read_text().splitlines()})
                    dump(dest / 'rejects.json', rejects)
                    shutil.copytree(runroot / 'SessLogs', dest / 'SessLogs')
                    shutil.copy2(runroot / 'REP_SESS_LOG.psv', dest / 'REP_SESS_LOG.psv')
                    with (runroot / 'REP_SESS_LOG.psv').open() as stream:
                        sessions = list(csv.DictReader(stream, delimiter='|'))
                    dump(dest / 'session_results.json', sessions[-1:])
                    stats = parse_stats(next((dest / 'SessLogs').glob('*.log')).read_text())
                    dump(dest / 'writer_stats.json', stats)
                    summary = {'scenario': name, 'run': number, 'returncode': rc,
                               'rows': len(load(dest / 'target.json')['rows']),
                               'written': sessions[-1]['SUCCESSFUL_ROWS'], 'rejected': sessions[-1]['FAILED_ROWS']}
                    dump(dest / 'summary.json', summary)
                    expected = typed(expected_target([[native(c) for c in r] for r in initial['rows']],
                                                     read_psv(landing(name))), initial)
                    require_equal(expected, load(dest / 'target.json'), dest / 'expected_target_comparison.json')
                    expected_bad = [bad_line(r['row_type'], r['values']) for r in route_rows(read_psv(landing(name)))
                                    if r['row_type'] != 1]
                    if bad_multiset(expected_bad) != bad_multiset([line for f in rejects for line in f['rows']]):
                        raise ValueError('Runner rejects differ from expected routes')
                    print(json.dumps(summary))
                    if rc:
                        raise RuntimeError('Runner failed; capture retained')
        finally:
            admin.execute(f'DROP DATABASE {db} WITH (FORCE)')


def parse_stats(text):
    import re
    result = {}
    current = None
    for line in text.splitlines():
        if 'WRT_8036' in line:
            current = re.search(r'Instance Name: \[([^]]+)\]', line).group(1)
            result[current] = {'inserted': 0, 'updated': 0, 'deleted': 0, 'rejected': 0, 'lines': []}
        if current and any(code in line for code in ('WRT_8038', 'WRT_8041', 'WRT_8040', 'WRT_8350')):
            result[current]['lines'].append(line)
            if 'WRT_8350' in line:
                result[current]['rejected'] += int(line.rsplit(':', 1)[1].strip())
            else:
                counts = dict(re.findall(r'(Requested|Applied|Rejected|Affected): (\d+)', line))
                kind = 'inserted' if 'WRT_8038' in line else 'updated' if 'WRT_8041' in line else 'deleted'
                result[current][kind] += int(counts['Applied'])
                result[current]['rejected'] += int(counts['Rejected'])
    return result


@contextmanager
def queries(path, step, workload='parity'):
    path.mkdir(parents=True, exist_ok=True)
    previous = evidence_live.LIVE
    evidence_live.LIVE = path
    try:
        with connection(workload, step, MAPPING) as conn, conn.cursor() as cursor:
            yield ReadOnlyQueries(cursor)
    finally:
        evidence_live.LIVE = previous


def require_equal(expected, actual, path):
    result = full_compare(expected, actual, ['ALERT_ID'])
    dump(path, result)
    if not result['equal']:
        raise ValueError('Typed multiset mismatch: ' + str(path))
    return result


def frozen_input(q, path):
    template = load(DEST / 'oracle/frozen/input.json')
    expected = typed(read_psv(landing('frozen')), template)
    if sha(landing('frozen')) != FROZEN_SHA:
        raise ValueError('Frozen input changed')
    actual = fetched(q, source('production'), expected, source_loading=True)
    dump(path / 'source.json', actual)
    return require_equal(expected, actual, path / 'source_comparison.json')


def preflight():
    path = DEST / 'preflight'
    fresh(path)
    with queries(path, 'unt5-preflight') as q:
        result = {'commit': head(), 'hashes': hashes(), 'control': control_snapshot(q, path),
                  'input': frozen_input(q, path), 'target': target_state(q, TARGET)}
        template = load(DEST / 'oracle/frozen/initial_target.json')
        if result['target']['exists']:
            actual = fetched(q, TARGET, template)
            dump(path / 'initial_target.json', actual)
            require_equal(template, actual, path / 'initial_target_comparison.json')
        before = 'SFX_D1110_AFTER.PC_BEFORE.SECURITY_ALERT'
        result['before'] = target_state(q, before)
        if result['before']['exists']:
            expected = load(DEST / 'oracle/frozen/run1/target.json')
            actual = fetched(q, before, expected)
            dump(path / 'before.json', actual)
            require_equal(expected, actual, path / 'before_comparison.json')
        dump(path / 'summary.json', result)


def fixture_write(cursor, records, sql, values=None):
    import re
    prefix = re.escape(SCHEMA)
    if not re.match(rf'^(CREATE SCHEMA {prefix} COMMENT|CREATE TABLE {prefix}\.\w+ \(|INSERT INTO {prefix}\.\w+ \()', sql):
        raise ValueError('Fixture writes must stay in the new UNT-5 schema')
    if values is None:
        cursor.execute(sql)
    else:
        cursor.executemany(sql, values)
    records.append({'sql': sql, 'qid': cursor.sfqid, 'rows': len(values) if values else None})


def fixture_load():
    path = DEST / 'fixture_load'
    fresh(path)
    records = []
    with queries(path, 'unt5-fixture-load', workload='load') as q:
        _, existing = q.run("SELECT SCHEMA_NAME FROM SFX_D1110_AFTER.INFORMATION_SCHEMA.SCHEMATA "
                            "WHERE SCHEMA_NAME='PC_AUDIT_UNT5_FIXTURE'")
        if existing:
            raise ValueError('Fixture schema exists; refusing to overwrite')
        fixture_write(q.cursor, records, f"CREATE SCHEMA {SCHEMA} COMMENT='{COMMENT}'")
        for name in SCENARIOS[1:]:
            for relation, filename in ((source(name), 'input.json'), (target(name), 'initial_target.json')):
                snap = load(DEST / 'oracle' / name / filename)
                ddl = ', '.join(c + ' ' + (sf_type(snap['types'][c]).replace('(9)', '(0)')
                               if filename == 'input.json' else sf_type(snap['types'][c])) for c in COLUMNS)
                if filename == 'initial_target.json':
                    ddl += ', PRIMARY KEY (ALERT_ID)'
                    ddl = ddl.replace('ALERT_ID NUMBER(38,0)', 'ALERT_ID NUMBER(38,0) NOT NULL', 1)
                fixture_write(q.cursor, records, f"CREATE TABLE {relation} ({ddl}) COMMENT='{COMMENT}'")
                values = [[native(c) for c in row] for row in snap['rows']]
                if values:
                    fixture_write(q.cursor, records, f"INSERT INTO {relation} ({', '.join(COLUMNS)}) "
                                  "VALUES (%s,%s,%s,%s,%s,%s)", values)
                actual = fetched(q, relation, snap, source_loading=filename == 'input.json')
                require_equal(snap, actual, path / f'{relation.split(".")[-1]}_comparison.json')
        dump(path / 'writes.json', records)


def dbt_env(subject):
    env = os.environ.copy()
    if subject != 'production':
        env['SFX_UNT5_SECURITY_FIXTURE'] = '1'
    return env


def compile_rejects(subject, path):
    from .harness import tag
    from sfx_conn import query_tag
    env = dbt_env(subject)
    env['DBT_ENV_SECRET_SNOWFLAKE_PRIVATE_KEY'] = env['SNOWFLAKE_PRIVATE_KEY']
    env['DBT_SEND_ANONYMOUS_USAGE_STATS'] = 'false'
    env['SFX_QUERY_TAG'] = query_tag('transform', 'unt5-reject-compile', tag('unt5-reject-compile', MAPPING))
    project = ROOT / 'warehouse/dbt'
    command = [str(Path(sys.executable).with_name('dbt')), 'compile', '--project-dir', str(project),
               '--profiles-dir', str(project), '--select', 'unt5_security_alert_rejects',
               '--vars', json.dumps({'unt5_subject': subject})]
    with (path / 'reject_compile.log').open('w') as output:
        subprocess.run(command, env=env, stdout=output, stderr=subprocess.STDOUT, check=True)
    compiled = project / 'target/compiled/sfx_warehouse/analyses/unt5_security_alert_rejects.sql'
    shutil.copy2(compiled, path / 'rejects.sql')
    return compiled.read_text()


def run(subject, number):
    pre = load(DEST / 'preflight/summary.json')
    if implementation_hashes(pre['hashes']) != implementation_hashes(hashes()):
        raise ValueError('Implementation changed since preflight')
    path = DEST / subject / f'run{number}'
    fresh(path)
    if number == 2 and not (path.parent / 'run1/execution.json').exists():
        raise ValueError('Run 1 must precede run 2')
    step = f'unt5-{subject}-run{number}-{uuid.uuid4().hex}'
    template = load(DEST / 'oracle' / scenario(subject) / 'initial_target.json')
    execution = {'commit': head(), 'step': step, 'start_utc': datetime.now(timezone.utc).isoformat(),
                 'command': [sys.executable, str(ROOT / 'warehouse/snowflake/run_dbt.py'), 'build',
                             '--select', model(subject), '--step', step, '--mapping', MAPPING]}
    with queries(path, step) as q:
        control_snapshot(q, path)
        if (path / 'control.json').read_bytes() != (DEST / 'preflight/control.json').read_bytes():
            raise ValueError('Control changed; stop before build')
        frozen_input(q, path)
        input_template = load(DEST / 'oracle' / scenario(subject) / 'input.json')
        actual_input = fetched(q, source(subject), input_template, source_loading=True)
        require_equal(input_template, actual_input, path / 'input_comparison.json')
        state = target_state(q, target(subject))
        initial = fetched(q, target(subject), template) if state['exists'] else {**template, 'rows': []}
        dump(path / 'initial_target.json', initial)
        expected_initial = template if number == 1 else load(path.parent / 'run1/target.json')
        require_equal(expected_initial, initial, path / 'initial_target_comparison.json')
        started = datetime.now(timezone.utc).timestamp()
        with (path / 'stdout_stderr.log').open('w') as output:
            rc = subprocess.run(execution['command'], cwd=ROOT, env=dbt_env(subject), stdout=output,
                                stderr=subprocess.STDOUT).returncode
        execution['returncode'] = rc
        execution['end_utc'] = datetime.now(timezone.utc).isoformat()
        dump(path / 'execution.json', execution)
        for relative in ('target/run_results.json', 'logs/dbt.log'):
            artifact = ROOT / 'warehouse/dbt' / relative
            if artifact.exists() and artifact.stat().st_mtime >= started:
                shutil.copy2(artifact, path / artifact.name)
        if (path / 'run_results.json').exists():
            execution['adapter_responses'] = [r.get('adapter_response') for r in load(path / 'run_results.json')['results']]
            execution['adapter_query_ids'] = adapter_query_ids(execution['adapter_responses'])
        history = history_capture(q, step)
        execution['dml_results'] = []
        for row in history:
            if row[2] == 'MERGE' and row[6] == 'SUCCESS':
                names, values = q.run(f"SELECT * FROM TABLE(RESULT_SCAN('{row[0]}'))")
                execution['dml_results'].append({'qid': row[0], 'columns': names, 'rows': values})
        execution['history'] = [[cell(v) for v in r] for r in history]
        execution['query_ids'] = [r[0] for r in history]
        if len(history) >= 10000:
            raise ValueError('Tagged query history truncated')
        dump(path / 'execution.json', execution)
        (path / 'dbt_transcript.txt').write_text('\n\n'.join(f'SQL: {r[1]}\nQID: {r[0]}' for r in history))
        actual = fetched(q, target(subject), template)
        dump(path / 'target.json', actual)
        if subject == 'dup_within_route':
            require_equal(initial, actual, path / 'unchanged_comparison.json')
            if rc == 0 or not any('Division by zero' in str(r) for r in execution['history'] +
                                 [load(path / 'run_results.json')]):
                raise ValueError('Duplicate fixture must fail specifically on the runtime guard')
        elif rc or not execution['query_ids'] or not (path / 'run_results.json').exists():
            raise ValueError('dbt build failed or evidence incomplete')
        collect_target(q, subject, path)


def comparisons(oracle1, oracle2, dbt1, dbt2, duplicate=False):
    pairs = {'oracle1_oracle2': (oracle1, oracle2), 'dbt1_dbt2': (dbt1, dbt2),
             'oracle1_dbt1': (oracle1, dbt1), 'oracle2_dbt2': (oracle2, dbt2)}
    result = {name: full_compare(a, b, ['ALERT_ID']) for name, (a, b) in pairs.items()}
    result['passed'] = all(r['equal'] and not r['duplicate_keys_before'] and not r['duplicate_keys_after']
                           for name, r in result.items() if not duplicate or name in ('oracle1_oracle2', 'dbt1_dbt2'))
    return result


def compare(subject):
    path = DEST / subject
    oracle_path = DEST / 'oracle' / scenario(subject)
    result = comparisons(*(load(p / 'target.json') for p in
                         (oracle_path / 'run1', oracle_path / 'run2', path / 'run1', path / 'run2')),
                         duplicate=subject == 'dup_within_route')
    branches = route_rows(read_psv(landing(scenario(subject))))
    result['branches'] = [{'route': r['route'], 'row_type': r['row_type'],
                           'values': [cell(v) for v in r['values']]} for r in branches]
    expected_bad = [bad_line(r['row_type'], r['values']) for r in branches if r['row_type'] != 1]
    result['rejects'] = {}
    result['stats'] = {}
    checks = []
    for n in (1, 2):
        raw = [line for f in load(oracle_path / f'run{n}/rejects.json') for line in f['rows']]
        actual = load(path / f'run{n}/bad_lines.json')
        typed_rejects = load(path / f'run{n}/rejects.json')
        expected_typed = [[cell(r['row_type'])] + [cell(v) for v in r['values']]
                          for r in branches if r['row_type'] != 1]
        typed_equal = Counter(map(json.dumps, expected_typed)) == Counter(map(json.dumps, typed_rejects['rows']))
        result['rejects'][str(n)] = {'oracle': bad_multiset(raw), 'dbt': bad_multiset(actual),
                                     'expected': bad_multiset(expected_bad), 'typed_equal': typed_equal,
                                     'equal': bad_multiset(raw) == bad_multiset(actual) == bad_multiset(expected_bad)}
        initial = load(oracle_path / ('initial_target.json' if n == 1 else 'run1/target.json'))
        expected_writers = expected_stats([[native(c) for c in r] for r in initial['rows']],
                                         read_psv(landing(scenario(subject))))
        actual_writers = load(oracle_path / f'run{n}/writer_stats.json')
        writer_equal = all(all(actual_writers.get(i, {}).get(k) == v for k, v in counts.items())
                           for i, counts in expected_writers.items())
        execution = load(path / f'run{n}/execution.json')
        merges = [r for r in execution['history'] if native(r[2]) == 'MERGE']
        dbt_initial = load(path / f'run{n}/initial_target.json')
        initial_keys = {native(r[0]) for r in dbt_initial['rows']}
        candidate_keys = {r['values'][0] for r in branches if r['row_type'] == 1}
        expected_merge = {'inserted': len(candidate_keys - initial_keys), 'updated': len(candidate_keys & initial_keys)}
        counts = [dict(zip(r['columns'], row)) for r in execution.get('dml_results', []) for row in r['rows']]
        actual_merge = {'inserted': sum(int(r.get('NUMBER OF ROWS INSERTED', 0)) for r in counts),
                        'updated': sum(int(r.get('NUMBER OF ROWS UPDATED', 0)) for r in counts)}
        if subject == 'dup_within_route':
            expected_merge = {'inserted': 0, 'updated': 0}
        # An absent production target is built with CTAS rather than MERGE on run 1.
        merge_equal = actual_merge == expected_merge if merges else (
            subject == 'dup_within_route' or (n == 1 and not initial_keys))
        checks.append(writer_equal and merge_equal)
        result['stats'][str(n)] = {'oracle_sessions': load(oracle_path / f'run{n}/session_results.json'),
                                   'oracle_writers': actual_writers, 'expected_writers': expected_writers,
                                   'writer_counts_equal': writer_equal,
                                   'dbt_adapter': execution.get('adapter_responses'),
                                   'dbt_merge': actual_merge, 'expected_merge': expected_merge,
                                   'merge_counts_equal': merge_equal,
                                   'note': 'Runner counts both cross-route operations; dbt merges the final STANDARD winner once. '
                                           'NULL-key rejects and DEFAULT rejects are excluded from the merge.'}
    a, b = [load(path / f'run{n}/execution.json') for n in (1, 2)]
    with queries(path / 'between_runs', 'unt5-between-runs') as q:
        _, history = q.run("SELECT QUERY_ID,QUERY_TEXT,QUERY_TYPE,QUERY_TAG,START_TIME,END_TIME,EXECUTION_STATUS "
                           "FROM TABLE(SFX_D1110_AFTER.INFORMATION_SCHEMA.QUERY_HISTORY_BY_USER("
                           f"END_TIME_RANGE_START=>'{a['end_utc']}'::TIMESTAMP_LTZ,"
                           f"END_TIME_RANGE_END=>'{b['start_utc']}'::TIMESTAMP_LTZ,RESULT_LIMIT=>10000)) ORDER BY START_TIME")
    writes = [r for r in history if r[2] not in ('SELECT', 'DESCRIBE', 'SHOW') and
              target(subject).split('.')[-1] in (r[1] or '').upper()]
    if len(history) >= 10000:
        raise ValueError('Query history truncated; cannot prove absence of intervening writes')
    result['between_runs'] = {'queries': len(history), 'writes': [[cell(v) for v in r] for r in writes]}
    result['passed'] = (result['passed'] and not writes and all(checks) and
                        all(r['equal'] and r['typed_equal'] for r in result['rejects'].values()))
    if subject == 'dup_within_route':
        result['intended_difference'] = 'Runner accepts ordered duplicate updates; dbt fails closed because PC_SRC has no order column.'
    dump(path / 'comparison.json', result)
    print(json.dumps({'subject': subject, 'passed': result['passed']}))
    if not result['passed']:
        raise ValueError('UNT-5 comparison failed')


def postflight():
    path = DEST / 'postflight'
    fresh(path)
    with queries(path, 'unt5-postflight') as q:
        result = control_snapshot(q, path)
    result['byte_identical'] = (path / 'control.json').read_bytes() == (DEST / 'preflight/control.json').read_bytes()
    dump(path / 'summary.json', result)
    if not result['byte_identical']:
        raise ValueError('Control changed')


def index():
    paths = sorted(p for p in DEST.rglob('*') if p.is_file() and p.name not in ('evidence_index.json', 'bundle.tar.gz'))
    dump(DEST / 'evidence_index.json', {'commit': head(), 'artifacts': [
        {'path': str(p.relative_to(DEST)), 'sha256': sha(p), 'commit': head()} for p in paths]})
    with tarfile.open(DEST / 'bundle.tar.gz', 'w:gz') as bundle:
        for p in paths + [DEST / 'evidence_index.json']:
            bundle.add(p, arcname=str(p.relative_to(DEST)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    sub = subs.add_parser('oracle')
    sub.add_argument('--scenario', choices=SCENARIOS, required=True)
    for name in ('preflight', 'fixture-load', 'postflight', 'index', 'recovery'):
        subs.add_parser(name)
    for name in ('run', 'compare'):
        sub = subs.add_parser(name)
        sub.add_argument('--subject', choices=SUBJECTS, required=True)
        if name == 'run':
            sub.add_argument('--run', type=int, choices=(1, 2), required=True)
    args = parser.parse_args()
    if args.command == 'oracle':
        oracle(args.scenario)
    elif args.command == 'run':
        run(args.subject, args.run)
    elif args.command == 'compare':
        compare(args.subject)
    else:
        {'preflight': preflight, 'fixture-load': fixture_load, 'postflight': postflight, 'index': index, 'recovery': recovery}[args.command]()


if __name__ == '__main__':
    main()
