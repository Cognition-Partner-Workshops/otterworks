"""UNT-4 daily summary and archive evidence. Only run/fixture-load write; never touches control rows."""
import argparse
from contextlib import contextmanager
import csv
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import uuid

from . import evidence_live
from .commands import relation
from .compare import normal
from .evidence import BOOTSTRAP, ESTATE, OUT, cell, dump, full_compare, replay_gate, scope, sha, snapshot
from .evidence_live import fetched, sf_type
from .evidence_unt3 import (ReadOnlyQueries, adapter_query_ids, control_snapshot, frozen_input, load,
                            target_state, utc)
from .harness import COMMENT, connection
from .inventory import ROOT

DEST = OUT / 'unt4'
MAPPINGS = ('m_SFX_AUDIT_DAILY_SUMMARY', 'm_SFX_AUDIT_EVENT_ARCHIVE')
UPSTREAM = ('m_SFX_STG_AUDIT_EVENT', 'm_SFX_AUDIT_EVENT')
ARCHIVE = MAPPINGS[1]
FIXTURE_SCHEMA = 'SFX_D1110_AFTER.PC_AUDIT_UNT4_FIXTURE'
FIXTURES = {'empty': 'pc_audit__unt4_fixture_archive_empty', 'history': 'pc_audit__unt4_fixture_archive_history'}
SEQ_KEY = 'SFX_AUDIT.m_SFX_AUDIT_EVENT_ARCHIVE.SEQ_AUDIT_ARCHIVE'
HISTORY_NEXT = 10
WRITE = re.compile(r'^(CREATE (SCHEMA IF NOT EXISTS {0} |TABLE {0}\.)|INSERT INTO {0}\.)'.format(
    re.escape(FIXTURE_SCHEMA)), re.I)


def owned(mapping):
    if mapping not in MAPPINGS:
        raise ValueError('UNT-4 owns only the daily summary and archive mappings')
    return next(r for r in scope() if r['mapping'] == mapping)


def oracle(mapping):
    return load(OUT / mapping / 'oracle1/target.json')


def git_head():
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()


def implementation_hashes():
    paths = [Path(__file__), Path(__file__).parent / 'mappings/sfx_audit.yml',
             ROOT / 'warehouse/dbt/macros/pc_audit_event_archive.sql']
    paths += sorted((ROOT / 'warehouse/dbt/models/pc/audit').rglob('*'))
    return {str(p.relative_to(ROOT)): sha(p) for p in paths if p.is_file()}


@contextmanager
def queries(path, step):
    path.mkdir(parents=True, exist_ok=True)
    previous = evidence_live.LIVE
    evidence_live.LIVE = path
    try:
        with connection('parity', step) as conn, conn.cursor() as cursor:
            yield ReadOnlyQueries(cursor)
    finally:
        evidence_live.LIVE = previous


def utc_date(q):
    _, rows = q.run("SELECT CONVERT_TIMEZONE('UTC', CURRENT_TIMESTAMP())::DATE")
    return rows[0][0].isoformat()


def require_equal(expected, actual, keys, path):
    result = full_compare(expected, actual, keys)
    dump(path, result)
    if not result['equal']:
        raise ValueError('Full multiset mismatch: ' + str(path))
    return {'equal': True, 'rows': len(actual['rows']), 'duplicate_keys': len(result['duplicate_keys_after'])}


def empty_like(template):
    return dict(columns=template['columns'], types=template['types'], rows=[])


# ---- isolated runner fixture -------------------------------------------------------------------

def fixture_rows(today):
    cutoff = datetime.combine(today - timedelta(days=2555), datetime.min.time())
    recent_cutoff = datetime.combine(today - timedelta(days=730), datetime.min.time())
    s = timedelta(seconds=1)
    rows = [  # EVENT_ID order deliberately differs from EVENT_TS order
        (91000001, 500001, 2000001, 10101, cutoff - timedelta(days=400, hours=-10, minutes=-15), 'DOC_VIEW', 'Opened in browser'),
        (91000002, 500002, 2000002, 10102, cutoff - s, 'DOC_EXPORT', 'Boundary: one second before cutoff'),
        (91000003, 500003, 2000003, 10103, cutoff, 'DOC_SHARE', 'Boundary: exactly at cutoff'),
        (91000004, 500004, 2000004, 10104, cutoff + s, 'DOC_VIEW', 'Boundary: one second after cutoff'),
        (91000005, 500005, 2000005, 10105, None, 'DOC_VIEW', 'Null timestamp'),
        (91000006, None, None, None, cutoff - timedelta(days=30), None, None),
        (91000007, 500007, 2000007, 10107, cutoff - timedelta(days=10, hours=-8), 'DOC_DELETE', 'Deleted by owner'),
        (91000008, 500008, 0, 0, cutoff - timedelta(days=9), 'DOC_EXPORT', '  padded details  '),
        (91000009, 500009, 2000009, 10109, datetime.combine(today - timedelta(days=1), datetime.min.time()), 'DOC_VIEW', 'Recent'),
        (91000010, 500010, 2000010, 10110, recent_cutoff - timedelta(days=10), 'DOC_VIEW', 'Older than 730 but not 2555 days'),
        (91000011, 500011, 2000011, 10111, datetime(2001, 1, 1), 'DOC_SHARE', 'Oldest event has a late EVENT_ID'),
        (91000012, 500012, 2000012, 10112, cutoff - timedelta(days=2, seconds=1), 'DOC_VIEW', 'x' * 160),
        (91000013, 500013, 2000013, 10113, cutoff - timedelta(days=3), '', ''),
    ]
    history = [
        (7, 400007, 1900007, datetime(2015, 3, 1, 9, 30), 'DOC_VIEW', 'Prior archive run'),
        (8, None, 1900008, datetime(2015, 3, 2), 'DOC_SHARE', None),
        (9, 400009, 1900009, datetime(2015, 3, 3, 23, 59, 59), 'DOC_EXPORT', ' kept whitespace '),
    ]
    return cutoff, rows, history


def runner_fixture(scenario):
    import psycopg
    path = DEST / 'fixture' / scenario / 'runner'
    if path.exists():
        raise ValueError('Never overwrite a runner fixture capture')
    params = dict(host='127.0.0.1', port=os.environ['TD_PORT'], user='postgres', password='', autocommit=True)
    db = 'unt4_fixture_' + scenario + '_' + uuid.uuid4().hex[:8]
    runroot = (path / db).resolve()
    runroot.mkdir(parents=True)
    with psycopg.connect(dbname='postgres', **params) as admin:
        admin.execute(f'CREATE DATABASE {db}')
        try:
            with psycopg.connect(dbname=db, **params) as pg:
                pg.execute(BOOTSTRAP.read_text())
                tz, today = pg.execute("SELECT current_setting('TimeZone'), CURRENT_DATE").fetchone()
                cutoff, rows, history = fixture_rows(today)
                with pg.cursor() as c:
                    c.executemany('INSERT INTO sfx_audit.audit_event VALUES (%s,%s,%s,%s,%s,%s,%s)', rows)
                    if scenario == 'history':
                        c.executemany('INSERT INTO sfx_audit.audit_event_archive VALUES (%s,%s,%s,%s,%s,%s)', history)
                storage = runroot / 'Storage'
                storage.mkdir()
                if scenario == 'history':
                    (storage / 'sequence_values.json').write_text(json.dumps({SEQ_KEY: HISTORY_NEXT}))
                initial = {'database': db, 'timezone': tz, 'current_date': today.isoformat(),
                           'cutoff_2555': cutoff.isoformat(), 'archive_days': owned(ARCHIVE)['parameters']['$$ARCHIVE_DAYS'],
                           'source': snapshot(pg, 'SFX_AUDIT.AUDIT_EVENT'),
                           'target': snapshot(pg, 'SFX_AUDIT.AUDIT_EVENT_ARCHIVE'),
                           'sequence_storage': json.loads((storage / 'sequence_values.json').read_text())
                           if scenario == 'history' else {}}
                dump(path / 'initial_state.json', initial)
                env = {k: v for k, v in os.environ.items() if not k.startswith(('SNOWFLAKE_', 'TD_'))}
                env.update(TD_HOST='127.0.0.1', TD_PORT=str(params['port']), TD_USER='postgres', TD_PASSWORD='',
                           TD_DB=db, PMROOTDIR=str(runroot), LANDING_DIR=str(ESTATE / 'tests/fixture/landing'))
                cmd = [str(ESTATE / '.venv/bin/python'), '-m', 'runner', 'startsession', '-f', 'SFX_AUDIT',
                       '-w', 'wf_SFX_AUDIT_DAILY', 's_m_SFX_AUDIT_EVENT_ARCHIVE']
                runs = []
                for n in (1, 2):  # run 2 documents the legacy duplicate-producing append
                    with (path / f'runner{n}.log').open('w') as log:
                        rc = subprocess.run(cmd, cwd=ESTATE, env=env, stdout=log, stderr=subprocess.STDOUT).returncode
                    snap = snapshot(pg, 'SFX_AUDIT.AUDIT_EVENT_ARCHIVE')
                    dump(path / f'runner{n}/target.json', snap)
                    bad = list(runroot.rglob('audit_event_archive1.bad'))
                    dump(path / f'runner{n}/rejects.json', [{'name': 'audit_event_archive1.bad', 'present': bool(bad),
                         'rows': bad[0].read_text().splitlines() if bad else []}])
                    with (runroot / 'REP_SESS_LOG.psv').open() as f:
                        sessions = [r for r in csv.DictReader(f, delimiter='|') if r.get('MAPPING_NAME') == ARCHIVE]
                    dump(path / f'runner{n}/session_results.json', sessions[-1:])
                    dump(path / f'runner{n}/sequence_storage.json', json.loads((storage / 'sequence_values.json').read_text()))
                    runs.append({'command': cmd, 'returncode': rc, 'rows': len(snap['rows'])})
                    if rc:
                        raise RuntimeError('Runner failed; logs retained in ' + str(runroot))
                dump(path / 'commands.json', runs)
        finally:
            admin.execute(f'DROP DATABASE {db} WITH (FORCE)')
    print(json.dumps(runs))


def python_value(c):
    kind, value = c
    if kind == 'null':
        return None
    if kind == 'number':
        return int(value)
    if kind == 'timestamp':
        return datetime.fromisoformat(value)
    return value


def write(cursor, records, sql, params=None):
    if not WRITE.match(sql):
        raise ValueError('UNT-4 writes are limited to new PC_AUDIT_UNT4_FIXTURE objects')
    if params is None:
        cursor.execute(sql)
        records.append({'sql': sql, 'qid': cursor.sfqid})
    else:
        cursor.executemany(sql, params)
        records.append({'sql': sql, 'qid': cursor.sfqid, 'rows': len(params)})


def fixture_load():
    path = DEST / 'fixture/snowflake_load'
    if path.exists():
        raise ValueError('Fixture already loaded; never overwrite')
    runner = {s: load(DEST / 'fixture' / s / 'runner/initial_state.json') for s in FIXTURES}
    if runner['empty']['source'] != runner['history']['source']:
        raise ValueError('Fixture sources differ between scenarios')
    source, history = runner['history']['source'], runner['history']['target']
    records = []
    with queries(path, 'unt4-fixture-load') as q:
        _, existing = q.run(f"SELECT TABLE_NAME FROM SFX_D1110_AFTER.INFORMATION_SCHEMA.TABLES "
                            f"WHERE TABLE_SCHEMA='PC_AUDIT_UNT4_FIXTURE'")
        if existing:
            raise ValueError('Fixture schema already has tables; refusing to overwrite')
        cursor = q.cursor
        write(cursor, records, f"CREATE SCHEMA IF NOT EXISTS {FIXTURE_SCHEMA} COMMENT = '{COMMENT}'")
        for name, snap in (('AUDIT_EVENT', source), ('UNT4_FIXTURE_ARCHIVE_HISTORY', history)):
            types = {c: sf_type(snap['types'][c]).replace('TIMESTAMP_NTZ(9)', 'TIMESTAMP_NTZ(0)') for c in snap['columns']}
            ddl = ', '.join(f'{c} {types[c]}' for c in snap['columns'])
            write(cursor, records, f"CREATE TABLE {FIXTURE_SCHEMA}.{name} ({ddl}) COMMENT = '{COMMENT}'")
            values = [[python_value(v) for v in r] for r in snap['rows']]
            if values:
                write(cursor, records, f"INSERT INTO {FIXTURE_SCHEMA}.{name} ({', '.join(snap['columns'])}) "
                      f"VALUES ({', '.join(['%s'] * len(snap['columns']))})", values)
            actual = fetched(q, f'{FIXTURE_SCHEMA}.{name}', snap, source_loading=True)
            dump(path / f'{name}.json', actual)
            require_equal(snap, actual, snap['columns'][:1], path / f'{name}_comparison.json')
        dump(path / 'writes.json', records)
    print(json.dumps(records, indent=2))


# ---- live Snowflake --------------------------------------------------------------------------

def frozen_upstream(q, path):
    result = {'input': frozen_input(q, path)}
    for mapping in UPSTREAM:
        row = next(r for r in scope() if r['mapping'] == mapping)
        actual = fetched(q, relation(row['after_table']), oracle(mapping), source_loading=True)
        result[mapping] = require_equal(oracle(mapping), actual, ['EVENT_ID'], path / f'{mapping}_unchanged.json')
    return result


def preflight():
    path = DEST / 'preflight'
    if (path / 'summary.json').exists():
        raise ValueError('Preflight already captured; preserve initial-state evidence')
    summary = {'git_head': git_head(), 'manifest_sha256': sha(OUT / 'manifest.json'),
               'implementation_sha256': implementation_hashes(), 'baselines': {}, 'targets': {}}
    with queries(path, 'unt4-preflight') as q:
        summary['control'] = control_snapshot(q, path)
        summary['upstream'] = frozen_upstream(q, path)
        for mapping in MAPPINGS:
            row = owned(mapping)
            sessions = load(OUT / mapping / 'oracle1/session_results.json')
            rejects = load(OUT / mapping / 'oracle1/rejects.json')
            if not all(s['RUN_STATUS'] == 'SUCCEEDED' and s['FAILED_ROWS'] == '0' and
                       'unt2_oracle_d53b0b939dd5/' in s['SESSION_LOG_FILE'] for s in sessions) or any(r['rows'] for r in rejects):
                raise ValueError('Oracle lineage/status/rejects do not match accepted UNT-2')
            actual = fetched(q, relation(row['before_table']), oracle(mapping))
            dump(path / mapping / 'before.json', actual)
            summary['baselines'][mapping] = require_equal(oracle(mapping), actual, row['key_columns'],
                                                          path / mapping / 'before_comparison.json')
            summary['targets'][mapping] = target_state(q, row['after_table'])
        for scenario, model in FIXTURES.items():
            summary['targets'][scenario] = target_state(q, f'{FIXTURE_SCHEMA}.{model.split("__", 1)[1].upper()}')
        summary['snowflake_utc_date'] = utc_date(q)
        summary['all_query_ids'] = [r['qid'] for r in q.records]
    summary['write_ready'] = (not any(summary['targets'][m]['exists'] for m in MAPPINGS + ('empty',))
                              and summary['targets']['history'].get('row_count') == 3)
    dump(path / 'summary.json', summary)
    print(json.dumps({k: summary[k] for k in ('git_head', 'write_ready', 'snowflake_utc_date', 'baselines')}, indent=2))
    if not summary['write_ready']:
        raise ValueError('Targets are not in the expected initial state; coordinate before any write')


def subject(name):
    if name in FIXTURES:
        initial = load(DEST / 'fixture' / name / 'runner/initial_state.json')
        return {'model': FIXTURES[name], 'mapping': ARCHIVE, 'keys': owned(ARCHIVE)['key_columns'],
                'table': f'{FIXTURE_SCHEMA}.{FIXTURES[name].split("__", 1)[1].upper()}',
                'oracle': load(DEST / 'fixture' / name / 'runner/runner1/target.json'),
                'rejects': load(DEST / 'fixture' / name / 'runner/runner1/rejects.json'),
                'sessions': load(DEST / 'fixture' / name / 'runner/runner1/session_results.json'),
                'runner_date': initial['current_date'], 'path': DEST / 'fixture' / name, 'env': {'SFX_UNT4_ARCHIVE_FIXTURE': '1'}}
    row = owned(name)
    return {'model': row['dbt_model'], 'mapping': name, 'keys': row['key_columns'], 'table': relation(row['after_table']),
            'oracle': oracle(name), 'rejects': load(OUT / name / 'oracle1/rejects.json'),
            'sessions': load(OUT / name / 'oracle1/session_results.json'), 'runner_date': None,
            'path': DEST / name, 'env': {}}


def run(name, number):
    s = subject(name)
    pre = load(DEST / 'preflight/summary.json')
    if not pre['write_ready'] or pre['implementation_sha256'] != implementation_hashes() or pre['git_head'] != git_head():
        raise ValueError('Preflight not authorized, or implementation/HEAD changed since preflight')
    path = s['path'] / f'run{number}'
    if path.exists():
        raise ValueError('Never overwrite an execution capture')
    if number == 2 and not (path.parent / 'run1/execution.json').exists():
        raise ValueError('Run 1 must precede run 2')
    step = f'unt4-{name}-run{number}-{uuid.uuid4().hex}'
    with queries(path, step) as q:
        if (DEST / 'preflight/control.json').read_bytes() != (
                json.dumps(evidence_live.control(q), indent=2, sort_keys=True) + '\n').encode():
            raise ValueError('Control changed since preflight; stop before build')
        frozen_upstream(q, path)
        if name in FIXTURES:
            source = load(DEST / 'fixture' / name / 'runner/initial_state.json')['source']
            require_equal(source, fetched(q, f'{FIXTURE_SCHEMA}.AUDIT_EVENT', source, source_loading=True),
                          ['EVENT_ID'], path / 'fixture_input_comparison.json')
        dump(path / 'initial_target.json', target_state(q, s['table']))
        execution = {'step': step, 'snowflake_utc_date_before': utc_date(q), 'runner_current_date': s['runner_date'],
                     'command': [str(ROOT / 'warehouse/.venv/bin/python'), str(ROOT / 'warehouse/snowflake/run_dbt.py'),
                                 'build', '--select', s['model'], '--step', step, '--mapping', s['mapping']],
                     'env_overrides': s['env'], 'start_utc': utc()}
        started = datetime.now(timezone.utc).timestamp()
        try:
            with (path / 'stdout_stderr.log').open('w') as output:
                process = subprocess.Popen(execution['command'], cwd=ROOT, stdout=subprocess.PIPE, text=True,
                                           stderr=subprocess.STDOUT, env={**os.environ, **s['env']})
                for line in process.stdout:
                    output.write(line)
                    print(line, end='', flush=True)
                execution['returncode'] = process.wait()
        finally:
            execution['end_utc'] = utc()
            for relative in ('target/run_results.json', 'logs/dbt.log'):
                artifact = ROOT / 'warehouse/dbt' / relative
                if artifact.exists() and artifact.stat().st_mtime >= started:
                    shutil.copy2(artifact, path / artifact.name)
            if (path / 'run_results.json').exists():
                execution['adapter_responses'] = [r.get('adapter_response') for r in load(path / 'run_results.json')['results']]
                execution['adapter_query_ids'] = adapter_query_ids(execution['adapter_responses'])
            _, history = q.run("SELECT QUERY_ID,QUERY_TEXT,QUERY_TYPE,QUERY_TAG,START_TIME,END_TIME,EXECUTION_STATUS "
                               "FROM TABLE(SFX_D1110_AFTER.INFORMATION_SCHEMA.QUERY_HISTORY_BY_USER(RESULT_LIMIT=>10000)) "
                               f"WHERE TRY_PARSE_JSON(QUERY_TAG):step::string='{step}' ORDER BY START_TIME")
            execution['history'] = [[cell(v) for v in r] for r in history]
            execution['query_ids'] = [r[0] for r in history]
            execution['snowflake_utc_date_after'] = utc_date(q)
            (path / 'dbt_transcript.txt').write_text('\n\n'.join(f'SQL: {r[1]}\nQID: {r[0]}' for r in history))
            dump(path / 'execution.json', execution)
        if execution['returncode'] or not (path / 'run_results.json').exists() or not execution['query_ids']:
            raise ValueError('dbt failed or evidence missing; retained raw output')
        if s['runner_date'] and {execution['snowflake_utc_date_before'], execution['snowflake_utc_date_after']} != {s['runner_date']}:
            raise ValueError('UTC date differs from the runner fixture date; date-boundary proof invalid')
        target = fetched(q, s['table'], s['oracle'], source_loading=True)
        dump(path / 'target.json', target)
        dump(path / 'rejects.json', empty_like(s['oracle']))


def replay(name):
    s = subject(name)
    path = s['path']
    run1, run2 = load(path / 'run1/target.json'), load(path / 'run2/target.json')
    seq = owned(s['mapping'])['sequence_columns']
    # UNT-4 gates rejects below (no dbt reject path, runner FAILED_ROWS=0), so the shared
    # runner-reject comparison gets empty snapshots.
    result = replay_gate(s['oracle'], run1, run2, s['keys'], seq, ([], [], []))
    raw_rejects = [r for f in s['rejects'] for r in f['rows']]
    result['rejects'] = {'oracle_raw_rows': raw_rejects,
                         'oracle_sessions': s['sessions'],
                         'dbt': {f'run{n}': full_compare(empty_like(s['oracle']), load(path / f'run{n}/rejects.json'), s['keys'])
                                 for n in (1, 2)},
                         'note': 'Neither mapping has a reject path in dbt; runner sessions report FAILED_ROWS=0 and no .bad rows.'}
    sessions_ok = all(x['RUN_STATUS'] == 'SUCCEEDED' and x['FAILED_ROWS'] == '0' for x in s['sessions'])
    executions = [load(path / f'run{n}/execution.json') for n in (1, 2)]
    with queries(path / 'between_runs', f'unt4-{name}-between-{uuid.uuid4().hex}') as q:
        _, between = q.run("SELECT QUERY_ID,QUERY_TYPE,QUERY_TEXT,QUERY_TAG,START_TIME,END_TIME,EXECUTION_STATUS "
                           "FROM TABLE(SFX_D1110_AFTER.INFORMATION_SCHEMA.QUERY_HISTORY_BY_USER("
                           f"END_TIME_RANGE_START=>'{executions[0]['end_utc']}'::TIMESTAMP_LTZ,"
                           f"END_TIME_RANGE_END=>'{executions[1]['start_utc']}'::TIMESTAMP_LTZ,RESULT_LIMIT=>10000)) ORDER BY START_TIME")
    table = s['table'].split('.')[-1]
    writes = [[cell(v) for v in r] for r in between
              if r[1] not in ('SELECT', 'DESCRIBE', 'SHOW') and table in (r[2] or '').upper()]
    result['between_runs'] = {'window': [executions[0]['end_utc'], executions[1]['start_utc']],
                              'all_queries': len(between), 'writes_to_target': writes}
    result['passed'] = (result['passed'] and sessions_ok and not raw_rejects and not writes
                        and all(r['equal'] for r in result['rejects']['dbt'].values()))
    if name in FIXTURES:
        legacy = load(path / 'runner/runner2/target.json')
        result['legacy_rerun'] = {'runner_run2_rows': len(legacy['rows']), 'dbt_run2_rows': len(run2['rows']),
                                  'runner_run2_vs_dbt_run2': full_compare(legacy, run2, s['keys'])['equal'],
                                  'note': 'INTENDED DIFFERENCE: legacy rerun appends every qualifying event again with new IDs.'}
    dump(path / 'replay.json', result)
    print(json.dumps({'subject': name, 'passed': result['passed'], 'rows': len(run2['rows']),
                      'between_run_writes': len(writes)}))
    if not result['passed']:
        raise ValueError('Replay parity failed')


def postflight():
    path = DEST / 'postflight'
    with queries(path, 'unt4-postflight') as q:
        summary = control_snapshot(q, path)
        summary['upstream'] = frozen_upstream(q, path)
    summary['byte_identical'] = (path / 'control.json').read_bytes() == (DEST / 'preflight/control.json').read_bytes()
    dump(path / 'summary.json', summary)
    print(json.dumps(summary, indent=2))
    if not summary['byte_identical']:
        raise ValueError('Control snapshot changed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    subs.add_parser('preflight')
    subs.add_parser('postflight')
    subs.add_parser('fixture-load')
    sub = subs.add_parser('fixture-runner')
    sub.add_argument('--scenario', required=True, choices=sorted(FIXTURES))
    for name in ('run', 'replay'):
        sub = subs.add_parser(name)
        sub.add_argument('--subject', required=True, choices=MAPPINGS + tuple(sorted(FIXTURES)))
        if name == 'run':
            sub.add_argument('--run', required=True, type=int, choices=(1, 2))
    args = parser.parse_args()
    if args.command == 'fixture-runner':
        runner_fixture(args.scenario)
    elif args.command == 'fixture-load':
        fixture_load()
    elif args.command == 'preflight':
        preflight()
    elif args.command == 'postflight':
        postflight()
    elif args.command == 'run':
        run(args.subject, args.run)
    else:
        replay(args.subject)


if __name__ == '__main__':
    main()
