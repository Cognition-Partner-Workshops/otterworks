"""Run-scoped Snowflake assessment control plane; private key stays in memory."""

import sys as _run_sys
from pathlib import Path as _RunPath
_run_sys.path.insert(0, str(_RunPath(__file__).resolve().parents[3]))
from warehouse.run_config import render as _run_render

import argparse
import csv
import json
import os
import re
from pathlib import Path
import sys
from contextlib import contextmanager

import yaml
from psycopg import sql

from assess import OUT, before_state_root, build

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'warehouse/snowflake'))
from sfx_conn import query_tag as session_tag

DATABASE = _run_render('__RUN_DATABASE__')
WAREHOUSE = _run_render('__RUN_DATABASE___OPS_WH')
SCHEMA = DATABASE + '.MIGRATION_CONTROL'
COMMENT = _run_render('run_token=__RUN_TOKEN__ expires=2026-11-24')
MANIFEST_FIELDS = 'id system kind name source target_type target wave owner owner_source risk risk_reasons complexity status'.split()
CONSUMER_FIELDS = 'id name account owner owner_source risk wave status hidden applications clients scan'.split()
TABLES = {'MANIFEST', 'CONSUMERS', 'DBQL_QRYLOG', 'DBQL_OBJECTUSAGE', 'DBQL_TABLESV', 'CODE_PRINCIPALS'}
VIEWS = {'V_WAVE_SUMMARY', 'V_LICENCE_COUNTER', 'V_DEAD_OBJECTS', 'V_HIDDEN_CONSUMERS'}


def identifier(name, qualified=True):
    parts = name.split('.') if qualified else [name]
    if any(not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9$]*', p) for p in parts):
        raise ValueError('Unsafe load identifier')
    return sql.Identifier(*(p.upper() for p in parts))


def compose(template, *parts, **named):
    return sql.SQL(template).format(*parts, **named).as_string()


def query_tag(step):
    return session_tag('ops', 'assess', {'run': _run_render('__RUN_TOKEN__'), 'act': 'assess', 'step': step})


def tag(cursor, step):
    cursor.execute('ALTER SESSION SET QUERY_TAG = %s', (query_tag(step),))


def connection_options(env):
    if env.get('SNOWFLAKE_DATABASE') != DATABASE or env.get('RUN_TOKEN', 'sfx1119') != _run_render('__RUN_TOKEN__'):
        raise ValueError('Database/run-token scope mismatch')
    from cryptography.hazmat.primitives import serialization
    key = serialization.load_pem_private_key(env['SNOWFLAKE_PRIVATE_KEY'].encode(), password=None)
    return dict(account=env['SNOWFLAKE_ACCOUNT'], user=env['SNOWFLAKE_USER'], role=env['SNOWFLAKE_ROLE'],
                warehouse=WAREHOUSE, database=DATABASE, authenticator='SNOWFLAKE_JWT',
                private_key=key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()),
                session_parameters={'QUERY_TAG': query_tag('preflight')}, login_timeout=30, network_timeout=60)


@contextmanager
def session():
    import snowflake.connector
    connection = snowflake.connector.connect(**connection_options(os.environ))
    cursor = connection.cursor()
    try:
        yield cursor
    finally:
        try:
            cursor.execute('SHOW WAREHOUSES LIKE %s', (WAREHOUSE,))
            columns = [c[0].lower() for c in cursor.description]
            states = [dict(zip(columns, row)) for row in cursor.fetchall()]
            if len(states) != 1:
                raise RuntimeError('Expected one scoped operations warehouse')
            if states[0]['state'] != 'SUSPENDED':
                cursor.execute(compose('ALTER WAREHOUSE {} SUSPEND', identifier(WAREHOUSE)))
            print('Warehouse suspended: ' + WAREHOUSE)
        finally:
            cursor.close()
            connection.close()


def scalar(cursor, sql, params=None):
    cursor.execute(sql, params)
    return cursor.fetchone()[0]


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')) if isinstance(value, (dict, list)) else value


def insert_rows(cursor, table, fields, records):
    if table not in TABLES:
        raise ValueError('Unsafe load identifier')
    target = identifier(SCHEMA + '.' + table)
    columns = sql.SQL(',').join(identifier(f, qualified=False) for f in fields)
    for offset in range(0, len(records), 200):
        chunk = records[offset:offset + 200]
        placeholders = '(' + ','.join(['%s'] * len(fields)) + ')'
        cursor.execute(compose('INSERT INTO {} ({}) VALUES {}', target, columns, sql.SQL(','.join([placeholders] * len(chunk)))), tuple(encode(r.get(f)) for r in chunk for f in fields))
    print(f'Loaded {table}: {len(records)}')


def create_table(cursor, name, fields):
    if name not in TABLES:
        raise ValueError('Unsafe load identifier')
    columns = sql.SQL(', ').join(sql.Composed([identifier(f, qualified=False), sql.SQL(' ' + ('INTEGER' if f == 'wave' else "VARCHAR DEFAULT 'not_started'" if f == 'status' else 'VARCHAR'))]) for f in fields)
    extra = ", UPDATED_AT TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP(), UPDATED_BY_ACT VARCHAR DEFAULT 'assess'" if name == 'MANIFEST' else ''
    target = identifier(SCHEMA + '.' + name)
    cursor.execute(compose('CREATE TABLE IF NOT EXISTS {} ({}{}) COMMENT = %s', target, columns, sql.SQL(extra)), (COMMENT,))
    cursor.execute(compose('ALTER TABLE {} SET COMMENT = %s', target), (COMMENT,))


def view_sql():
    schema = identifier(SCHEMA)
    return {
        'V_WAVE_SUMMARY': compose('SELECT WAVE, TARGET_TYPE, STATUS, COUNT(*) AS OBJECT_COUNT FROM {schema}.MANIFEST GROUP BY WAVE, TARGET_TYPE, STATUS', schema=schema),
        'V_LICENCE_COUNTER': compose("""SELECT 'Teradata objects' AS COUNTER, COUNT(*) AS REMAINING, 0 AS TARGET FROM {schema}.MANIFEST
            WHERE SYSTEM='teradata' AND KIND IN ('table','view','macro','procedure','catalog') AND STATUS NOT IN ('done','retired')
            UNION ALL SELECT 'PowerCenter mappings', COUNT(*), 0 FROM {schema}.MANIFEST WHERE KIND='mapping' AND STATUS NOT IN ('done','retired')
            UNION ALL SELECT 'Spark executor-hours', 0, 0""", schema=schema),
        'V_DEAD_OBJECTS': compose("""SELECT T.DATABASENAME || '.' || T.TABLENAME AS OBJECT_NAME FROM {schema}.DBQL_TABLESV T
            WHERE T.DATABASENAME LIKE 'SFX_%' AND NOT EXISTS (
              SELECT 1 FROM {schema}.DBQL_OBJECTUSAGE O JOIN {schema}.DBQL_QRYLOG Q ON Q.QUERYID=O.QUERYID
              WHERE O.OBJECTDATABASENAME=T.DATABASENAME AND O.OBJECTTABLENAME=T.TABLENAME
              AND Q.STARTTIME::TIMESTAMP_NTZ >= '2026-08-12'::TIMESTAMP_NTZ AND Q.STARTTIME::TIMESTAMP_NTZ < '2026-11-10'::TIMESTAMP_NTZ)""", schema=schema),
        'V_HIDDEN_CONSUMERS': compose("""SELECT DISTINCT Q.USERNAME AS PRINCIPAL FROM {schema}.DBQL_QRYLOG Q
            WHERE Q.STATEMENTTYPE='SELECT' AND Q.STARTTIME::TIMESTAMP_NTZ >= '2026-08-12'::TIMESTAMP_NTZ
              AND Q.STARTTIME::TIMESTAMP_NTZ < '2026-11-10'::TIMESTAMP_NTZ
              AND NOT EXISTS (SELECT 1 FROM {schema}.CODE_PRINCIPALS C WHERE C.PRINCIPAL=Q.USERNAME)
              AND NOT EXISTS (SELECT 1 FROM {schema}.DBQL_QRYLOG B WHERE B.USERNAME=Q.USERNAME AND B.STATEMENTGROUP IN ('ETL','UTILITY','BATCH'))""", schema=schema)
    }


def load(cursor):
    data = yaml.safe_load(_run_render((OUT / 'manifest.yaml').read_text()))
    tag(cursor, 'create_schema')
    cursor.execute(compose('CREATE SCHEMA IF NOT EXISTS {} COMMENT = %s', identifier(SCHEMA)), (COMMENT,))
    cursor.execute(compose('ALTER SCHEMA {} SET COMMENT = %s', identifier(SCHEMA)), (COMMENT,))
    create_table(cursor, 'MANIFEST', MANIFEST_FIELDS)
    create_table(cursor, 'CONSUMERS', CONSUMER_FIELDS)
    create_table(cursor, 'CODE_PRINCIPALS', ['principal', 'source', 'scope'])
    csv_data = {}
    dbql = before_state_root() / 'warehouse/teradata/dbql'
    for table, filename in [('DBQL_QRYLOG', 'qrylog.csv'), ('DBQL_OBJECTUSAGE', 'objectusage.csv'), ('DBQL_TABLESV', 'tablesv.csv')]:
        with (dbql / filename).open() as stream:
            reader = csv.DictReader(stream)
            fields = reader.fieldnames
            records = list(reader)
        create_table(cursor, table, fields)
        csv_data[table] = (fields, records)
    tag(cursor, 'load_manifest')
    # A single DML transaction replaces all datasets together. DDL is outside it.
    cursor.execute('BEGIN')
    try:
        for table in sorted(TABLES):
            cursor.execute(compose('DELETE FROM {}', identifier(SCHEMA + '.' + table)))
        insert_rows(cursor, 'MANIFEST', MANIFEST_FIELDS, data['objects'])
        insert_rows(cursor, 'CONSUMERS', CONSUMER_FIELDS, data['consumers'])
        scans = build()['scans']
        records = [{'principal': p, 'source': path, 'scope': 'warehouse_etl' if path in scan['warehouse_etl_hits'] else 'repository'} for p, scan in scans.items() for path in scan['repo_hits']]
        insert_rows(cursor, 'CODE_PRINCIPALS', ['principal', 'source', 'scope'], records)
        tag(cursor, 'load_dbql')
        for table, (fields, records) in csv_data.items():
            insert_rows(cursor, table, fields, records)
        cursor.execute('COMMIT')
    except Exception:
        cursor.execute('ROLLBACK')
        raise
    for name, query in view_sql().items():
        tag(cursor, 'dead_objects' if name == 'V_DEAD_OBJECTS' else 'hidden_consumers' if name == 'V_HIDDEN_CONSUMERS' else 'create_schema')
        cursor.execute(compose('CREATE OR REPLACE VIEW {} COMMENT = %s AS {}', identifier(SCHEMA + '.' + name), sql.SQL(query.replace('%', '%%'))), (COMMENT,))
    print('LOAD COMPLETE')


def verify(cursor):
    tag(cursor, 'preflight')
    exists = scalar(cursor, compose("SELECT COUNT(*) FROM {}.INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME='MIGRATION_CONTROL'", identifier(DATABASE)))
    if not exists:
        print(_run_render('FAIL | schema | __RUN_DATABASE__.MIGRATION_CONTROL missing'))
        return False
    tag(cursor, 'verify')
    data = yaml.safe_load(_run_render((OUT / 'manifest.yaml').read_text()))
    checks = []
    for table, key in [('MANIFEST', 'objects'), ('CONSUMERS', 'consumers')]:
        count = scalar(cursor, compose('SELECT COUNT(*) FROM {}', identifier(SCHEMA + '.' + table)))
        checks.append((table, count == len(data[key]), f'{count}/{len(data[key])} rows'))
    cursor.execute(compose("SELECT TABLE_NAME, COMMENT FROM {}.INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='MIGRATION_CONTROL'", identifier(DATABASE)))
    comments = dict(cursor.fetchall())
    schema_comment = scalar(cursor, compose("SELECT COMMENT FROM {}.INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME='MIGRATION_CONTROL'", identifier(DATABASE)))
    checks.append(('comments', set(comments) == TABLES | VIEWS and all(v == COMMENT for v in comments.values()) and schema_comment == COMMENT, f'{len(comments)} tables/views + schema'))
    tag(cursor, 'dead_objects')
    cursor.execute(compose('SELECT OBJECT_NAME FROM {}.V_DEAD_OBJECTS ORDER BY OBJECT_NAME', identifier(SCHEMA)))
    dead = [r[0] for r in cursor.fetchall()]
    checks.append(('dead objects', len(dead) == 6 and dead == sorted(data['dead']), str(len(dead))))
    tag(cursor, 'hidden_consumers')
    cursor.execute(compose('SELECT PRINCIPAL FROM {}.V_HIDDEN_CONSUMERS ORDER BY PRINCIPAL', identifier(SCHEMA)))
    hidden = [r[0] for r in cursor.fetchall()]
    checks.append(('hidden consumers', hidden == sorted(r['account'] for r in data['consumers'] if r['hidden']), ', '.join(hidden)))
    print('RESULT | CHECK | ACTUAL')
    for name, passed, actual in checks:
        print(f"{'PASS' if passed else 'FAIL'} | {name} | {actual}")
    return all(passed for _, passed, _ in checks)


def report(cursor):
    tag(cursor, 'verify')
    queries = [compose(template, identifier(SCHEMA)) for template in (
        'SELECT WAVE, SUM(OBJECT_COUNT) AS OBJECT_COUNT FROM {}.V_WAVE_SUMMARY GROUP BY WAVE ORDER BY WAVE',
        'SELECT * FROM {}.V_LICENCE_COUNTER ORDER BY COUNTER', 'SELECT * FROM {}.V_DEAD_OBJECTS ORDER BY OBJECT_NAME',
        'SELECT * FROM {}.V_HIDDEN_CONSUMERS ORDER BY PRINCIPAL')]
    for sql in queries:
        print(sql + ';')
        cursor.execute(sql)
        print(' | '.join(c[0] for c in cursor.description))
        for row in cursor.fetchall():
            print(' | '.join(str(v) for v in row))


def history(cursor):
    tag(cursor, 'verify')
    sql = _run_render((OUT / 'query_history_assess.sql').read_text())
    print(sql)
    cursor.execute(sql)
    print(' | '.join(c[0] for c in cursor.description))
    for row in cursor.fetchall():
        print(' | '.join(str(v) for v in row))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['load', 'verify', 'report', 'history'])
    args = parser.parse_args()
    with session() as cursor:
        if args.command == 'load':
            load(cursor)
        elif args.command == 'verify':
            if not verify(cursor):
                return 1
        elif args.command == 'report':
            report(cursor)
        else:
            history(cursor)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
