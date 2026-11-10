"""Scoped offline oracle capture and full snapshot gates; never publishes control results."""
import argparse
from collections import Counter
import csv
from datetime import datetime
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET
import zlib

import yaml

from .compare import normal
from .inventory import BOOTSTRAP, ESTATE, ROOT, inventory, target_relation

OUT = Path(__file__).parent / 'out/evidence'
PARAM = ESTATE / 'params/sfx_d1110_daily.par'
sys.path.insert(0, str(ESTATE))
from runner.params import resolve, expand


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scope():
    config = yaml.safe_load(Path(__file__).with_name('evidence_scope.yml').read_text())
    rows = []
    for row in inventory():
        if row['mapping'] not in config['mappings']:
            continue
        row.update(config['mappings'][row['mapping']])
        doc = ET.parse(ESTATE / 'repository' / row['folder'] / (row['workflow'] + '.XML'))
        session = next(s for s in doc.findall('.//SESSION') if s.get('NAME') == row['session'])
        attrs = [a.attrib for a in session.findall('.//ATTRIBUTE')]
        row['reject_files'] = [a['VALUE'] for a in attrs if a['NAME'] == 'Reject filename']
        row['reject_tables'] = []
        task = next(t for t in doc.findall('.//TASKINSTANCE') if t.get('TASKNAME') == row['session'])
        row['enabled_in_workflow'] = task.get('ISENABLED') == 'YES'
        row['disabled_reason'] = None if row['enabled_in_workflow'] else 'Disabled in canonical PowerCenter workflow; standalone capture only.'
        mapping = ET.parse(ESTATE / 'repository' / row['folder'] / 'mappings' / (row['mapping'] + '.XML'))
        sequences = {t.get('NAME'): {a.get('NAME'): a.get('VALUE') for a in t.findall('TABLEATTRIBUTE')}
                     for t in mapping.findall('.//TRANSFORMATION') if t.get('TYPE') in ('Sequence', 'Sequence Generator')}
        row['sequence_initial_state'] = sequences
        row['sequence_columns'] = [c.get('TOFIELD') for c in mapping.findall('.//CONNECTOR')
                                   if c.get('FROMINSTANCE') in sequences and c.get('TOINSTANCETYPE') == 'Target Definition']
        row['parameters'] = resolve([PARAM], row['folder'], row['workflow'], row['session'])
        files = []
        for ext in session.findall('SESSIONEXTENSION'):
            a = {x.get('NAME'): x.get('VALUE') for x in ext.findall('ATTRIBUTE')}
            if 'Source file directory' in a:
                files.append(expand(a['Source file directory'] + a['Source filename'], row['parameters'],
                                    {'$PMSourceFileDir': str(ESTATE / 'tests/fixture/landing')}))
        row['landing_files'] = files
        rows.append(row)
    if len(rows) != 8:
        raise ValueError('Expected exactly eight owned mappings')
    return rows


def cell(value):
    # Preserve string whitespace, numeric scale and timestamp zone: no lossy normalisations.
    if isinstance(value, str):
        return ['string', value]
    if isinstance(value, Decimal):
        return ['decimal', str(value)]
    if isinstance(value, datetime):
        return ['timestamp', value.isoformat(timespec='microseconds')]
    return normal(value)


def snapshot(pg, relation):
    schema, table = relation.lower().split('.')
    cols = pg.execute('''SELECT column_name, data_type, character_maximum_length,
        numeric_precision, numeric_scale, datetime_precision FROM information_schema.columns
        WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position''', (schema, table)).fetchall()
    if not cols:
        raise ValueError('Missing table: ' + relation)
    names = [c[0].upper() for c in cols]
    data = pg.execute(f'SELECT * FROM {schema}.{table}').fetchall()
    return {'columns': names, 'types': {c[0].upper(): list(c[1:]) for c in cols},
            'rows': sorted([[cell(v) for v in r] for r in data], key=json.dumps)}


def full_compare(before, after, keys):
    if not keys or not set(keys) <= set(before['columns']):
        raise ValueError('Missing business keys')
    columns = before['columns']
    if set(columns) != set(after['columns']):
        return {'equal': False, 'schema_error': 'Column sets differ'}
    order = [after['columns'].index(c) for c in columns]
    br = before['rows']
    ar = [[r[i] for i in order] for r in after['rows']]
    def counts(rows, indexes):
        return Counter(json.dumps([r[i] for i in indexes], sort_keys=True) for r in rows)
    b, a = counts(br, range(len(columns))), counts(ar, range(len(columns)))
    ki = [columns.index(k) for k in keys]
    bk, ak = counts(br, ki), counts(ar, ki)
    def differences(counter):
        return [{'row': json.loads(r), 'multiplicity': n} for r, n in sorted(counter.items())]
    return {'equal': b == a and before['types'] == after['types'],
            'before_rows': len(br), 'after_rows': len(ar),
            'only_before': differences(b - a), 'only_after': differences(a - b),
            'key_multiplicities': [{'key': json.loads(k), 'before': bk[k], 'after': ak[k]}
                                   for k in sorted(bk.keys() | ak.keys())],
            'duplicate_keys_before': differences(Counter({k: n for k, n in bk.items() if n > 1})),
            'duplicate_keys_after': differences(Counter({k: n for k, n in ak.items() if n > 1})),
            'null_counts': {c: {'before': sum(r[i][0] == 'null' for r in br),
                                'after': sum(r[i][0] == 'null' for r in ar)} for i, c in enumerate(columns)},
            'type_checks': {'equal': before['types'] == after['types'],
                            'before': before['types'], 'after': after['types']},
            'representation_only_normalisations': ['JSON typed cells; native integer/date/bool encoding'],
            'strict_checks': ['decimal scale', 'timestamp timezone and precision', 'string whitespace', 'null versus empty']}


def replay_gate(oracle, run1, run2, keys, sequence_columns):
    checks = {'oracle_run1': full_compare(oracle, run1, keys),
              'oracle_run2': full_compare(oracle, run2, keys),
              'run1_run2': full_compare(run1, run2, keys)}
    def ids(s):
        indexes = [s['columns'].index(c) for c in keys + sequence_columns]
        return Counter(json.dumps([r[i] for i in indexes]) for r in s['rows'])
    stable = ids(run1) == ids(run2)
    return {'passed': stable and all(c['equal'] and not c.get('duplicate_keys_before')
                                    and not c.get('duplicate_keys_after') for c in checks.values()),
            'sequence_ids_stable': stable, 'comparisons': checks}


def local_params():
    host = os.environ.get('TD_HOST', '127.0.0.1')
    if host not in ('127.0.0.1', 'localhost'):
        raise ValueError('Oracle capture restricted to local PostgreSQL')
    port = os.environ.get('TD_PORT', str(55500 + zlib.crc32(b'sfx-d1110-before') % 1000))
    return dict(host=host, port=port, user=os.environ.get('TD_USER', 'postgres'),
                password=os.environ.get('TD_PASSWORD', ''), autocommit=True)


def manifest_data(pg):
    rows = scope()
    files = sorted({p for r in rows for p in r['landing_files']})
    tables = sorted({target_relation(r['target_table']) for r in rows} |
                    {s for r in rows for s in r['source_objects'] if '.' in s})
    notes = {
        'm_SFX_LOGIN_EVENT': {'source_rows': 420, 'written_rows': 412, 'rejected_rows': 0,
            'explanation': 'RTR_LOGIN_RESULT routes SUCCESS (364) and FAILED/LOCKED/MFA_FAILED (48) to connected target instances. Eight TIMEOUT rows reach unconnected DEFAULT1 and are filtered, not rejected.'},
        'm_SFX_SECURITY_ALERT': {'source_rows': 64, 'written_rows': 61, 'rejected_rows': 3,
            'explanation': 'RTR_SEVERITY routes CRITICAL/HIGH (15) and MEDIUM/LOW (46) to DD_UPDATE writers with Update else Insert. Three INFO rows route DEFAULT1 to UPD_ALERT_UNKNOWN DD_REJECT and security_alert21.bad.'}}
    for mapping, note in notes.items():
        dump(OUT / mapping / 'routing_notes.json', note)
    return {'business_date': sorted({r['parameters']['$$LOAD_DATE'] for r in rows}),
            'routing_notes': notes,
            'landing': [{'path': p, 'sha256': sha(Path(p)), 'row_count': len(Path(p).read_text().splitlines())} for p in files],
            'parameter_file': {'path': str(PARAM), 'sha256': sha(PARAM)},
            'bootstrap_sha256': sha(BOOTSTRAP), 'scope': rows,
            'initial_tables': {t: snapshot(pg, t) for t in tables},
            'sequence_storage_initial': {},
            'runner_git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            'oracle_source_sha256': {str(p.relative_to(ROOT)): sha(p) for p in sorted((ESTATE / 'runner').glob('*.py'))}}


def capture(command):
    import psycopg
    params = local_params()
    captures = []
    for n in range(1, 3 if command == 'oracle' else 2):
        db = 'unt2_oracle_' + uuid.uuid4().hex[:12]
        runroot = (OUT / db).resolve()
        runroot.mkdir(parents=True)
        with psycopg.connect(dbname='postgres', **params) as admin:
            admin.execute(f'CREATE DATABASE {db}')
            try:
                with psycopg.connect(dbname=db, **params) as pg:
                    pg.execute(BOOTSTRAP.read_text())
                    manifest = manifest_data(pg)
                    dump(runroot / 'manifest.json', manifest)
                    if command == 'manifest':
                        dump(OUT / 'manifest.json', manifest)
                        print('Manifest:', OUT / 'manifest.json')
                        return
                    frozen = json.loads((OUT / 'manifest.json').read_text())
                    if manifest != frozen:
                        raise ValueError('Inputs/initial state differ from frozen manifest')
                    env = {k: v for k, v in os.environ.items() if not k.startswith(('SNOWFLAKE_', 'TD_'))}
                    env.update(TD_HOST=params['host'], TD_PORT=str(params['port']), TD_USER=params['user'],
                               TD_PASSWORD=params['password'], TD_DB=db, PMROOTDIR=str(runroot),
                               LANDING_DIR=str(ESTATE / 'tests/fixture/landing'))
                    commands = [['startworkflow', '-f', 'SFX_AUDIT', 'wf_SFX_AUDIT_DAILY']]
                    # Canonical content workflow also runs five unowned mappings. Do not dispatch it.
                    commands += [['startsession', '-f', r['folder'], '-w', r['workflow'], r['session']]
                                 for r in scope() if r['folder'] == 'SFX_CONTENT' or not r['enabled_in_workflow']]
                    if command == 'content-check':
                        commands = [['startworkflow', '-f', 'SFX_CONTENT', 'wf_SFX_CONTENT_DAILY'],
                                    ['startsession', '-f', 'SFX_CONTENT', '-w', 'wf_SFX_CONTENT_DAILY', 's_m_SFX_TEAM_MEMBER']]
                    results = []
                    for i, args in enumerate(commands):
                        cmd = [str(ESTATE / '.venv/bin/python'), '-m', 'runner', *args]
                        with (runroot / f'command-{i}.log').open('w') as log:
                            result = subprocess.run(cmd, cwd=ESTATE, env=env, stdout=log, stderr=subprocess.STDOUT)
                        results.append({'command': cmd, 'returncode': result.returncode})
                    dump(runroot / 'commands.json', results)
                    if command == 'content-check':
                        reports = {}
                        for row in scope():
                            if row['folder'] != 'SFX_CONTENT':
                                continue
                            before = json.loads((OUT / row['mapping'] / 'oracle1/target.json').read_text())
                            after = snapshot(pg, target_relation(row['target_table']))
                            reports[row['mapping']] = full_compare(before, after, row['key_columns'])
                        dump(OUT / 'content_workflow_equivalence.json', {'runroot': str(runroot), 'commands': results, 'comparisons': reports})
                        if any(r['returncode'] for r in results) or not all(r['equal'] for r in reports.values()):
                            raise RuntimeError('Content workflow equivalence failed')
                        print('Content workflow equivalence: all three owned targets identical; logs:', runroot)
                        return
                    targets = {}
                    for r in scope():
                        snap = snapshot(pg, target_relation(r['target_table']))
                        targets[r['mapping']] = snap
                        dest = OUT / r['mapping'] / f'oracle{n}'
                        dump(dest / 'target.json', snap)
                        with (dest / 'target.csv').open('w', newline='') as f:
                            writer = csv.writer(f)
                            writer.writerow(snap['columns'])
                            writer.writerows([[json.dumps(v) for v in row] for row in snap['rows']])
                        rejects = []
                        for name in r['reject_files']:
                            matches = list(runroot.rglob(name))
                            rejects.append({'name': name, 'present': bool(matches),
                                            'rows': matches[0].read_text().splitlines() if matches else [],
                                            'absence_reason': None if matches else 'Runner removes empty reject files (engine.write_target); see session result for transformation errors.'})
                        dump(dest / 'rejects.json', rejects)
                        with (dest / 'rejects.csv').open('w', newline='') as f:
                            writer = csv.writer(f)
                            writer.writerow(['file', 'line_number', 'raw_runner_record'])
                            for reject in rejects:
                                writer.writerows((reject['name'], i, line) for i, line in enumerate(reject['rows'] or [], 1))
                        with (runroot / 'REP_SESS_LOG.psv').open() as f:
                            records = list(csv.DictReader(f, delimiter='|'))
                        dump(dest / 'session_results.json', [record for record in records if record.get('MAPPING_NAME') == r['mapping']])
                    captures.append(targets)
                    dump(runroot / 'summary.json', {'database': db, 'commands': results,
                         'target_counts': {m: len(s['rows']) for m, s in targets.items()}})
                    print('Oracle', n, 'logs:', runroot, 'counts:', {m: len(s['rows']) for m, s in targets.items()})
                    if any(r['returncode'] for r in results):
                        raise RuntimeError('PowerCenter command failed; retained logs: ' + str(runroot))
            finally:
                admin.execute(f'DROP DATABASE {db} WITH (FORCE)')
    for r in scope():
        report = full_compare(captures[0][r['mapping']], captures[1][r['mapping']], r['key_columns'])
        rejects = [json.loads((OUT / r['mapping'] / f'oracle{n}' / 'rejects.json').read_text()) for n in (1, 2)]
        report['rejects_identical'] = rejects[0] == rejects[1]
        report['reject_counts'] = [{x['name']: len(x['rows']) if x['rows'] is not None else None for x in run} for run in rejects]
        dump(OUT / r['mapping'] / 'oracle_determinism.json', report)
        print(r['mapping'], 'oracle deterministic:', report['equal'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['manifest', 'oracle', 'content-check', 'live-preflight', 'live', 'compare', 'replay'])
    parser.add_argument('--mapping')
    parser.add_argument('--oracle', type=Path)
    parser.add_argument('--run1', type=Path)
    parser.add_argument('--run2', type=Path)
    args = parser.parse_args()
    if args.command.startswith('live'):
        from .evidence_live import live
        live(preflight_only=args.command == 'live-preflight')
        return
    if args.command in ('manifest', 'oracle', 'content-check'):
        capture(args.command)
        return
    row = next(r for r in scope() if r['mapping'] == args.mapping)
    load = lambda p: json.loads(p.read_text())
    if args.command == 'compare':
        result = full_compare(load(args.oracle), load(args.run1), row['key_columns'])
        passed = result['equal']
    else:
        result = replay_gate(load(args.oracle), load(args.run1), load(args.run2), row['key_columns'], row['sequence_columns'])
        passed = result['passed']
    dump(OUT / row['mapping'] / (args.command + '.json'), result)
    raise SystemExit(0 if passed else 1)


if __name__ == '__main__':
    main()
