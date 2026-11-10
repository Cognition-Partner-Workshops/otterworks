"""Mapping-scoped capture, comparison and guarded result publication."""
import csv
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid
import zlib

from .compare import compare, status
from .harness import COMMENT, DATABASE, connection, control_table, require_owner, tag, query_tag
from .inventory import BOOTSTRAP, ESTATE, ROOT, inventory, target_relation

OUT = Path(__file__).parent / 'out'


def build(mapping=None, folder=None):
    if os.environ.get('SNOWFLAKE_DATABASE') != DATABASE:
        raise ValueError('SNOWFLAKE_DATABASE must be SFX_D1110_AFTER')
    rows = inventory()
    if mapping:
        row = next((r for r in rows if r['mapping'] == mapping), None)
        if row is None:
            raise ValueError('Unknown mapping')
        selection = row['dbt_model']
    else:
        area = (folder or '').upper().removeprefix('SFX_').removeprefix('PC_')
        if area not in ('BILLING', 'CONTENT', 'AUDIT'):
            raise ValueError('FOLDER must be BILLING, CONTENT, or AUDIT')
        selection = 'path:models/pc/' + area.lower()
    command = [sys.executable, str(ROOT / 'warehouse/snowflake/run_dbt.py'), 'build',
               '--select', selection, '--step', 'dbt']
    if mapping:
        command += ['--mapping', mapping]
    subprocess.run(command, check=True)


def identifier(value):
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', value):
        raise ValueError(f'Invalid identifier: {value}')
    return value.upper()


def relation(value):
    parts = value.split('.')
    if len(parts) == 2:
        parts.insert(0, DATABASE)
    if len(parts) != 3 or parts[0].upper() != DATABASE:
        raise ValueError('Relations must be in SFX_D1110_AFTER')
    return '.'.join(identifier(p) for p in parts)


def save(row, result):
    OUT.mkdir(exist_ok=True)
    path = OUT / (row['mapping'] + '.json')
    data = json.loads(path.read_text()) if path.exists() else {}
    data.update(result)
    data['config'] = row
    path.write_text(json.dumps(data, indent=2, default=str))


def before(row):
    import psycopg

    ns = os.environ.get('NS', 'sfx-d1110-before')
    port = os.environ.get('TD_PORT', str(55500 + zlib.crc32(ns.encode()) % 1000))
    host = os.environ.get('TD_HOST', '127.0.0.1')
    if host not in ('127.0.0.1', 'localhost'):
        raise ValueError('BEFORE resets are restricted to local fixture PostgreSQL')
    params = dict(host=host, port=port, user=os.environ.get('TD_USER', 'postgres'),
                  password=os.environ.get('TD_PASSWORD', ''), autocommit=True)
    # Like the integration fixture, use a fresh isolated database and sequence state.
    database = 'sfx_d1110_parity_' + uuid.uuid4().hex[:12]
    OUT.mkdir(exist_ok=True)
    runroot = OUT / database
    with psycopg.connect(dbname='postgres', **params) as admin:
        admin.execute(f'CREATE DATABASE {database}')
        try:
            with psycopg.connect(dbname=database, **params) as pg:
                pg.execute(BOOTSTRAP.read_text())
                env = {k: v for k, v in os.environ.items() if not k.startswith('SNOWFLAKE_')}
                env.update(TD_HOST=host, TD_PORT=str(port), TD_DB=database,
                           LANDING_DIR=str(ESTATE / 'tests/fixture/landing'), PMROOTDIR=str(runroot))
                cmd = [str(ESTATE / '.venv/bin/python'), '-m', 'runner', 'startworkflow',
                       '-f', row['folder'], row['workflow']]
                subprocess.run(cmd, cwd=ESTATE, env=env, check=True)
                # TEAM_MEMBER is deliberately disabled in the daily workflow.
                if row['mapping'] == 'm_SFX_TEAM_MEMBER':
                    subprocess.run([str(ESTATE / '.venv/bin/python'), '-m', 'runner',
                                    'startsession', '-f', row['folder'], '-w', row['workflow'],
                                    row['session']], cwd=ESTATE, env=env, check=True)
                schema, table = target_relation(row['target_table']).lower().split('.')
                cols = pg.execute('''SELECT column_name, data_type, character_maximum_length,
                    numeric_precision, numeric_scale FROM information_schema.columns
                    WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position''', (schema, table)).fetchall()
                data = pg.execute(f'SELECT * FROM {identifier(schema)}.{identifier(table)}').fetchall()
                types = []
                for name, dtype, length, precision, scale in cols:
                    if dtype in ('bigint', 'integer', 'smallint'):
                        sf = 'NUMBER(38,0)'
                    elif dtype == 'numeric':
                        sf = f'NUMBER({precision or 38},{scale or 0})'
                    elif dtype in ('character', 'character varying', 'text'):
                        sf = f'VARCHAR({length})' if length else 'VARCHAR'
                    elif dtype == 'date':
                        sf = 'DATE'
                    elif dtype.startswith('timestamp'):
                        sf = 'TIMESTAMP_TZ' if 'with time zone' in dtype else 'TIMESTAMP_NTZ'
                    elif dtype == 'boolean':
                        sf = 'BOOLEAN'
                    else:
                        raise ValueError(f'Unsupported PostgreSQL type: {dtype}')
                    types.append(identifier(name) + ' ' + sf)
                path = runroot / 'target.csv'
                path.parent.mkdir(exist_ok=True)
                with path.open('w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerows([[r'\N' if v is None else v for v in rec] for rec in data])
                with connection('load', 'before', row['mapping']) as conn, conn.cursor() as cur:
                    table = relation(row['before_table'])
                    cur.execute(f"CREATE OR REPLACE TABLE {table} ({', '.join(types)}) COMMENT='{COMMENT}'")
                    stage = DATABASE + '.PC_BEFORE.CAPTURE_STAGE'
                    cur.execute(f"CREATE STAGE IF NOT EXISTS {stage} COMMENT='{COMMENT}'")
                    cur.execute(f"PUT '{path.resolve().as_uri()}' @{stage}/{database}/ AUTO_COMPRESS=FALSE OVERWRITE=TRUE")
                    cur.execute(f"""COPY INTO {table} FROM @{stage}/{database}/ FILES=('target.csv')
                        FILE_FORMAT=(TYPE=CSV FIELD_OPTIONALLY_ENCLOSED_BY='"' NULL_IF=('\\\\N')
                        EMPTY_FIELD_AS_NULL=FALSE ESCAPE_UNENCLOSED_FIELD=NONE) FORCE=TRUE""")
                    cur.execute(f'SELECT COUNT(*) FROM {table}')
                    count = cur.fetchone()[0]
                    if count != len(data):
                        raise RuntimeError('BEFORE upload rowcount mismatch')
                save(row, dict(before_rows=count, rowcount_match=False, keyed_hash_match=False,
                               rerun_duplicates=None, parity_query_tag=None))
                print(f"BEFORE {row['mapping']}: {count} rows -> {table}")
        finally:
            admin.execute(f'DROP DATABASE {database} WITH (FORCE)')


def fetch(cur, table):
    cur.execute(f'SELECT * FROM {relation(table)}')
    columns = [c[0].upper() for c in cur.description]
    return columns, [dict(zip(columns, r)) for r in cur.fetchall()]


def parity(row, sample):
    print('Exclusions: ' + json.dumps(row['exclude_columns'], sort_keys=True))
    save(row, dict(rowcount_match=False, keyed_hash_match=False, rerun_duplicates=None,
                   parity_query_tag=query_tag('parity', 'parity_parity', tag('parity', row['mapping']))))
    with connection('parity', 'parity', row['mapping']) as conn, conn.cursor() as cur:
        after = relation(row['after_table'])
        _, schema, table = after.split('.')
        cur.execute(f'SELECT COUNT(*) FROM {DATABASE}.INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s', (schema, table))
        if not cur.fetchone()[0]:
            save(row, dict(after_rows=None, rowcount_match=False, keyed_hash_match=False,
                           parity_error='AFTER missing', rerun_duplicates=None))
            raise SystemExit(f'AFTER missing: {after}')
        bc, b = fetch(cur, row['before_table'])
        ac, a = fetch(cur, after)
        excluded = {identifier(c) for c in row['exclude_columns']}
        if excluded - set(bc):
            raise ValueError('Excluded columns absent from BEFORE')
        columns = [c for c in bc if c not in excluded]
        keys = [identifier(k) for k in row['key_columns']]
        missing = set(columns) - set(ac)
        if missing or not set(keys) <= set(columns):
            save(row, dict(rowcount_match=False, keyed_hash_match=False, rerun_duplicates=None,
                           parity_error='Missing comparison/key columns'))
            raise SystemExit(f'Missing comparison/key columns: {sorted(missing)}')
        result = compare(b, a, columns, keys, sample)
        result['parity_query_tag'] = query_tag('parity', 'parity_parity', tag('parity', row['mapping']))
        result['parity_error'] = None
        result['rerun_duplicates'] = None
        save(row, result)
        print(json.dumps(result, indent=2))
        if not result['rowcount_match'] or not result['keyed_hash_match']:
            raise SystemExit(1)


def idempotence(row):
    save(row, dict(rerun_duplicates=None, run1_rows=None, run2_rows=None))
    keys = [identifier(k) for k in row['key_columns']]
    if not keys:
        raise ValueError('Idempotence duplicate checks require YAML key_columns for STG targets')
    counts = []
    for _ in range(2):
        subprocess.run([sys.executable, str(ROOT / 'warehouse/snowflake/run_dbt.py'), 'build',
                        '--select', row['dbt_model'], '--step', 'idempotence',
                        '--mapping', row['mapping']], check=True)
        with connection('parity', 'idempotence', row['mapping']) as conn, conn.cursor() as cur:
            table = relation(row['after_table'])
            cur.execute(f'SELECT COUNT(*) FROM {table}')
            counts.append(cur.fetchone()[0])
            cur.execute(f"SELECT COALESCE(SUM(n-1),0) FROM (SELECT COUNT(*) n FROM {table} GROUP BY {', '.join(keys)} HAVING COUNT(*)>1)")
            duplicates = cur.fetchone()[0]
    result = dict(run1_rows=counts[0], run2_rows=counts[1], rerun_duplicates=int(duplicates))
    # Refresh hashes after the final build, not from a pre-build snapshot.
    parity(row, 10)
    save(row, result)
    print(json.dumps(result))


def mark_sql():
    return f'''MERGE INTO {control_table()} t USING (SELECT %s MAPPING, %s OWNER_EFFORT) s
        ON t.MAPPING=s.MAPPING
        WHEN MATCHED AND t.OWNER_EFFORT=s.OWNER_EFFORT THEN UPDATE SET
        BEFORE_ROWS=%s, AFTER_ROWS=%s, ROWCOUNT_MATCH=%s, KEYED_HASH_MATCH=%s,
        SAMPLED_DIFFS=PARSE_JSON(%s), RUN1_ROWS=%s, RUN2_ROWS=%s, RERUN_DUPLICATES=%s,
        STATUS=%s, AMBER_REASON=%s, PR_URL=COALESCE(%s,t.PR_URL), PARITY_QUERY_TAG=%s,
        VERIFIED_AT=IFF(%s='VERIFIED',CURRENT_TIMESTAMP(),NULL)'''


def mark(row, args):
    with connection('ops', 'mark', row['mapping']) as conn, conn.cursor() as cur:
        require_owner(cur, row['mapping'], args.owner)
        result = json.loads((OUT / (row['mapping'] + '.json')).read_text())
        if result.get('config') != row:
            raise ValueError('Mapping configuration changed; regenerate evidence')
        decision = status(result, args.amber)
        cur.execute(mark_sql(), (row['mapping'], args.owner, result.get('before_rows'),
                    result.get('after_rows'), result.get('rowcount_match'), result.get('keyed_hash_match'),
                    json.dumps(result.get('sampled_diffs', [])), result.get('run1_rows'),
                    result.get('run2_rows'), result.get('rerun_duplicates'), decision,
                    args.amber, args.pr_url, result.get('parity_query_tag'), decision))
        if cur.rowcount != 1:
            raise ValueError('Ownership changed; no row updated')
    print(f"{row['mapping']}: {decision}")


def dispatch(args):
    row = next((r for r in inventory() if r['mapping'] == args.mapping), None)
    if row is None:
        raise ValueError('Unknown mapping')
    if args.command == 'before':
        before(row)
    elif args.command == 'parity':
        parity(row, args.sample)
    elif args.command == 'idempotence':
        idempotence(row)
    else:
        mark(row, args)
