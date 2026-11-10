"""Guarded Snowflake evidence operations for the eight owned baselines only."""
import csv
from datetime import datetime, date
from decimal import Decimal
import json
from pathlib import Path
import uuid

import psycopg

from .evidence import OUT, cell, dump, full_compare, scope, sha, local_params, snapshot
from .harness import connection, control_table
from .harness import COMMENT
from .evidence import replay_gate
from .inventory import table_definitions, target_relation

LIVE = OUT / 'live'


class Queries:
    def __init__(self, cursor):
        self.cursor = cursor
        self.records = []

    def run(self, sql):
        try:
            self.cursor.execute(sql)
            names = [c[0].upper() for c in self.cursor.description or []]
            rows = self.cursor.fetchall()
            self.records.append({'sql': sql, 'qid': self.cursor.sfqid, 'rowcount': len(rows),
                                 'columns': names, 'rows': [[cell(v) for v in r] for r in rows]})
            return names, rows
        except Exception as error:
            self.records.append({'sql': sql, 'qid': self.cursor.sfqid, 'error': str(error)})
            raise
        finally:
            dump(LIVE / 'queries.json', self.records)
            (LIVE / 'transcript.txt').write_text('\n\n'.join(
                f"SQL: {r['sql']}\nQID: {r.get('qid')}\nROWCOUNT: {r.get('rowcount')}\nERROR: {r.get('error', '')}"
                for r in self.records))


def control(q):
    names, rows = q.run(f'SELECT * FROM {control_table()} ORDER BY FOLDER, MAPPING')
    records = [dict(zip(names, r)) for r in rows]
    ours = {r['mapping'] for r in scope()}
    assert len(records) == 20 and len({(r['FOLDER'], r['MAPPING']) for r in records}) == 20
    assert {r['MAPPING'] for r in records if r['OWNER_EFFORT'] == 'migrations-page'} == ours
    assert sum(r['OWNER_EFFORT'] == 'act3-workflow' for r in records) == 12
    return {'columns': names, 'rows': [[cell(v) for v in r] for r in rows]}


def expected_landing(manifest, row, source):
    columns, types = source['columns'], source['types']
    path = row['landing_files'][0]
    frozen = next(f for f in manifest['landing'] if f['path'] == path)
    assert sha(Path(path)) == frozen['sha256']
    result = []
    for raw in csv.reader(Path(path).open(), delimiter='|', quoting=csv.QUOTE_NONE):
        values = []
        for column, value in zip(columns, raw):
            dtype = types[column][0]
            if value == '':
                value = None
            elif dtype in ('bigint', 'integer', 'smallint'):
                value = int(value)
            elif dtype == 'numeric':
                value = Decimal(value)
            elif dtype == 'date':
                value = date.fromisoformat(value)
            elif dtype.startswith('timestamp'):
                value = datetime.fromisoformat(value)
            values.append(cell(value))
        if len(values) != len(columns):
            raise ValueError('Landing column count mismatch')
        result.append(values)
    return dict(columns=columns, types=types, rows=result)


def fetched(q, table, template, source_loading=False):
    _, described = q.run('DESCRIBE TABLE ' + table)
    actual_types = {r[0].upper(): r[1].upper() for r in described}
    for name in template['columns']:
        expected_type = sf_type(template['types'][name])
        spec = template['types'][name]
        if source_loading and spec[0].startswith('timestamp'):
            expected_type = expected_type.replace('(9)', f'({spec[4]})')
        if actual_types.get(name) != expected_type:
            raise ValueError(f'Unexpected warehouse type {table}.{name}: {actual_types.get(name)}')
    names, rows = q.run('SELECT * FROM ' + table)
    result = []
    for row in rows:
        values = []
        for name, value in zip(names, row):
            dtype = template['types'][name][0]
            if value is not None and dtype in ('bigint', 'integer', 'smallint'):
                value = int(value)
            values.append(cell(value))
        result.append(values)
    return dict(columns=names, types=template['types'], rows=result)


def sf_type(spec):
    dtype, length, precision, scale, *rest = spec
    if dtype in ('bigint', 'integer', 'smallint'):
        return 'NUMBER(38,0)'
    if dtype == 'numeric':
        return f'NUMBER({precision or 38},{scale or 0})'
    if dtype in ('character', 'character varying', 'text'):
        return f'VARCHAR({length or 16777216})'
    if dtype == 'date':
        return 'DATE'
    if dtype.startswith('timestamp'):
        return 'TIMESTAMP_TZ(9)' if 'with time zone' in dtype else 'TIMESTAMP_NTZ(9)'
    if dtype == 'boolean':
        return 'BOOLEAN'
    raise ValueError('Unsupported type: ' + dtype)


def upload(q, table, snap):
    allowed = {r['target_table'] for r in scope()}
    if table not in allowed | {t + '__REJECTS' for t in allowed}:
        raise ValueError('Unowned baseline target')
    relation = 'SFX_D1110_AFTER.PC_BEFORE.' + table
    ddl = ', '.join(c + ' ' + sf_type(snap['types'][c]) for c in snap['columns'])
    q.run(f"CREATE OR REPLACE TABLE {relation} ({ddl}) COMMENT='{COMMENT}'")
    path = (LIVE / (table + '.csv')).resolve()
    with path.open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows([[r'\N' if v[0] == 'null' else v[1] for v in row] for row in snap['rows']])
    q.run(f"PUT '{path.as_uri()}' @SFX_D1110_AFTER.PC_BEFORE.CAPTURE_STAGE/{table}/ AUTO_COMPRESS=FALSE OVERWRITE=TRUE")
    q.run(f"""COPY INTO {relation} FROM @SFX_D1110_AFTER.PC_BEFORE.CAPTURE_STAGE/{table}/ FILES=('{table}.csv')
        FILE_FORMAT=(TYPE=CSV FIELD_OPTIONALLY_ENCLOSED_BY='"' NULL_IF=('\\\\N')
        EMPTY_FIELD_AS_NULL=FALSE ESCAPE_UNENCLOSED_FIELD=NONE) FORCE=TRUE""")
    actual = fetched(q, relation, snap)
    result = full_compare(snap, actual, snap['columns'])
    result['label'] = 'UPLOAD FIDELITY — not mapping parity'
    dump(LIVE / (table + '_upload_fidelity.json'), result)
    if not result['equal']:
        raise ValueError('Upload fidelity failed: ' + table)


def baselines(q):
    names, tables = q.run('SHOW TABLES IN SCHEMA SFX_D1110_AFTER.PC_BEFORE')
    targets = {r['target_table'] for r in scope()}
    dump(LIVE / 'existing_baselines.json', [dict(zip(names, [cell(v) for v in r]))
          for r in tables if r[names.index('NAME')] in targets])
    q.run(f"CREATE STAGE IF NOT EXISTS SFX_D1110_AFTER.PC_BEFORE.CAPTURE_STAGE COMMENT='{COMMENT}'")
    for row in scope():
        snap = json.loads((OUT / row['mapping'] / 'oracle1/target.json').read_text())
        upload(q, row['target_table'], snap)
        rejects = json.loads((OUT / row['mapping'] / 'oracle1/rejects.json').read_text())
        records = [[cell(r['name']), cell(i), cell(line)] for r in rejects for i, line in enumerate(r['rows'], 1)]
        if records:
            upload(q, row['target_table'] + '__REJECTS', {
                'columns': ['FILE_NAME', 'LINE_NUMBER', 'RAW_RECORD'],
                'types': {'FILE_NAME': ['character varying', 200, None, None],
                          'LINE_NUMBER': ['bigint', None, 64, 0],
                          'RAW_RECORD': ['character varying', 4000, None, None]}, 'rows': records})


def smoke(q):
    schema = 'SFX_D1110_AFTER.PC_EVIDENCE_SMOKE'
    # Never replace or drop another execution's scratch schema.
    q.run(f"CREATE SCHEMA {schema} COMMENT='{COMMENT}'")
    results = {'label': 'HARNESS SMOKE — not mapping parity'}
    snap = json.loads((OUT / 'm_SFX_SECURITY_ALERT/oracle1/target.json').read_text())
    try:
        q.run(f'CREATE TABLE {schema}.RUN1 AS SELECT * FROM SFX_D1110_AFTER.PC_BEFORE.SECURITY_ALERT')
        run1 = fetched(q, schema + '.RUN1', snap)
        for case, mutation in [('identical', None),
                               ('duplicate_key', f'INSERT INTO {schema}.RUN2 SELECT * FROM {schema}.RUN1 LIMIT 1'),
                               ('changed_value', f"UPDATE {schema}.RUN2 SET STATUS_CD='SMOKE' WHERE ALERT_ID=(SELECT MIN(ALERT_ID) FROM {schema}.RUN1)"),
                               ('resequence_id', f'UPDATE {schema}.RUN2 SET ALERT_ID=ALERT_ID+900000000 WHERE ALERT_ID=(SELECT MIN(ALERT_ID) FROM {schema}.RUN1)')]:
            q.run(f'CREATE OR REPLACE TABLE {schema}.RUN2 AS SELECT * FROM {schema}.RUN1')
            if mutation:
                q.run(mutation)
            run2 = fetched(q, schema + '.RUN2', snap)
            result = replay_gate(snap, run1, run2, ['ALERT_ID'], ['ALERT_ID'])
            results[case] = result
            dump(LIVE / 'smoke.json', results)
            assert result['passed'] == (case == 'identical'), 'Smoke gate unexpected result: ' + case
        print('HARNESS SMOKE — identical pass; duplicate/value/ID mutations each fail')
    finally:
        q.run('DROP SCHEMA ' + schema + ' CASCADE')
        results['drop_qid'] = q.cursor.sfqid
        dump(LIVE / 'smoke.json', results)


def live(preflight_only=False):
    LIVE.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((OUT / 'manifest.json').read_text())
    with connection('parity', 'evidence_smoke') as conn, conn.cursor() as cur:
        q = Queries(cur)
        q.run('SELECT CURRENT_ACCOUNT(), CURRENT_ROLE(), CURRENT_DATABASE(), CURRENT_WAREHOUSE()')
        before = control(q)
        dump(LIVE / 'control_preflight.json', before)
        try:
            comparisons = {}
            for row in scope():
                if not row['landing_files']:
                    continue
                table = row['landing_files'][0].split('/')[-2]
                # Shared setup derives PC_SRC types from the matching STG bootstrap table.
                db = 'unt2_types_' + uuid.uuid4().hex[:12]
                params = local_params()
                with psycopg.connect(dbname='postgres', **params) as admin:
                    admin.execute(f'CREATE DATABASE {db}')
                    try:
                        with psycopg.connect(dbname=db, **params) as pg:
                            pg.execute('CREATE SCHEMA source_types')
                            body = table_definitions()[target_relation('STG_' + table)]
                            pg.execute(f'CREATE TABLE source_types.input ({body})')
                            template = snapshot(pg, 'source_types.input')
                    finally:
                        admin.execute(f'DROP DATABASE {db} WITH (FORCE)')
                expected = expected_landing(manifest, row, template)
                actual = fetched(q, 'SFX_D1110_AFTER.PC_SRC.' + table, template, source_loading=True)
                comparisons[table] = full_compare(expected, actual, template['columns'])
                dump(LIVE / 'input_freeze.json', comparisons)
            if not all(r['equal'] for r in comparisons.values()):
                raise ValueError('PC_SRC differs from frozen inputs; no setup/load or baseline writes performed')
            if not preflight_only:
                baselines(q)
                smoke(q)
            print('Live preflight and full input freeze: PASS')
        finally:
            after = control(q)
            dump(LIVE / 'control_postflight.json', after)
            unchanged = before == after
            dump(LIVE / 'control_preserved.json', {'byte_identical': unchanged})
            assert unchanged, 'Control rows changed during evidence execution'
