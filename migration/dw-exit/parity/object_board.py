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
MIGRATION = ROOT / 'migration/dw-exit'
MANIFEST = MIGRATION / 'manifest.yaml'
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'migration/dw-exit/tools'))
sys.path.insert(0, str(ROOT / 'migration/dw-exit'))
from warehouse.run_config import RunConfig
from assess import board as wave_board, licence_counters
from parity import connection as snowflake_connection
from parity.ladder import identifier, relation as snowflake_relation


def quote(name):
    return '"' + name.replace('"', '""') + '"'


def relation(name):
    parts = name.split('.')
    if len(parts) != 2:
        raise ValueError('Expected schema.relation')
    return '.'.join(map(quote, parts))


def canonical(value):
    return json.dumps(value, default=str, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def measure(connection, name):
    # Relation and column identifiers are double-quoted, not SQL value parameters.
    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
    cursor = connection.execute('SELECT * FROM ' + relation(name))
    columns = [col[0] for col in cursor.description]
    rows = cursor.fetchall()
    profiles = {}
    for column in columns:
        c = quote(column)
        # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        values = connection.execute(f'SELECT COUNT(*)-COUNT({c}), MIN({c}), MAX({c}), COUNT(DISTINCT {c}) FROM {relation(name)}').fetchone()
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
                        definitions.append(quote(column.upper())+' '+kind)
                    source_schema, source_table = name.split('.')
                    # Identifiers are quoted; column types come from the fixed mapping above.
                    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                    connection.execute('CREATE SCHEMA IF NOT EXISTS '+quote(source_schema))
                    # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                    connection.execute(f'CREATE TABLE {relation(name)} ({", ".join(definitions)})')
                    # psycopg Identifier quotes both catalog-derived identifiers.
                    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                    cursor.execute(sql.SQL('SELECT * FROM {}.{}').format(sql.Identifier(schema),sql.Identifier(table)))
                    rows = cursor.fetchall()
                    if rows:
                        connection.executemany(f'INSERT INTO {relation(name)} VALUES ({", ".join("?" for _ in cols)})', rows)
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
        # DuckDB metadata and identifiers are local; relation()/quote() escape identifiers.
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        definitions = before.execute('DESCRIBE '+relation(name)).fetchall()
        # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        after.execute(f'CREATE TABLE {relation(target)} ({", ".join(quote(c[0])+" "+c[1] for c in definitions)})')
        if table.startswith('STG_'):
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            rows = before.execute('SELECT * FROM '+relation(name)).fetchall()
            if rows:
                after.executemany(f'INSERT INTO {relation(target)} VALUES ({", ".join("?" for _ in definitions)})', rows)
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


FIELDS = ('row_count', 'column_profile', 'keyed_row_hash', 'sampled_differences')
CREDENTIALS = ('SNOWFLAKE_ACCOUNT', 'SNOWFLAKE_USER', 'SNOWFLAKE_ROLE', 'SNOWFLAKE_PRIVATE_KEY')


def empty_leg(reason=None):
    return dict(status='red', reason=reason, **dict.fromkeys(FIELDS))


class SnowflakeMeasurements:
    def __init__(self):
        self.connection = None
        self.query_ids = []
        self.session_query_ids = []
        self.error = 'Snowflake credentials unavailable'
        if all(os.environ.get(key) for key in CREDENTIALS):
            try:
                self.connection = snowflake_connection.connect('parity-board')
                tag = canonical({'run_id': RunConfig.from_env().token, 'act': 'prove', 'step': 'parity-board'})
                self.query("ALTER SESSION SET QUERY_TAG='" + tag.replace("'", "''") + "'")
                self.query("ALTER SESSION SET TIMEZONE='UTC'")
                self.session_query_ids = list(self.query_ids)
                self.error = None
            except Exception as error:
                self.error = 'Snowflake session failed: ' + type(error).__name__

    def query(self, statement):
        with self.connection.cursor() as cursor:
            try:
                cursor.execute(statement)
                columns = [c[0] for c in cursor.description] if cursor.description else []
                return columns, cursor.fetchall()
            finally:
                if getattr(cursor, 'sfqid', None):
                    self.query_ids.append(cursor.sfqid)

    def compare(self, before, source, destination):
        snowflake_relation(snowflake_connection.DATABASE + '.' + source)
        qualified = snowflake_connection.DATABASE + '.' + destination
        try:
            columns, rows = self.query('SELECT * FROM ' + snowflake_relation(qualified))
        except Exception as error:
            if getattr(error, 'errno', None) == 2003 or getattr(error, 'sqlstate', None) == '42S02':
                raise ValueError('output not materialized in Snowflake: ' + qualified) from error
            raise
        with duckdb.connect() as local:
            definitions = before.execute('DESCRIBE SELECT * FROM query_table(?)', [source]).fetchall()
            if columns != [c[0] for c in definitions]:
                raise ValueError('Output column names/order differ')
            for column, kind, *_ in definitions:
                identifier(column)
                if not re.fullmatch(r'(?:SMALLINT|INTEGER|BIGINT|DATE|TIMESTAMP(?: WITH TIME ZONE)?|BOOLEAN|FLOAT|DOUBLE|BLOB|VARCHAR|DECIMAL\([0-9]+,[0-9]+\))', kind):
                    raise ValueError('Unsupported snapshot column type: ' + kind)
            staging = 'main.snapshot'
            create = exp.Create(
                this=exp.Schema(this=exp.Table(this=exp.to_identifier('snapshot'), db=exp.to_identifier('main')),
                    expressions=[exp.ColumnDef(this=exp.to_identifier(c[0], quoted=True),
                        kind=exp.DataType.build(c[1], dialect='duckdb')) for c in definitions]),
                kind='TABLE')
            local.execute(create.sql(dialect='duckdb'))
            if rows:
                insert = exp.Insert(this=exp.Table(this=exp.to_identifier('snapshot'), db=exp.to_identifier('main')),
                    expression=exp.Values(expressions=[exp.Tuple(expressions=[exp.Placeholder() for _ in columns])]))
                local.executemany(insert.sql(dialect='duckdb'), rows)
            return compare(before, local, source, staging)

    def exists(self, obj):
        target = obj.get('target', '')
        parts = target.split('.')
        if len(parts) != 2 or target == 'NONE':
            return False
        schema, name = parts
        identifier(name)
        scope = identifier(snowflake_connection.DATABASE) + '.' + identifier(schema)
        kind = 'TASKS' if obj['kind'] in ('session', 'workflow', 'worklet') else 'PROCEDURES'
        columns, rows = self.query('SHOW ' + kind + ' IN SCHEMA ' + scope)
        index = [c.lower() for c in columns].index('name')
        return any(str(row[index]).upper() == name.upper() for row in rows)

    def close(self):
        if self.connection is not None:
            self.connection.close()


def declared_outputs(obj):
    outputs = obj.get('output_relations', [])
    if outputs or obj.get('system') != 'spark':
        return outputs
    registry = ROOT / 'etl/spark/jobs/registry' / (obj['name'] + '.yaml')
    declarations = [yaml.safe_load(registry.read_text())] if registry.is_file() else []
    classification = ROOT / 'etl/spark/classification.yaml'
    if classification.is_file():
        declarations += [r for r in yaml.safe_load(classification.read_text()) if r['job'] == obj['name']]
    return sorted({r for declaration in declarations for r in declaration.get('output_relations', [])})


def update_migration_summary(result, objects):
    statuses = {obj['id']: obj.get('status', 'not_started') for obj in objects}
    rows = result['rows']
    for row in rows:
        row['migration_status'] = statuses[row['id']]
    pending = [row for row in rows if row['migration_status'] != 'migrated']
    remaining_by_system = Counter(r['licence_dependency'] for r in pending if r['licence_dependency'] != 'none')
    result['summary'].update(
        migrated=len(rows) - len(pending),
        migrated_areas=len({r['subject_area'] for r in rows} - {r['subject_area'] for r in pending}),
        licence_total=sum(r['licence_dependency_count'] for r in rows),
        licence_remaining=sum(remaining_by_system.values()),
        licence_by_system=dict(remaining_by_system),
    )
    result['licence_counters'] = licence_counters(objects, result['licence_counters'])


def build_board(manifest, before=None, after=None, available=None, errors=None, target='duckdb',
                counters=None, subject_area=None, snowflake=None):
    if target not in ('duckdb', 'snowflake'):
        raise ValueError('Unsupported parity target')
    objects = manifest['objects']
    selected = [o for o in objects if subject_area is None or o['subject_area'] == subject_area]
    result = wave_board(selected, counters or {})
    result.update(run_token=RunConfig.from_env().token, target=target, rows=[])
    result['measurement_contract'] = {'source': 'PostgreSQL Teradata emulator snapshot',
        'local_target': 'DuckDB', 'conversions': ['billing/initial/10_load.sql','billing/initial/30_views.sql'],
        'non_relational_objects': 'dependency parity and routine existence', 'migration_state': 'manifest'}
    if target == 'duckdb' and os.environ.get('BOARD_DUCKDB_PATH'):
        result['measurement_contract']['conversions'] = ['operator-provisioned DuckDB target']
    available, errors = set(available or ()), errors or {}
    own_snowflake = snowflake is None
    snowflake = snowflake or SnowflakeMeasurements()
    by_id = {o['id']: o for o in objects}
    dependencies = {o['id']: set(o.get('depends_on', [])) for o in objects}
    for a, b in manifest.get('dependencies', []):
        if a not in by_id or b not in by_id:
            continue
        if by_id[b]['kind'] in ('session', 'workflow', 'worklet'):
            dependencies[b].add(a)
        else:
            dependencies[a].add(b)
    cache, visiting = {}, set()

    def leg_for(obj, side):
        key = (obj['id'], side)
        if key in cache:
            return cache[key]
        leg = empty_leg()
        if side == 'snowflake':
            leg['query_ids'] = list(snowflake.session_query_ids)
            if snowflake.error:
                leg['reason'] = snowflake.error
                cache[key] = leg
                return leg
        if key in visiting:
            return empty_leg('dependency cycle: ' + obj['id'])
        visiting.add(key)
        query_start = len(snowflake.query_ids)
        outputs = declared_outputs(obj)
        try:
            if outputs:
                measured = {}
                for source in outputs:
                    destination = source.removeprefix('SFX_')
                    if side == 'duckdb' and destination not in available:
                        leg['reason'] = errors.get(destination, errors.get('*', 'output not materialized: ' + destination))
                        break
                    measured[source] = (compare(before, after, source, destination) if side == 'duckdb'
                                        else snowflake.compare(before, source, destination))
                if leg['reason'] is None:
                    leg['row_count'] = {s: sum(r['row_count'][s] for r in measured.values()) for s in ('before', 'after')}
                    for field in FIELDS[1:]:
                        leg[field] = {name: values[field] for name, values in measured.items()}
                    leg['status'] = 'green' if all(r['passed'] for r in measured.values()) else 'red'
                    leg['reason'] = None if leg['status'] == 'green' else 'measured parity mismatch'
            else:
                deps = sorted(dependencies[obj['id']])
                if not deps:
                    leg['reason'] = 'no dependency declared'
                else:
                    for dep in deps:
                        if dep not in by_id or leg_for(by_id[dep], side)['status'] != 'green':
                            leg['reason'] = 'dependency red: ' + dep
                            break
                    if leg['reason'] is None:
                        artifact = obj.get('converted_artifact')
                        exists = (bool(artifact) and (ROOT / artifact).is_file()) if side == 'duckdb' else snowflake.exists(obj)
                        if exists:
                            leg.update(status='green', reason=None)
                        else:
                            leg['reason'] = 'routine missing: ' + str(obj.get('target', obj['name']))
        except Exception as error:
            message = str(error).splitlines()[0]
            leg['reason'] = message if message.startswith('output not materialized in Snowflake: ') else 'measurement failed: ' + message
        finally:
            visiting.remove(key)
        if side == 'snowflake':
            leg['query_ids'] += snowflake.query_ids[query_start:]
        cache[key] = leg
        return leg

    try:
        for obj in selected:
            row = {key: obj[key] for key in ('id','name','kind','wave','owner','subject_area','licence_dependency')}
            for key in ('source', 'source_ref'):
                if key in obj:
                    row[key] = obj[key]
            legs = {side: leg_for(obj, side) for side in ('duckdb', 'snowflake')}
            red = next((side for side in legs if legs[side]['status'] == 'red'), None)
            row.update(legs=legs, status='red' if red else 'green',
                       reason=red + ': ' + legs[red]['reason'] if red else None,
                       licence_dependency_count=int(obj['licence_dependency'] != 'none'))
            row.update({field: legs['duckdb'][field] for field in FIELDS})
            result['rows'].append(row)
    finally:
        if own_snowflake:
            snowflake.close()
    def counts(rows):
        return dict(green=sum(r['status']=='green' for r in rows), red=sum(r['status']=='red' for r in rows),
                    measured=sum(r['row_count'] is not None for r in rows))
    result['summary'] = dict(rows=len(selected), **counts(result['rows']),
        legs={side: counts([r['legs'][side] for r in result['rows']]) for side in ('duckdb', 'snowflake')})
    update_migration_summary(result, selected)
    return result


def measure_board(manifest, *, target='duckdb', counters=None, subject_area=None, snowflake=None):
    before = after = None
    ready, errors = set(), {}
    try:
        if manifest['objects']:
            names = {r for obj in manifest['objects'] for r in declared_outputs(obj)}
            ns = os.environ.get('NS',RunConfig.from_env().before_namespace)
            port = os.environ.get('TD_PG_PORT',str(54500+zlib.crc32(ns.encode())%1000))
            dsn = os.environ.get('BOARD_SOURCE_DSN',f'host=127.0.0.1 port={port} dbname=teradata user=postgres')
            before, source_ready, source_errors = source_snapshot(dsn,names)
            if target == 'duckdb':
                if local_target := os.environ.get('BOARD_DUCKDB_PATH'):
                    after = duckdb.connect(local_target, read_only=True)
                    ready = {f'{schema}.{table}'.upper() for schema, table in after.execute(
                        'SELECT table_schema, table_name FROM information_schema.tables').fetchall()}
                else:
                    after, ready, errors = materialize(before, source_ready, MIGRATION/'billing/initial')
            errors.update(source_errors)
        return build_board(manifest, before, after, ready, errors, target=target, counters=counters,
                           subject_area=subject_area, snowflake=snowflake)
    finally:
        if before is not None:
            before.close()
        if after is not None:
            after.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, default=MANIFEST)
    parser.add_argument('--output', type=Path, default=MIGRATION/'board/board.json')
    parser.add_argument('--target', choices=['duckdb','snowflake'], default=os.environ.get('PARITY_TARGET','duckdb'))
    parser.add_argument('--subject-area')
    args = parser.parse_args()
    manifest = yaml.safe_load(args.manifest.read_text())
    from assess import build
    payload = measure_board(manifest, target=args.target, counters=build()['counters'],
                            subject_area=args.subject_area)
    args.output.write_text(json.dumps(payload, indent=2, default=str) + '\n')
    print(json.dumps(payload['summary'], sort_keys=True))


if __name__ == '__main__':
    main()
