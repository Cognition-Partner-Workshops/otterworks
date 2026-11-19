"""Measure declared outputs without changing migration or retirement state."""
import argparse
from collections import Counter
import hashlib
import json
import os
import re
from pathlib import Path
import sys
import zlib

import duckdb
import psycopg
from psycopg import sql
import sqlglot
from sqlglot import exp
import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'migration/dw-exit/tools'))
from warehouse.run_config import RunConfig
from assess import board as wave_board
from parity.sql import compose, identifier


def quote(name):
    return identifier(name, 'duckdb', qualified=False, preserve_case=True).as_string()


def relation(name):
    parts = name.split('.')
    if len(parts) != 2:
        raise ValueError('Expected schema.relation')
    return '.'.join(map(quote, parts))


def ident(name):
    relation(name)
    return identifier(name, 'duckdb', preserve_case=True)


def column_definition(name, kind):
    if not re.fullmatch(r'SMALLINT|INTEGER|BIGINT|DATE|TIMESTAMP|TIMESTAMPTZ|TIMESTAMP WITH TIME ZONE|BOOLEAN|FLOAT|DOUBLE|BLOB|VARCHAR|DECIMAL\(\d+,\d+\)', kind):
        raise ValueError(f'Unsupported column type: {kind}')
    return sql.Composed([identifier(name, 'duckdb', qualified=False, preserve_case=True), sql.SQL(' ' + kind)])


def canonical(value):
    return json.dumps(value, default=str, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def measure(connection, name):
    cursor = connection.execute(compose('SELECT * FROM {}', ident(name)))
    columns = [col[0] for col in cursor.description]
    rows = cursor.fetchall()
    profiles = {}
    for column in columns:
        c = identifier(column, 'duckdb', qualified=False, preserve_case=True)
        values = connection.execute(compose('SELECT COUNT(*)-COUNT({c}), MIN({c}), MAX({c}), COUNT(DISTINCT {c}) FROM {table}', c=c, table=ident(name))).fetchone()
        profiles[column] = dict(zip(('nulls', 'min', 'max', 'distinct'), values))
    return columns, rows, profiles


def compare(before, after, source, target, sample_size=5):
    bcols, brows, bp = measure(before, source)
    acols, arows, ap = measure(after, target)
    if not bcols or bcols != acols:
        raise ValueError('Output column names/order differ')
    def digests(rows):
        return Counter((canonical(row[:1]), hashlib.sha256(canonical(row).encode()).hexdigest()) for row in rows)
    bh, ah = digests(brows), digests(arows)
    def checksum(values):
        return hashlib.sha256(canonical(sorted((key,digest,count) for (key,digest),count in values.items())).encode()).hexdigest()
    delta = (bh-ah) + (ah-bh)
    mismatched_keys = {key for key, digest in delta}
    samples = []
    for key in sorted(mismatched_keys)[:sample_size]:
        samples.append({'key': json.loads(key),
                        'before': sorted((r for r in brows if canonical(r[:1]) == key), key=canonical)[:sample_size],
                        'after': sorted((r for r in arows if canonical(r[:1]) == key), key=canonical)[:sample_size]})
    return {'row_count': {'before': len(brows), 'after': len(arows)},
            'column_profile': {'before': bp, 'after': ap},
            'keyed_row_hash': {'keys': bcols[:1], 'difference': sum(delta.values()),
                               'before': checksum(bh), 'after': checksum(ah),
                               'key_policy': 'first declared column; full-row digest preserves multiplicity'},
            'sampled_differences': samples,
            'passed': len(brows) == len(arows) and canonical(bp) == canonical(ap) and not delta}


def source_snapshot(dsn, names):
    connection = duckdb.connect()
    ready, errors = set(), {}
    with psycopg.connect(dsn) as source:
        with source.cursor() as cursor:
            cursor.execute("SELECT table_schema,table_name,column_name,data_type,numeric_precision,numeric_scale FROM information_schema.columns WHERE table_schema LIKE 'sfx_%' ORDER BY table_schema,table_name,ordinal_position")
            columns = {}
            for schema, table, column, dtype, precision, scale in cursor:
                columns.setdefault((schema, table), []).append((column, dtype, precision, scale))
            index = {(s+'.'+t).upper(): (s,t,cols) for (s,t),cols in columns.items()}
            for name in sorted(names):
                if name not in index:
                    errors[name] = 'source output unavailable'
                    continue
                schema, table, cols = index[name]
                try:
                    definitions = []
                    for column, dtype, precision, scale in cols:
                        kind = {'smallint': 'SMALLINT', 'integer': 'INTEGER', 'bigint': 'BIGINT',
                                'date': 'DATE', 'timestamp without time zone': 'TIMESTAMP',
                                'timestamp with time zone': 'TIMESTAMPTZ', 'boolean': 'BOOLEAN',
                                'real': 'FLOAT', 'double precision': 'DOUBLE', 'bytea': 'BLOB'}.get(dtype, 'VARCHAR')
                        if dtype == 'numeric':
                            kind = f'DECIMAL({precision or 38},{scale or 0})'
                        definitions.append(column_definition(column.upper(), kind))
                    source_schema, source_table = name.split('.')
                    connection.execute(compose('CREATE SCHEMA IF NOT EXISTS {}', identifier(source_schema, 'duckdb', preserve_case=True)))
                    connection.execute(compose('CREATE TABLE {} ({})', ident(name), sql.SQL(', ').join(definitions)))
                    cursor.execute(compose('SELECT * FROM {}', identifier(schema + '.' + table, 'postgres', preserve_case=True)))
                    rows = cursor.fetchall()
                    if rows:
                        connection.executemany(compose('INSERT INTO {} VALUES ({})', ident(name), sql.SQL(', '.join('?' for _ in cols))), rows)
                    ready.add(name)
                except (duckdb.Error, psycopg.Error, ValueError) as error:
                    errors[name] = 'source snapshot: '+type(error).__name__
                    source.rollback()
    return connection, ready, errors


def materialize(before, names, conversion_dir):
    after = duckdb.connect()
    ready, errors = set(), {}
    after.execute('CREATE SCHEMA BILLING')
    for name in sorted(names):
        if not name.startswith('SFX_BILLING.'):
            continue
        table = name.split('.')[1]
        if table.startswith('V_'):
            continue
        target = 'BILLING.'+table
        definitions = before.execute(compose('DESCRIBE {}', ident(name))).fetchall()
        after.execute(compose('CREATE TABLE {} ({})', ident(target), sql.SQL(', ').join(column_definition(c[0], c[1]) for c in definitions)))
        if table.startswith('STG_'):
            rows = before.execute(compose('SELECT * FROM {}', ident(name))).fetchall()
            if rows:
                after.executemany(compose('INSERT INTO {} VALUES ({})', ident(target), sql.SQL(', '.join('?' for _ in definitions))), rows)
            ready.add(target)
    for filename in ('10_load.sql', '30_views.sql'):
        text = RunConfig.from_env().render((conversion_dir / filename).read_text())
        try:
            statements = sqlglot.parse(text, read='snowflake')
        except sqlglot.errors.ParseError:
            errors['*'] = 'conversion parse failed: '+filename
            continue
        for statement in statements:
            if statement is None:
                continue
            for table in statement.find_all(exp.Table):
                table.set('catalog', None)
            if isinstance(statement, exp.Create):
                target = statement.this.sql(dialect='duckdb', comments=False)
                query = statement.expression
                if not isinstance(query, exp.Query):
                    continue
                references = {(t.db+'.'+t.name).upper() for t in query.find_all(exp.Table)}
                if not references <= ready:
                    errors[target] = 'conversion input not materialized'
                    continue
                statement.set('properties', None)
            elif isinstance(statement, (exp.Insert, exp.Delete)):
                target = statement.this.sql(dialect='duckdb', comments=False)
                references = {(t.db+'.'+t.name).upper() for t in statement.expression.find_all(exp.Table)} if isinstance(statement, exp.Insert) else set()
                if not references <= ready:
                    errors[target] = 'conversion input not materialized'
                    continue
            else:
                continue
            try:
                after.execute(statement.sql(dialect='duckdb', comments=False))
                if not isinstance(statement, exp.Delete):
                    ready.add(target)
            except duckdb.Error as error:
                ready.discard(target)
                errors[target] = 'conversion failed: '+str(error).splitlines()[0]
    return after, ready, errors


def build_board(manifest, before=None, after=None, available=None, errors=None, target='duckdb', counters=None):
    if target not in ('duckdb', 'snowflake'):
        raise ValueError('Unsupported parity target')
    objects = manifest['objects']
    result = wave_board(objects, counters or {})
    result.update(run_token=RunConfig.from_env().token, target=target, rows=[])
    result['measurement_contract'] = {'source': 'PostgreSQL Teradata emulator snapshot',
        'local_target': 'DuckDB', 'conversions': ['billing/initial/10_load.sql','billing/initial/30_views.sql'],
        'non_relational_objects': 'declared output relations', 'migration_state': 'BEFORE'}
    available, errors = set(available or ()), errors or {}
    for obj in objects:
        row = {key:obj[key] for key in ('id','name','kind','wave','owner','subject_area','licence_dependency')}
        row.update(status='red', migration_status='not_started', licence_dependency_count=int(obj['licence_dependency'] != 'none'),
                   row_count=None, column_profile=None, keyed_row_hash=None, sampled_differences=None, reason=None)
        if obj['system'] == 'spark':
            if obj.get('source') and (ROOT / obj['source']).is_file():
                row.update(source=obj['source'], source_ref=obj.get('source_ref'))
                row['reason'] = 'Spark source available; output not materialized locally'
            else:
                row['reason'] = 'source on Spark baseline PR'
        elif target == 'snowflake':
            row['reason'] = 'Snowflake target selected; execution disabled'
        elif not obj.get('output_relations'):
            row['reason'] = 'no declared output relation'
        else:
            measured = {}
            for source in obj['output_relations']:
                destination = source.removeprefix('SFX_')
                if destination not in available:
                    row['reason'] = errors.get(destination, errors.get('*', 'output not materialized: '+destination))
                    break
                try:
                    measured[source] = compare(before, after, source, destination)
                except (duckdb.Error, ValueError) as error:
                    row['reason'] = 'measurement failed: '+str(error).splitlines()[0]
                    break
            if row['reason'] is None:
                row['row_count'] = {side:sum(r['row_count'][side] for r in measured.values()) for side in ('before','after')}
                for field in ('column_profile','keyed_row_hash','sampled_differences'):
                    row[field] = {name:values[field] for name,values in measured.items()}
                row['status'] = 'green' if all(r['passed'] for r in measured.values()) else 'red'
                if row['status'] == 'red':
                    row['reason'] = 'measured parity mismatch'
        result['rows'].append(row)
    total = sum(r['licence_dependency_count'] for r in result['rows'])
    result['summary'] = dict(rows=len(objects), red=sum(r['status']=='red' for r in result['rows']),
        green=sum(r['status']=='green' for r in result['rows']), measured=sum(r['row_count'] is not None for r in result['rows']),
        migrated=0, licence_remaining=total, licence_total=total,
        licence_by_system=dict(Counter(r['licence_dependency'] for r in result['rows'] if r['licence_dependency']!='none')))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest',type=Path,default=ROOT/'migration/dw-exit/manifest.yaml')
    parser.add_argument('--output',type=Path,default=ROOT/'migration/dw-exit/board/board.json')
    parser.add_argument('--target',choices=['duckdb','snowflake'],default=os.environ.get('PARITY_TARGET','duckdb'))
    args = parser.parse_args()
    manifest = yaml.safe_load(args.manifest.read_text())
    from assess import build
    counters = build()['counters']
    before = after = None
    ready, errors = set(), {}
    try:
        if args.target == 'duckdb' and manifest['objects']:
            names = {r for obj in manifest['objects'] for r in obj.get('output_relations',[])}
            ns = os.environ.get('NS',RunConfig.from_env().before_namespace)
            port = os.environ.get('TD_PG_PORT',str(54500+zlib.crc32(ns.encode())%1000))
            dsn = os.environ.get('BOARD_SOURCE_DSN',f'host=127.0.0.1 port={port} dbname=teradata user=postgres')
            before, source_ready, source_errors = source_snapshot(dsn,names)
            after, ready, errors = materialize(before,source_ready,ROOT/'migration/dw-exit/billing/initial')
            errors.update(source_errors)
        payload = build_board(manifest,before,after,ready,errors,target=args.target,counters=counters)
        args.output.write_text(json.dumps(payload,indent=2,default=str)+'\n')
        print(json.dumps(payload['summary'],sort_keys=True))
    finally:
        if before is not None:
            before.close()
        if after is not None:
            after.close()


if __name__ == '__main__':
    main()
