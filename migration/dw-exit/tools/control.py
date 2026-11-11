"""Run-scoped Snowflake assessment control plane; private key stays in memory."""
import argparse
import csv
import json
import os
from contextlib import contextmanager

import yaml

from assess import OUT, before_state_root, build

DATABASE = 'SFX_D1110_AFTER'
WAREHOUSE = 'SFX_D1110_OPS_WH'
SCHEMA = DATABASE + '.MIGRATION_CONTROL'
COMMENT = 'run_token=sfx-d1110 expires=2026-11-24'
MANIFEST_FIELDS = 'id system kind name source target_type target wave owner owner_source risk risk_reasons complexity status'.split()
CONSUMER_FIELDS = 'id name account owner owner_source risk wave status hidden applications clients scan'.split()
TABLES = {'MANIFEST', 'CONSUMERS', 'DBQL_QRYLOG', 'DBQL_OBJECTUSAGE', 'DBQL_TABLESV', 'CODE_PRINCIPALS'}
VIEWS = {'V_WAVE_SUMMARY', 'V_LICENCE_COUNTER', 'V_DEAD_OBJECTS', 'V_HIDDEN_CONSUMERS'}


def query_tag(step):
    return json.dumps({'run': 'sfx-d1110', 'act': 'assess', 'step': step}, separators=(',', ':'))


def tag(cursor, step):
    cursor.execute('ALTER SESSION SET QUERY_TAG = %s', (query_tag(step),))


def connection_options(env):
    if env.get('SNOWFLAKE_DATABASE') != DATABASE or env.get('SNOWFLAKE_RUN_TOKEN') != 'sfx-d1110':
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
            cursor.execute("SHOW WAREHOUSES LIKE '" + WAREHOUSE + "'")
            columns = [c[0].lower() for c in cursor.description]
            states = [dict(zip(columns, row)) for row in cursor.fetchall()]
            if len(states) != 1:
                raise RuntimeError('Expected one scoped operations warehouse')
            if states[0]['state'] != 'SUSPENDED':
                cursor.execute('ALTER WAREHOUSE ' + WAREHOUSE + ' SUSPEND')
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
    if table not in TABLES or any(not f.replace('_', '').isalnum() for f in fields):
        raise ValueError('Unsafe load identifier')
    for offset in range(0, len(records), 200):
        chunk = records[offset:offset + 200]
        placeholders = '(' + ','.join(['%s'] * len(fields)) + ')'
        cursor.execute('INSERT INTO ' + SCHEMA + '.' + table + ' (' + ','.join('"' + f.upper() + '"' for f in fields) + ') VALUES ' + ','.join([placeholders] * len(chunk)), tuple(encode(r.get(f)) for r in chunk for f in fields))
    print(f'Loaded {table}: {len(records)}')


def create_table(cursor, name, fields):
    columns = ', '.join('"' + f.upper() + '" ' + ('INTEGER' if f == 'wave' else "VARCHAR DEFAULT 'not_started'" if f == 'status' else 'VARCHAR') for f in fields)
    extra = ", UPDATED_AT TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP(), UPDATED_BY_ACT VARCHAR DEFAULT 'assess'" if name == 'MANIFEST' else ''
    cursor.execute(f"CREATE TABLE IF NOT EXISTS {SCHEMA}.{name} ({columns}{extra}) COMMENT = '{COMMENT}'")
    cursor.execute(f"ALTER TABLE {SCHEMA}.{name} SET COMMENT = '{COMMENT}'")


def view_sql():
    return {
        'V_WAVE_SUMMARY': f'SELECT WAVE, TARGET_TYPE, STATUS, COUNT(*) AS OBJECT_COUNT FROM {SCHEMA}.MANIFEST GROUP BY WAVE, TARGET_TYPE, STATUS',
        'V_LICENCE_COUNTER': f"""SELECT 'Teradata objects' AS COUNTER, COUNT(*) AS REMAINING, 0 AS TARGET FROM {SCHEMA}.MANIFEST
            WHERE SYSTEM='teradata' AND KIND IN ('table','view','macro','procedure','catalog') AND STATUS NOT IN ('done','retired')
            UNION ALL SELECT 'PowerCenter mappings', COUNT(*), 0 FROM {SCHEMA}.MANIFEST WHERE KIND='mapping' AND STATUS NOT IN ('done','retired')
            UNION ALL SELECT 'Spark executor-hours', 0, 0""",
        'V_DEAD_OBJECTS': f"""SELECT T.DATABASENAME || '.' || T.TABLENAME AS OBJECT_NAME FROM {SCHEMA}.DBQL_TABLESV T
            WHERE T.DATABASENAME LIKE 'SFX_%' AND NOT EXISTS (
              SELECT 1 FROM {SCHEMA}.DBQL_OBJECTUSAGE O JOIN {SCHEMA}.DBQL_QRYLOG Q ON Q.QUERYID=O.QUERYID
              WHERE O.OBJECTDATABASENAME=T.DATABASENAME AND O.OBJECTTABLENAME=T.TABLENAME
              AND Q.STARTTIME::TIMESTAMP_NTZ >= '2026-08-12'::TIMESTAMP_NTZ AND Q.STARTTIME::TIMESTAMP_NTZ < '2026-11-10'::TIMESTAMP_NTZ)""",
        'V_HIDDEN_CONSUMERS': f"""SELECT DISTINCT Q.USERNAME AS PRINCIPAL FROM {SCHEMA}.DBQL_QRYLOG Q
            WHERE Q.STATEMENTTYPE='SELECT' AND Q.STARTTIME::TIMESTAMP_NTZ >= '2026-08-12'::TIMESTAMP_NTZ
              AND Q.STARTTIME::TIMESTAMP_NTZ < '2026-11-10'::TIMESTAMP_NTZ
              AND NOT EXISTS (SELECT 1 FROM {SCHEMA}.CODE_PRINCIPALS C WHERE C.PRINCIPAL=Q.USERNAME)
              AND NOT EXISTS (SELECT 1 FROM {SCHEMA}.DBQL_QRYLOG B WHERE B.USERNAME=Q.USERNAME AND B.STATEMENTGROUP IN ('ETL','UTILITY','BATCH'))"""
    }


def load(cursor):
    data = yaml.safe_load((OUT / 'manifest.yaml').read_text())
    tag(cursor, 'create_schema')
    cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA} COMMENT = '{COMMENT}'")
    cursor.execute(f"ALTER SCHEMA {SCHEMA} SET COMMENT = '{COMMENT}'")
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
            cursor.execute(f'DELETE FROM {SCHEMA}.{table}')
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
    for name, sql in view_sql().items():
        tag(cursor, 'dead_objects' if name == 'V_DEAD_OBJECTS' else 'hidden_consumers' if name == 'V_HIDDEN_CONSUMERS' else 'create_schema')
        cursor.execute(f"CREATE OR REPLACE VIEW {SCHEMA}.{name} COMMENT = '{COMMENT}' AS {sql}")
    print('LOAD COMPLETE')


def verify(cursor):
    tag(cursor, 'preflight')
    exists = scalar(cursor, f"SELECT COUNT(*) FROM {DATABASE}.INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME='MIGRATION_CONTROL'")
    if not exists:
        print('FAIL | schema | SFX_D1110_AFTER.MIGRATION_CONTROL missing')
        return False
    tag(cursor, 'verify')
    data = yaml.safe_load((OUT / 'manifest.yaml').read_text())
    checks = []
    for table, key in [('MANIFEST', 'objects'), ('CONSUMERS', 'consumers')]:
        count = scalar(cursor, f'SELECT COUNT(*) FROM {SCHEMA}.{table}')
        checks.append((table, count == len(data[key]), f'{count}/{len(data[key])} rows'))
    cursor.execute(f"SELECT TABLE_NAME, COMMENT FROM {DATABASE}.INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='MIGRATION_CONTROL'")
    comments = dict(cursor.fetchall())
    schema_comment = scalar(cursor, f"SELECT COMMENT FROM {DATABASE}.INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME='MIGRATION_CONTROL'")
    checks.append(('comments', set(comments) == TABLES | VIEWS and all(v == COMMENT for v in comments.values()) and schema_comment == COMMENT, f'{len(comments)} tables/views + schema'))
    tag(cursor, 'dead_objects')
    cursor.execute(f'SELECT OBJECT_NAME FROM {SCHEMA}.V_DEAD_OBJECTS ORDER BY OBJECT_NAME')
    dead = [r[0] for r in cursor.fetchall()]
    checks.append(('dead objects', len(dead) == 6 and dead == sorted(data['dead']), str(len(dead))))
    tag(cursor, 'hidden_consumers')
    cursor.execute(f'SELECT PRINCIPAL FROM {SCHEMA}.V_HIDDEN_CONSUMERS ORDER BY PRINCIPAL')
    hidden = [r[0] for r in cursor.fetchall()]
    checks.append(('hidden consumers', hidden == sorted(r['account'] for r in data['consumers'] if r['hidden']), ', '.join(hidden)))
    print('RESULT | CHECK | ACTUAL')
    for name, passed, actual in checks:
        print(f"{'PASS' if passed else 'FAIL'} | {name} | {actual}")
    return all(passed for _, passed, _ in checks)


def report(cursor):
    tag(cursor, 'verify')
    queries = [f'SELECT WAVE, SUM(OBJECT_COUNT) AS OBJECT_COUNT FROM {SCHEMA}.V_WAVE_SUMMARY GROUP BY WAVE ORDER BY WAVE',
               f'SELECT * FROM {SCHEMA}.V_LICENCE_COUNTER ORDER BY COUNTER', f'SELECT * FROM {SCHEMA}.V_DEAD_OBJECTS ORDER BY OBJECT_NAME',
               f'SELECT * FROM {SCHEMA}.V_HIDDEN_CONSUMERS ORDER BY PRINCIPAL']
    for sql in queries:
        print(sql + ';')
        cursor.execute(sql)
        print(' | '.join(c[0] for c in cursor.description))
        for row in cursor.fetchall():
            print(' | '.join(str(v) for v in row))


def history(cursor):
    tag(cursor, 'verify')
    sql = (OUT / 'query_history_assess.sql').read_text()
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
