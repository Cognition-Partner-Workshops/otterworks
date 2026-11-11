"""UNT-3 audit evidence. Only the explicit run subcommand can launch a dbt build."""
import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid

from . import evidence_live
from .commands import relation
from .evidence import OUT, cell, dump, full_compare, replay_gate, scope, sha
from .evidence_live import control, expected_landing, fetched
from .harness import connection, control_table
from .inventory import ROOT

DEST = OUT / 'unt3'
MANIFEST_SHA = 'b5e0c8a390fba31c4f5f4b930d82d54102eb09e8e35837c90f1096168b67c41c'
MAPPINGS = ('m_SFX_STG_AUDIT_EVENT', 'm_SFX_AUDIT_EVENT')


def load(path):
    return json.loads(path.read_text())


def owned(mapping):
    if mapping not in MAPPINGS:
        raise ValueError('UNT-3 owns only the two audit event mappings')
    return next(r for r in scope() if r['mapping'] == mapping)


def oracle(mapping):
    return load(OUT / mapping / 'oracle1/target.json')


def fingerprint(value):
    return hashlib.sha256((json.dumps(value, indent=2, sort_keys=True) + '\n').encode()).hexdigest()


def implementation_hashes():
    paths = [Path(__file__), Path(__file__).parent / 'mappings/sfx_audit.yml']
    paths += sorted((ROOT / 'warehouse/dbt/models/pc/audit').glob('*'))
    return {str(p.relative_to(ROOT)): sha(p) for p in paths if p.is_file()}


class ReadOnlyQueries(evidence_live.Queries):
    def run(self, sql):
        if not re.match(r'^(SELECT|DESCRIBE|SHOW)\s', sql, re.I):
            raise ValueError('Evidence SQL must be read-only')
        return super().run(sql)


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


def target_state(q, table):
    table = relation(table)
    _, schema, name = table.split('.')
    names, rows = q.run(f"SELECT TABLE_CATALOG,TABLE_SCHEMA,TABLE_NAME,TABLE_TYPE,CREATED,LAST_ALTERED,TABLE_OWNER "
                        f"FROM SFX_D1110_AFTER.INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='{schema}' AND TABLE_NAME='{name}'")
    state = {'exists': bool(rows), 'metadata': [dict(zip(names, [cell(v) for v in r])) for r in rows],
             'metadata_qid': q.records[-1]['qid']}
    if rows:
        columns, described = q.run('DESCRIBE TABLE ' + table)
        state['describe'] = {'columns': columns, 'rows': [[cell(v) for v in r] for r in described],
                             'qid': q.records[-1]['qid']}
        _, counts = q.run('SELECT COUNT(*) FROM ' + table)
        state.update(row_count=int(counts[0][0]), count_qid=q.records[-1]['qid'])
    return state


def control_snapshot(q, path):
    if control_table() != 'SFX_D1110_AFTER.MIGRATION_CONTROL.MAPPINGS':
        raise ValueError('UNT-3 control table cannot be overridden')
    value = control(q)
    dump(path / 'control.json', value)
    return {'sha256': sha(path / 'control.json'), 'qid': q.records[-1]['qid'],
            'row_count': len(value['rows']), 'owners': {'migrations-page': 8, 'act3-workflow': 12}}


def duplicate_keys(snap):
    i = snap['columns'].index('EVENT_ID')
    counts = Counter(json.dumps(r[i]) for r in snap['rows'])
    return sum(n - 1 for n in counts.values() if n > 1)


def require_equal(expected, actual, path):
    result = full_compare(expected, actual, ['EVENT_ID'])
    dump(path, result)
    if not result['equal']:
        raise ValueError('Full multiset mismatch: ' + str(path))
    return {'equal': True, 'rows': len(actual['rows']), 'duplicate_event_ids': duplicate_keys(actual)}


def frozen_input(q, path):
    manifest_path = OUT / 'manifest.json'
    if sha(manifest_path) != MANIFEST_SHA:
        raise ValueError('Frozen manifest SHA256 mismatch')
    manifest = load(manifest_path)
    row = owned(MAPPINGS[0])
    template = manifest['initial_tables']['SFX_AUDIT.STG_AUDIT_EVENT']
    expected = expected_landing(manifest, row, template)
    actual = fetched(q, 'SFX_D1110_AFTER.PC_SRC.AUDIT_EVENT', template, source_loading=True)
    dump(path / 'input_expected.json', expected)
    dump(path / 'input_actual.json', actual)
    return require_equal(expected, actual, path / 'input_comparison.json')


def preflight():
    path = DEST / 'preflight'
    if (path / 'summary.json').exists():
        raise ValueError('Preflight already captured; preserve initial-state evidence')
    summary = {'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
               'manifest_sha256': sha(OUT / 'manifest.json'), 'targets': {}, 'baselines': {},
               'implementation_sha256': implementation_hashes()}
    with queries(path, 'unt3-preflight') as q:
        summary['control'] = control_snapshot(q, path)
        summary['input_freeze'] = frozen_input(q, path)
        for mapping in MAPPINGS:
            row = owned(mapping)
            template = oracle(mapping)
            sessions = load(OUT / mapping / 'oracle1/session_results.json')
            if not all(s['RUN_STATUS'] == 'SUCCEEDED' and s['FAILED_ROWS'] == '0'
                       and s['FAILED_SOURCE_ROWS'] == '0' and
                       'unt2_oracle_d53b0b939dd5/' in s['SESSION_LOG_FILE'] for s in sessions):
                raise ValueError('Oracle lineage/status/reject count does not match accepted UNT-2')
            reject_template(mapping, oracle(MAPPINGS[0]))
            actual = fetched(q, relation(row['before_table']), template)
            dump(path / mapping / 'before.json', actual)
            summary['baselines'][mapping] = require_equal(template, actual, path / mapping / 'before_comparison.json')
            if len(template['rows']) != 480 or duplicate_keys(template):
                raise ValueError('Expected 480 distinct frozen EVENT_IDs')
            summary['targets'][mapping] = target_state(q, row['after_table'])
        summary['all_query_ids'] = [r['qid'] for r in q.records]
        summary['write_ready'] = not summary['targets'][MAPPINGS[1]].get('row_count', 0)
        dump(path / 'summary.json', summary)
    print(json.dumps(summary, indent=2))
    if not summary['write_ready']:
        raise ValueError('AUDIT_EVENT exists with rows; coordinate before any write')


def reject_predicate(mapping):
    model = owned(mapping)['dbt_model']
    sql = (ROOT / 'warehouse/dbt/models/pc/audit' / (model + '.sql')).read_text()
    match = re.search(r'{% set reject_predicate = "([^"]+)" %}', sql)
    if not match or 'where not ({{ reject_predicate }})' not in sql:
        raise ValueError('Model must expose and use its exact reject predicate')
    return match[1]


def reject_template(mapping, template):
    raw = load(OUT / mapping / 'oracle1/rejects.json')
    if any(r['rows'] for r in raw):
        raise ValueError('UNT-3 requires an empty oracle reject multiset; nonempty raw .bad is lossy')
    return dict(columns=template['columns'], types=template['types'], rows=[])


def export_rejects(q, mapping, path):
    table = 'PC_SRC.AUDIT_EVENT' if mapping == MAPPINGS[0] else 'PC_AUDIT.STG_AUDIT_EVENT'
    template = oracle(MAPPINGS[0])
    # Validate every input column's live type before exporting the predicate's rows.
    fetched(q, relation(table), template, source_loading=True)
    names, rows = q.run(f'SELECT * FROM {relation(table)} WHERE {reject_predicate(mapping)}')
    records = []
    for row in rows:
        records.append([cell(int(v) if v is not None and template['types'][c][0] == 'bigint' else v)
                        for c, v in zip(names, row)])
    snap = dict(columns=names, types=template['types'], rows=records)
    dump(path / 'rejects.json', snap)
    return full_compare(reject_template(mapping, template), snap, ['EVENT_ID'])


def build_command(mapping, step):
    return [sys.executable, str(ROOT / 'warehouse/snowflake/run_dbt.py'), 'build',
            '--select', owned(mapping)['dbt_model'], '--step', step, '--mapping', mapping]


def utc():
    return datetime.now(timezone.utc).isoformat()


def adapter_query_ids(responses):
    result = []
    for response in responses:
        for key, value in (response or {}).items():
            if key.lower() in ('query_id', 'queryid', 'sfqid') and value:
                result.append(value)
    return result


def run(mapping, number):
    row = owned(mapping)
    pre = load(DEST / 'preflight/summary.json')
    if not pre['write_ready']:
        raise ValueError('Preflight did not authorize an empty initial AUDIT_EVENT target')
    if pre['implementation_sha256'] != implementation_hashes():
        raise ValueError('Implementation changed since preflight')
    if pre['git_head'] != subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip():
        raise ValueError('HEAD changed since preflight')
    path = DEST / mapping / f'run{number}'
    if path.exists():
        raise ValueError('Never overwrite an execution capture')
    if number == 2 and not (path.parent / 'run1/execution.json').exists():
        raise ValueError('Run 1 must precede run 2')
    step = f'unt3-{mapping}-run{number}-{uuid.uuid4().hex}'
    with queries(path, step) as q:
        if (DEST / 'preflight/control.json').read_bytes() != (
                json.dumps(control(q), indent=2, sort_keys=True) + '\n').encode():
            raise ValueError('Control changed since preflight; stop before build')
        frozen_input(q, path)
        if mapping == MAPPINGS[1]:
            stg = fetched(q, 'SFX_D1110_AFTER.PC_AUDIT.STG_AUDIT_EVENT', oracle(MAPPINGS[0]), source_loading=True)
            require_equal(oracle(MAPPINGS[0]), stg, path / 'stg_input_comparison.json')
            if duplicate_keys(stg):
                raise ValueError('Duplicate merge input EVENT_IDs; runner order cannot be reproduced by MERGE')
            if number == 1:
                state = target_state(q, row['after_table'])
                dump(path / 'initial_target.json', state)
                if state.get('row_count', 0):
                    raise ValueError('AUDIT_EVENT has rows before run1; stop before write')
        execution = {'step': step, 'command': build_command(mapping, step), 'start_utc': utc()}
        started = datetime.now(timezone.utc).timestamp()
        try:
            with (path / 'stdout_stderr.log').open('w') as output:
                process = subprocess.Popen(execution['command'], cwd=ROOT, stdout=subprocess.PIPE,
                                           stderr=subprocess.STDOUT, text=True)
                for line in process.stdout:
                    output.write(line)
                    output.flush()
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
            _, history = q.run("SELECT QUERY_ID,QUERY_TEXT,QUERY_TAG,START_TIME,END_TIME,EXECUTION_STATUS "
                               "FROM TABLE(SFX_D1110_AFTER.INFORMATION_SCHEMA.QUERY_HISTORY_BY_USER(RESULT_LIMIT=>10000)) "
                               f"WHERE TRY_PARSE_JSON(QUERY_TAG):step::string='{step}' "
                               "AND TRY_PARSE_JSON(QUERY_TAG):workload::string='transform' ORDER BY START_TIME")
            execution['history'] = [[cell(v) for v in r] for r in history]
            execution['query_ids'] = [r[0] for r in history]
            (path / 'dbt_transcript.txt').write_text('\n\n'.join(f'SQL: {r[1]}\nQID: {r[0]}' for r in history))
            dump(path / 'execution.json', execution)
        if execution['returncode']:
            raise ValueError('dbt failed; retained raw output and execution artifacts')
        if not (path / 'run_results.json').exists() or not (path / 'dbt.log').exists():
            raise ValueError('Missing fresh dbt execution artifacts')
        if not execution['query_ids']:
            raise ValueError('Missing tagged query-history evidence')
        target = fetched(q, relation(row['after_table']), oracle(mapping), source_loading=True)
        dump(path / 'target.json', target)
        result = export_rejects(q, mapping, path)
        dump(path / 'reject_comparison.json', result)
        if not result['equal']:
            raise ValueError('Reject parity failed')


def replay(mapping):
    path = DEST / mapping
    # UNT-3 gates rejects below against its own empty reject template, so the shared
    # runner-reject comparison gets empty snapshots.
    result = replay_gate(oracle(mapping), load(path / 'run1/target.json'),
                         load(path / 'run2/target.json'), ['EVENT_ID'], ['EVENT_ID'], ([], [], []))
    template = reject_template(mapping, oracle(MAPPINGS[0]))
    result['rejects'] = {f'run{n}': full_compare(template, load(path / f'run{n}/rejects.json'), ['EVENT_ID'])
                         for n in (1, 2)}
    result['passed'] = result['passed'] and all(r['equal'] for r in result['rejects'].values())
    dump(path / 'replay.json', result)
    print(json.dumps({'mapping': mapping, 'passed': result['passed']}))
    if not result['passed']:
        raise ValueError('Replay parity failed')


def postflight():
    path = DEST / 'postflight'
    with queries(path, 'unt3-postflight') as q:
        summary = control_snapshot(q, path)
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
    for name in ('run', 'replay'):
        sub = subs.add_parser(name)
        sub.add_argument('--mapping', required=True, choices=MAPPINGS)
        if name == 'run':
            sub.add_argument('--run', required=True, type=int, choices=(1, 2))
    args = parser.parse_args()
    if args.command == 'preflight':
        preflight()
    elif args.command == 'postflight':
        postflight()
    elif args.command == 'run':
        run(args.mapping, args.run)
    else:
        replay(args.mapping)


if __name__ == '__main__':
    main()
