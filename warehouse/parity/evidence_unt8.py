"""UNT-8 isolated oracle and opt-in, explicitly scoped Snowflake evidence."""
import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid

from . import evidence_live
from .evidence import BOOTSTRAP, ESTATE, OUT, cell, dump, full_compare, sha, snapshot
from .evidence_live import fetched, sf_type
from .evidence_unt3 import ReadOnlyQueries, control_snapshot, load, target_state
from .evidence_unt7 import parse_stats
from .harness import COMMENT, connection
from .inventory import ROOT

DEST = OUT / 'unt8'
FIXTURES = Path(__file__).parent / 'fixtures/unt8'
MAPPING = 'm_SFX_TEAM_MEMBER'
SCHEMA = 'SFX_D1110_AFTER.PC_FX_UNT8_TEAM_MEMBER'
TARGET = 'SFX_D1110_AFTER.PC_CONTENT.TEAM_MEMBER'
COLUMNS = ['TEAM_MEMBER_ID', 'TEAM_ID', 'USER_ID', 'ROLE_CD', 'JOINED_DT']
SUBJECTS = ('production', 'seeded', 'dup_key')
KEYS = ['TEAM_MEMBER_ID']
HISTORY = 'QUERY_ID,QUERY_TEXT,QUERY_TYPE,QUERY_TAG,START_TIME,END_TIME,EXECUTION_STATUS,ERROR_CODE,ERROR_MESSAGE'


def binding():
    dirty = subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True)
    if dirty:
        raise ValueError('Refusing execution with a dirty tree')
    paths = subprocess.check_output(['git', 'ls-files', 'warehouse', 'etl/informatica'],
                                    cwd=ROOT, text=True).splitlines()
    return {'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            'sha256': {p: sha(ROOT / p) for p in paths if (ROOT / p).is_file()}}


def fresh(path):
    implementation = binding()
    if path.exists():
        raise ValueError('Refusing to overwrite evidence: ' + str(path))
    path.mkdir(parents=True)
    dump(path / 'implementation.json', implementation)


def landing(subject):
    if subject not in SUBJECTS:
        raise ValueError('Unknown subject')
    return (ESTATE / 'tests/fixture/landing/users/TEAM_MEMBER/20261109.psv'
            if subject == 'production' else FIXTURES / (subject + '.psv'))


def read_psv(path):
    import csv
    with path.open(encoding='utf-8', newline='') as stream:
        rows = [[None if v == '' else v for v in row]
                for row in csv.reader(stream, delimiter='|', quoting=csv.QUOTE_NONE)]
    if any(len(r) != 5 for r in rows):
        raise ValueError('Expected five fields')
    return rows


def typed_input(subject):
    rows = read_psv(landing(subject))
    if subject == 'production':
        rows = [[int(v) if i < 3 and v is not None else date.fromisoformat(v)
                 if i == 4 and v is not None else v for i, v in enumerate(r)] for r in rows]
    return rows


def seed(subject):
    if subject == 'production':
        return []
    return [[int(v) if i < 3 and v is not None else date.fromisoformat(v)
             if i == 4 and v is not None else v.ljust(12) if i == 3 and v is not None else v for i, v in enumerate(r)]
            for r in read_psv(FIXTURES / (subject + '_target.psv'))]


def route(row):
    from runner import expr
    from runner.engine import coerce
    values = [None if v is None else str(v)[:n] for v, n in zip(row, (20, 20, 20, 12, 10))]
    try:
        values[:3] = [expr._to_integer(v) for v in values[:3]]
        values[3] = coerce(None if values[3] is None else values[3].strip(' ').upper(), 'string', 12)
        values[4] = None if values[4] is None else expr._to_date(values[4], 'YYYY-MM-DD').date()
    except expr.TransformationError:
        return {'classification': 'transformation_drop', 'values': values}
    rejected = (values[0] is None or any(v is not None and not -(2**63) <= v < 2**63 for v in values[:3])
                or (values[3] is not None and '\x00' in values[3]))
    return {'classification': 'writer_reject' if rejected else 'accepted', 'values': values}


def expected(initial, rows):
    state = {r[0]: list(r) for r in initial}
    for raw in rows:
        record = route(raw)
        if record['classification'] == 'accepted':
            row = record['values']
            state[row[0]] = [*row[:3], None if row[3] is None else row[3].ljust(12), row[4]]
    return list(state.values())


def writer_rejects(initial, rows):
    keys = {r[0] for r in initial}
    records = []
    for raw in rows:
        record = route(raw)
        values = record['values']
        if record['classification'] == 'writer_reject':
            update_error = any(v is not None and not -(2**63) <= v < 2**63 for v in values[1:3])
            update_error |= values[3] is not None and '\x00' in values[3]
            row_type = 1 if update_error or values[0] in keys else 0
            records.append(','.join([str(row_type)] + ['D,' + ('' if v is None else str(v)) for v in values]))
        elif record['classification'] == 'accepted':
            keys.add(values[0])
    return records


def table(subject):
    if subject not in SUBJECTS:
        raise ValueError('Unknown subject')
    return TARGET if subject == 'production' else SCHEMA + '.UNT8_FIXTURE_' + subject.upper()


def source(subject):
    return 'SFX_D1110_AFTER.PC_SRC.TEAM_MEMBER' if subject == 'production' else SCHEMA + '.' + subject.upper() + '_SOURCE'


def model(subject):
    return 'pc_content__team_member' if subject == 'production' else 'pc_content__unt8_fixture_' + subject


def equal(a, b, path):
    result = full_compare(a, b, KEYS)
    dump(path, result)
    if not result['equal']:
        raise ValueError('Snapshot mismatch: ' + str(path))
    return result


def oracle(subject):
    import psycopg
    path = DEST / 'oracle' / subject
    fresh(path)
    db = 'unt8_' + subject + '_' + uuid.uuid4().hex[:12]
    params = dict(host='127.0.0.1', port=int(os.environ.get('UNT8_PG_PORT', '55488')), user='postgres')
    root = (path / db).resolve()
    staged = root / 'landing/users/TEAM_MEMBER'
    staged.mkdir(parents=True)
    shutil.copy2(landing(subject), staged / '20261109.psv')
    command = [sys.executable, '-m', 'runner', 'startsession', '-f', 'SFX_CONTENT', '-w',
               'wf_SFX_CONTENT_DAILY', 's_m_SFX_TEAM_MEMBER']
    env = {k: v for k, v in os.environ.items() if not k.startswith(('SNOWFLAKE_', 'TD_'))}
    env.update(TD_HOST=params['host'], TD_PORT=str(params['port']), TD_USER='postgres', TD_PASSWORD='',
               TD_DB=db, PMROOTDIR=str(root), LANDING_DIR=str(root / 'landing'))
    with psycopg.connect(dbname='postgres', autocommit=True, **params) as admin:
        admin.execute('CREATE DATABASE ' + db)
        try:
            with psycopg.connect(dbname=db, autocommit=True, **params) as pg:
                pg.execute(BOOTSTRAP.read_text())
                if seed(subject):
                    with pg.cursor() as cursor:
                        cursor.executemany('INSERT INTO sfx_users.team_member VALUES (%s,%s,%s,%s,%s)', seed(subject))
                initial = snapshot(pg, 'sfx_users.team_member')
                template = snapshot(pg, 'sfx_users.stg_team_member')
                if subject != 'production':
                    template['types'] = {c: ['character varying', 200, None, None, None] for c in COLUMNS}
                dump(path / 'initial_target.json', initial)
                dump(path / 'input.json', {**template, 'rows': [[cell(v) for v in r] for r in typed_input(subject)]})
                dump(path / 'lineage.json', {'command': command, 'landing_sha256': sha(landing(subject)),
                                           'database': db, 'implementation': binding()})
                summaries = []
                for number in (1, 2):
                    dest = path / f'run{number}'
                    fresh(dest)
                    result = subprocess.run(command, cwd=ESTATE, env=env, capture_output=True, text=True)
                    (dest / 'stdout_stderr.log').write_text(result.stdout + result.stderr)
                    for folder in ('SessLogs', 'BadFiles'):
                        if (root / folder).exists():
                            shutil.copytree(root / folder, dest / folder)
                    shutil.copy2(root / 'REP_SESS_LOG.psv', dest / 'REP_SESS_LOG.psv')
                    import csv
                    with (root / 'REP_SESS_LOG.psv').open() as stream:
                        session = list(csv.DictReader(stream, delimiter='|'))[-1]
                    dump(dest / 'session_results.json', session)
                    dump(dest / 'writer_stats.json', parse_stats(next((dest / 'SessLogs').glob('*.log')).read_text()))
                    actual = snapshot(pg, 'sfx_users.team_member')
                    dump(dest / 'target.json', actual)
                    want = {**initial, 'rows': sorted([[cell(v) for v in r]
                            for r in expected(seed(subject), read_psv(landing(subject)))], key=json.dumps)}
                    equal(want, actual, dest / 'expected_comparison.json')
                    bad = [line for f in (root / 'BadFiles').glob('*.bad') for line in f.read_text().splitlines()]
                    dump(dest / 'rejects.json', bad)
                    counts = Counter(route(r)['classification'] for r in read_psv(landing(subject)))
                    prior = seed(subject) if number == 1 else expected(seed(subject), read_psv(landing(subject)))
                    if (Counter(bad) != Counter(writer_rejects(prior, read_psv(landing(subject))))
                            or result.returncode or session['RUN_STATUS'] != 'SUCCEEDED'
                            or int(session['FAILED_SOURCE_ROWS']) != counts['transformation_drop']):
                        raise ValueError('Unexpected oracle rejects/status')
                    summary = dict(subject=subject, run=number, rows=len(actual['rows']),
                                   rejects=len(bad), drops=counts['transformation_drop'], returncode=result.returncode)
                    dump(dest / 'summary.json', summary)
                    summaries.append(summary)
                equal(load(path / 'run1/target.json'), load(path / 'run2/target.json'), path / 'replay.json')
                dump(path / 'summary.json', {'runs': summaries, 'run1_equals_run2': True})
                print(json.dumps({'runs': summaries, 'run1_equals_run2': True}))
        finally:
            admin.execute('DROP DATABASE ' + db + ' WITH (FORCE)')


@contextmanager
def queries(path, step, workload='parity'):
    previous = evidence_live.LIVE
    evidence_live.LIVE = path
    try:
        with connection(workload, step, MAPPING) as conn, conn.cursor() as cursor:
            yield ReadOnlyQueries(cursor)
    finally:
        evidence_live.LIVE = previous


def protected(q, path):
    _, relations = q.run("SELECT TABLE_SCHEMA,TABLE_NAME FROM SFX_D1110_AFTER.INFORMATION_SCHEMA.TABLES "
                        "WHERE TABLE_SCHEMA IN ('PC_CONTENT','PC_AUDIT','PC_BILLING') "
                        "OR STARTSWITH(TABLE_SCHEMA,'PC_FX_') "
                        "OR TABLE_SCHEMA LIKE '%FIXTURE%'")
    values = {}
    for schema, name in sorted(relations):
        relation = 'SFX_D1110_AFTER.' + schema + '.' + name
        if relation == TARGET or schema == SCHEMA.split('.')[1]:
            continue
        if not re.fullmatch(r'[A-Z0-9_]+', schema + name):
            raise ValueError('Unsafe protected identifier')
        columns, rows = q.run('SELECT * FROM ' + relation)
        _, types = q.run('DESCRIBE TABLE ' + relation)
        values[relation] = {'columns': columns, 'types': [[cell(v) for v in r] for r in types],
                            'rows': sorted([[cell(v) for v in r] for r in rows], key=json.dumps)}
    for name, count in [('LOGIN_EVENT', 412), ('ROLE_GRANT', 149)]:
        if len(values['SFX_D1110_AFTER.PC_CONTENT.' + name]['rows']) != count:
            raise ValueError('Protected row count changed: ' + name)
    required = {'PC_CONTENT.' + name for name in ('LOGIN_EVENT', 'ROLE_GRANT', 'STG_APP_USER', 'APP_USER',
                                                'STG_DOCUMENT', 'DOCUMENT', 'DOC_SHARE')}
    required |= {'PC_AUDIT.' + name for name in ('STG_AUDIT_EVENT', 'AUDIT_EVENT', 'AUDIT_EVENT_ARCHIVE',
                                              'AUDIT_DAILY_SUMMARY', 'SECURITY_ALERT')}
    if not {'SFX_D1110_AFTER.' + name for name in required} <= values.keys():
        raise ValueError('Required protected target missing')
    dump(path / 'protected.json', values)
    dump(path / 'protected_sha256.json', {'sha256': sha(path / 'protected.json'), 'relations': list(values)})
    return values


def controls(q, path):
    result = control_snapshot(q, path)
    if result['row_count'] != 20:
        raise ValueError('Expected 20 control rows')
    dump(path / 'control_sha256.json', result)
    return result


def unchanged(q, path):
    controls(q, path)
    protected(q, path)
    for name in ('control.json', 'protected.json'):
        if (path / name).read_bytes() != (DEST / 'preflight' / name).read_bytes():
            raise ValueError('Protected/control state changed: ' + name)


def preflight():
    path = DEST / 'preflight'
    fresh(path)
    with queries(path, 'unt8-preflight') as q:
        controls(q, path)
        protected(q, path)
        state = target_state(q, TARGET)
        _, exists = q.run("SELECT SCHEMA_NAME FROM SFX_D1110_AFTER.INFORMATION_SCHEMA.SCHEMATA "
                          "WHERE SCHEMA_NAME='PC_FX_UNT8_TEAM_MEMBER'")
        if state['exists'] or exists:
            raise ValueError('Production target or fixture schema already exists')
        template = load(DEST / 'oracle/production/input.json')
        actual = fetched(q, source('production'), template, source_loading=True)
        equal(template, actual, path / 'source_comparison.json')
        dump(path / 'source.json', actual)
        before = 'SFX_D1110_AFTER.PC_BEFORE.TEAM_MEMBER'
        state = target_state(q, before)
        dump(path / 'before_state.json', state)
        if state['exists']:
            dump(path / 'before.json', fetched(q, before, load(DEST / 'oracle/production/initial_target.json')))


def native(c):
    if c[0] == 'null':
        return None
    if c[0] in ('int', 'integer', 'number'):
        return int(c[1])
    if c[0] == 'date':
        return date.fromisoformat(c[1])
    return c[1]


def fixture_load():
    path = DEST / 'fixture_load'
    fresh(path)
    if binding() != load(DEST / 'preflight/implementation.json'):
        raise ValueError('Implementation changed since preflight')
    records = []
    with queries(path, 'unt8-fixture-load', 'load') as q:
        unchanged(q, path)
        _, existing = q.run("SELECT SCHEMA_NAME FROM SFX_D1110_AFTER.INFORMATION_SCHEMA.SCHEMATA "
                            "WHERE SCHEMA_NAME='PC_FX_UNT8_TEAM_MEMBER'")
        if existing:
            raise ValueError('Fixture schema already exists')
        def write(sql, values=None):
            if not sql.startswith(('CREATE SCHEMA ' + SCHEMA + ' COMMENT', 'CREATE TABLE ' + SCHEMA + '.',
                                   'INSERT INTO ' + SCHEMA + '.')):
                raise ValueError('Out-of-scope fixture write')
            if values:
                q.cursor.executemany(sql, values)
            else:
                q.cursor.execute(sql)
            records.append({'sql': sql, 'qid': q.cursor.sfqid})
        write(f"CREATE SCHEMA {SCHEMA} COMMENT='{COMMENT}'")
        for subject in SUBJECTS[1:]:
            for relation, filename in [(source(subject), 'input.json'), (table(subject), 'initial_target.json')]:
                snap = load(DEST / 'oracle' / subject / filename)
                ddl = ', '.join(c + ' ' + sf_type(snap['types'][c]) for c in COLUMNS)
                if filename == 'initial_target.json':
                    ddl = ddl.replace('TEAM_MEMBER_ID NUMBER(38,0)', 'TEAM_MEMBER_ID NUMBER(38,0) NOT NULL')
                    ddl += ', PRIMARY KEY (TEAM_MEMBER_ID)'
                write(f"CREATE TABLE {relation} ({ddl}) COMMENT='{COMMENT}'")
                values = [[native(c) for c in row] for row in snap['rows']]
                if values:
                    write(f"INSERT INTO {relation} ({','.join(COLUMNS)}) VALUES (%s,%s,%s,%s,%s)", values)
                equal(snap, fetched(q, relation, snap, source_loading=filename == 'input.json'),
                      path / (relation.split('.')[-1] + '_readback.json'))
    dump(path / 'writes.json', records)


def identity(q, relation):
    state = target_state(q, relation)
    metadata = state['metadata']
    _, ids = q.run("SELECT TABLE_ID FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES "
                  f"WHERE TABLE_CATALOG='SFX_D1110_AFTER' AND TABLE_SCHEMA='{relation.split('.')[1]}' "
                  f"AND TABLE_NAME='{relation.split('.')[2]}' AND DELETED IS NULL")
    return {'exists': state['exists'], 'created': metadata[0]['CREATED'] if metadata else None,
            'table_id': [str(r[0]) for r in ids],
            'table_id_limitation': 'ACCOUNT_USAGE may lag; no numeric identity claim when absent'}


def history(q, start=None, end=None):
    bounds = f"END_TIME_RANGE_START=>'{start}'::TIMESTAMP_LTZ,END_TIME_RANGE_END=>'{end}'::TIMESTAMP_LTZ," if start else ''
    _, rows = q.run(f'SELECT {HISTORY} FROM TABLE(SFX_D1110_AFTER.INFORMATION_SCHEMA.QUERY_HISTORY_BY_USER('
                   + bounds + "RESULT_LIMIT=>10000)) ORDER BY START_TIME")
    if len(rows) >= 10000:
        raise ValueError('History truncated')
    return rows


def intervening(rows, relation):
    writes, failed = [], []
    for row in rows:
        if row[6] != 'SUCCESS':
            failed.append(row)
        elif row[2] not in ('SELECT', 'SHOW', 'DESCRIBE') and relation.split('.')[-1] in (row[1] or '').upper():
            writes.append(row)
    return writes, failed


def write_scope(rows):
    writes, failed, unparsed = [], [], []
    for row in rows:
        if MAPPING not in (row[3] or ''):
            continue
        if row[6] != 'SUCCESS':
            failed.append(row)
            continue
        if row[2] in ('SELECT', 'SHOW', 'DESCRIBE', 'USE', 'ALTER_SESSION', 'BEGIN_TRANSACTION', 'COMMIT', 'ROLLBACK'):
            continue
        sql = re.sub(r'/\*.*?\*/', '', row[1] or '', flags=re.S).replace('"', '').strip().upper()
        if re.match(r'^(USE |ALTER SESSION |BEGIN|COMMIT|ROLLBACK)', sql):
            continue
        match = re.search(r'(?:MERGE INTO|INSERT INTO|UPDATE|DELETE FROM|COMMENT ON TABLE|'
                          r'(?:CREATE(?: OR REPLACE)?(?: TEMPORARY| TEMP| TRANSIENT)?|ALTER|DROP) (?:TABLE|VIEW|SCHEMA))'
                          r'\s+(?:IF (?:NOT )?EXISTS\s+)?([A-Z0-9_.]+)', sql)
        if not match:
            unparsed.append(row)
            continue
        relation = match.group(1)
        allowed = relation == TARGET or relation.startswith(TARGET + '__DBT_') or relation == SCHEMA or relation.startswith(SCHEMA + '.')
        writes.append({'qid': row[0], 'relation': relation, 'allowed': allowed})
    return {'writes': writes, 'failed_statements': [[cell(v) for v in r] for r in failed],
            'unparsed_successful_statements': [[cell(v) for v in r] for r in unparsed],
            'passed': not unparsed and all(r['allowed'] for r in writes),
            'limitation': 'Current-user mapping-tagged history only; not an account-wide audit'}


def run(subject, number):
    path = DEST / subject / f'run{number}'
    fresh(path)
    pre = load(DEST / 'preflight/implementation.json')
    if binding() != pre:
        raise ValueError('Implementation changed since preflight')
    env = os.environ.copy()
    if subject != 'production':
        env['SFX_UNT8_TEAM_FIXTURE'] = '1'
    step = f'unt8-{subject}-run{number}'
    command = [sys.executable, str(ROOT / 'warehouse/snowflake/run_dbt.py'), 'build',
               '--select', model(subject), '--step', step, '--mapping', MAPPING]
    with queries(path, step + '-readback') as q:
        unchanged(q, path)
        input_template = load(DEST / 'oracle' / subject / 'input.json')
        equal(input_template, fetched(q, source(subject), input_template, source_loading=True), path / 'source_comparison.json')
        template = load(DEST / 'oracle' / subject / 'initial_target.json')
        before_id = identity(q, table(subject))
        if number == 2:
            equal(load(DEST / subject / 'run1/target.json'), fetched(q, table(subject), template), path / 'between_snapshot.json')
        elif before_id['exists']:
            equal(template, fetched(q, table(subject), template), path / 'initial_comparison.json')
        start = datetime.now(timezone.utc).isoformat()
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
        end = datetime.now(timezone.utc).isoformat()
        (path / 'stdout_stderr.log').write_text(result.stdout + result.stderr)
        for filename in ('target/run_results.json', 'target/manifest.json', 'logs/dbt.log'):
            artifact = ROOT / 'warehouse/dbt' / filename
            if artifact.exists():
                shutil.copy2(artifact, path / artifact.name)
        after_id = identity(q, table(subject))
        if before_id['exists'] and (before_id['created'] != after_id['created'] or
                                   (before_id['table_id'] and after_id['table_id'] and before_id['table_id'] != after_id['table_id'])):
            raise ValueError('Target object recreated')
        dump(path / 'identity.json', {'before': before_id, 'after': after_id})
        dump(path / 'target.json', fetched(q, table(subject), template))
        dump(path / 'execution.json', dict(argv=command, start_utc=start, end_utc=end,
                                           returncode=result.returncode, implementation=binding()))
        rows = history(q)
        dump(path / 'history.json', [[cell(v) for v in r] for r in rows
                                    if MAPPING in (r[3] or '') and step in (r[3] or '')])
        if subject == 'dup_key':
            if not result.returncode or 'Division by zero' not in result.stdout + result.stderr:
                raise ValueError('Duplicate build did not fail closed')
            equal(template, load(path / 'target.json'), path / 'preservation.json')
        elif result.returncode:
            raise ValueError('dbt build failed')
        env['DBT_ENV_SECRET_SNOWFLAKE_PRIVATE_KEY'] = env['SNOWFLAKE_PRIVATE_KEY']
        env['DBT_SEND_ANONYMOUS_USAGE_STATS'] = 'false'
        env['SFX_QUERY_TAG'] = json.dumps(dict(run='sfx-d1110', mapping=MAPPING, step=step + '-rejects'))
        project = ROOT / 'warehouse/dbt'
        compile_argv = [str(Path(sys.executable).with_name('dbt')), 'compile', '--project-dir', str(project),
                        '--profiles-dir', str(project), '--select', 'unt8_team_member_rejects',
                        '--vars', json.dumps({'unt8_subject': subject})]
        compiled = subprocess.run(compile_argv, env=env, capture_output=True, text=True)
        (path / 'reject_compile.log').write_text(compiled.stdout + compiled.stderr)
        dump(path / 'reject_compile_execution.json', {'argv': compile_argv, 'returncode': compiled.returncode,
                                                      'implementation': binding()})
        if compiled.returncode:
            raise ValueError('Reject compile failed')
        sql = (project / 'target/compiled/sfx_warehouse/analyses/unt8_team_member_rejects.sql').read_text()
        (path / 'rejects.sql').write_text(sql)
        names, rows = q.run('SELECT * FROM (' + sql.strip().rstrip(';') + ')')
        dump(path / 'classified.json', {'columns': names, 'rows': [[cell(v) for v in r] for r in rows]})


def compare(subject):
    path = DEST / subject / 'comparison'
    fresh(path)
    one, two = [load(DEST / subject / f'run{n}/target.json') for n in (1, 2)]
    result = {'negative_not_parity': subject == 'dup_key', 'comparisons': []}
    result['comparisons'].append(equal(one, two, path / 'dbt_replay.json'))
    identities = [load(DEST / subject / f'run{n}/identity.json') for n in (1, 2)]
    if identities[0]['after']['created'] != identities[1]['before']['created']:
        raise ValueError('Target recreated between runs')
    known_ids = [state['table_id'] for capture in identities for state in capture.values() if state['table_id']]
    if known_ids and any(value != known_ids[0] for value in known_ids):
        raise ValueError('TABLE_ID changed')
    dump(path / 'identity_stability.json', identities)
    for n in (1, 2):
        oracle_path = DEST / 'oracle' / subject / f'run{n}'
        if subject != 'dup_key':
            result['comparisons'].append(equal(load(oracle_path / 'target.json'),
                                               one if n == 1 else two, path / f'parity{n}.json'))
        classified = load(DEST / subject / f'run{n}/classified.json')
        index = classified['columns'].index('CLASSIFICATION')
        actual = Counter(r[index][1] for r in classified['rows'])
        want = Counter(route(r)['classification'] for r in read_psv(landing(subject)))
        if actual != want:
            raise ValueError('Classification counts differ')
        expected_rows = Counter(json.dumps([cell(v) for v in r['values']]) for r in
                                map(route, read_psv(landing(subject))) if r['classification'] == 'writer_reject')
        indexes = [classified['columns'].index(c) for c in COLUMNS]
        actual_rows = Counter(json.dumps([r[i] for i in indexes]) for r in classified['rows']
                              if r[index][1] == 'writer_reject')
        if expected_rows != actual_rows:
            raise ValueError('Typed writer rejects differ')
        summary = load(oracle_path / 'summary.json')
        if summary['rejects'] != actual['writer_reject'] or summary['drops'] != actual['transformation_drop']:
            raise ValueError('Oracle rejects/drops differ')
        initial = seed(subject) if n == 1 else expected(seed(subject), read_psv(landing(subject)))
        if Counter(load(oracle_path / 'rejects.json')) != Counter(writer_rejects(initial, read_psv(landing(subject)))):
            raise ValueError('Oracle raw .bad rows differ')
    a, b = [load(DEST / subject / f'run{n}/execution.json') for n in (1, 2)]
    with queries(path, 'unt8-between-runs') as q:
        rows = history(q, a['end_utc'], b['start_utc'])
        writes, failed = intervening(rows, table(subject))
        dump(path / 'between_runs.json', {'writes': [[cell(v) for v in r] for r in writes],
                                         'failed': [[cell(v) for v in r] for r in failed],
                                         'limitation': 'Current-user history only; not an account-wide audit'})
        if writes:
            raise ValueError('Intervening writes')
    dump(path / 'summary.json', result)


def postflight():
    path = DEST / 'postflight'
    fresh(path)
    with queries(path, 'unt8-postflight') as q:
        unchanged(q, path)
        template = load(DEST / 'oracle/production/input.json')
        equal(template, fetched(q, source('production'), template, source_loading=True), path / 'source_comparison.json')
        before = 'SFX_D1110_AFTER.PC_BEFORE.TEAM_MEMBER'
        state = target_state(q, before)
        initial_state = load(DEST / 'preflight/before_state.json')
        if state['exists'] != initial_state['exists']:
            raise ValueError('PC_BEFORE existence changed')
        if state['exists']:
            template = load(DEST / 'preflight/before.json')
            equal(template, fetched(q, before, template), path / 'before_comparison.json')
        rows = history(q)
        dump(path / 'tagged_history.json', [[cell(v) for v in r] for r in rows if MAPPING in (r[3] or '')])
        result = write_scope(rows)
        dump(path / 'write_scope.json', result)
        if not result['passed']:
            raise ValueError('Unparsed or out-of-scope successful writes; review retained history')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['oracle', 'preflight', 'fixture-load', 'run', 'compare', 'postflight'])
    parser.add_argument('--subject', choices=SUBJECTS)
    parser.add_argument('--run', type=int, choices=[1, 2])
    args = parser.parse_args()
    binding()
    if args.command in ('oracle', 'run', 'compare') and not args.subject:
        parser.error('--subject is required')
    if args.command == 'run' and not args.run:
        parser.error('--run is required')
    if args.command == 'oracle':
        oracle(args.subject)
    elif args.command == 'preflight':
        preflight()
    elif args.command == 'fixture-load':
        fixture_load()
    elif args.command == 'run':
        run(args.subject, args.run)
    elif args.command == 'compare':
        compare(args.subject)
    else:
        postflight()


if __name__ == '__main__':
    main()
