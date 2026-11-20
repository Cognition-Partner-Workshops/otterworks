"""Measure declared outputs without changing migration or retirement state."""
import argparse
from collections import Counter
import hashlib
import json
import os
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
sys.path.insert(0, str(ROOT / 'migration/dw-exit'))
sys.path.insert(0, str(ROOT / 'migration/dw-exit/tools'))
from warehouse.run_config import RunConfig
from assess import board as wave_board
from assess import build
from parity import pc_users, spark_users, retirement_users, report_outputs
from parity.provenance import provenance, markdown, compact_markdown
from parity.ladder import local_compare
from parity.local_sql import execute
from parity.semantics import columns as source_columns

TARGETS = ('duckdb', 'snowflake')
SNOWFLAKE_DISABLED = 'Snowflake login down; execution disabled'


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


def materialize(before, names, conversion_dir, business_date='20261109', subject='billing', after=None):
    if subject == 'users':
        return materialize_users(before, names, conversion_dir, business_date, after)
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


def materialize_users(before, names, conversion_dir, business_date='20261109', after=None):
    after = after if after is not None else duckdb.connect()
    ready, errors = set(), {}
    schema = 'USERS'
    after.execute('CREATE SCHEMA '+schema)
    for name in sorted(names):
        if not name.startswith('SFX_'+schema+'.'):
            continue
        table = name.split('.')[1]
        if table.startswith('V_'):
            continue
        target = schema+'.'+table
        # DuckDB metadata and identifiers are local; relation()/quote() escape identifiers.
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        definitions = before.execute('DESCRIBE '+relation(name)).fetchall()
        # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        rules = source_columns(name)
        after.execute(f'CREATE TABLE {relation(target)} ({", ".join(quote(c[0])+" "+c[1]+(" COLLATE NOCASE" if rules.get(c[0], {}).get("case_insensitive") else "") for c in definitions)})')
        if table.startswith('STG_'):
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            rows = before.execute('SELECT * FROM '+relation(name)).fetchall()
            if rows:
                after.executemany(f'INSERT INTO {relation(target)} VALUES ({", ".join("?" for _ in definitions)})', rows)
            ready.add(target)
    if (conversion_dir / '20_routines.sql').exists():
        errors.update(execute(after, conversion_dir, ready, business_date, 'users'))
        return after, ready, errors
    return after, ready, errors


def unavailable_cell(reason=None):
    return dict(status='red', reason=reason, row_count=None, column_profile=None,
                keyed_row_hash=None, sampled_differences=None)


def parity_counts(rows):
    return {target: {status: sum(row['targets'][target]['status'] == status for row in rows)
                     for status in ('green', 'red', 'retire_verified')
                     if status != 'retire_verified' or any(row['targets'][target]['status'] == status for row in rows)} for target in TARGETS}


def build_board(manifest, before=None, after=None, available=None, errors=None, target='duckdb', counters=None, pc_results=None):
    if target not in TARGETS:
        raise ValueError('Unsupported parity target')
    objects = manifest['objects']
    result = wave_board(objects, counters or {})
    result.update(run_token=RunConfig.from_env().token, rows=[])
    result['measurement_contract'] = {'source': 'PostgreSQL Teradata emulator snapshot',
        'local_target': 'DuckDB', 'conversions': ['billing/initial/10_load.sql','billing/initial/30_views.sql',
            'users/10_load.sql','users/20_routines.sql','users/30_views.sql'],
        'non_relational_objects': 'declared output relations', 'migration_state': 'BEFORE'}
    available, errors = set(available or ()), errors or {}
    retire_evidence = retirement_users.verify() if any(o['subject_area'] == 'users' and o['target_type'] == 'retire' for o in objects) else None
    for obj in objects:
        row = {key:obj[key] for key in ('id','name','kind','wave','owner','subject_area','licence_dependency')}
        row.update(migration_status='not_started', licence_dependency_count=int(obj['licence_dependency'] != 'none'))
        local = unavailable_cell()
        if obj['system'] == 'spark' and not any(r.startswith('SFX_SPARK.') for r in obj.get('output_relations', [])):
            if obj.get('source') and (ROOT / obj['source']).is_file():
                row.update(source=obj['source'], source_ref=obj.get('source_ref'))
                local['reason'] = 'Spark source available; output not materialized locally'
            else:
                local['reason'] = 'source on Spark baseline PR'
        elif target == 'snowflake':
            local['reason'] = 'Snowflake target selected; execution disabled'
        elif not obj.get('output_relations'):
            local['reason'] = 'no declared output relation'
        else:
            measured = {}
            for source in obj['output_relations']:
                destination = source.removeprefix('SFX_')
                if destination not in available:
                    local['reason'] = errors.get(destination, errors.get('*', 'output not materialized: '+destination))
                    break
                try:
                    measured[source] = (local_compare if obj['subject_area'] == 'users' else compare)(before, after, source, destination)
                except (duckdb.Error, ValueError) as error:
                    local['reason'] = 'measurement failed: '+str(error).splitlines()[0]
                    break
            if local['reason'] is None:
                local['row_count'] = {side:sum(r['row_count'][side] for r in measured.values()) for side in ('before','after')}
                for field in ('column_profile','keyed_row_hash','sampled_differences'):
                    local[field] = {name:values[field] for name,values in measured.items()}
                local['status'] = 'green' if all(r['passed'] for r in measured.values()) else 'red'
                if local['status'] == 'red':
                    local['reason'] = 'measured parity mismatch'
        if obj['subject_area'] == 'users':
            row['provenance'] = provenance(obj)
        mapping = obj['name'].removeprefix('s_')
        if target == 'duckdb' and obj['subject_area'] == 'users' and obj['kind'] in ('mapping','session') and pc_results is not None:
            proof = pc_results[mapping]
            local['bteq_relation_measurement'] = {k: local.get(k) for k in
                ('status','reason','row_count','column_profile','keyed_row_hash','sampled_differences','comparison_rules')}
            local.update(status=proof['status'],reason=proof['reason'],powercenter=proof,
                       measurement_basis='actual PowerCenter runner targets vs shipped dbt model on captured inputs')
            measurement = proof['measurement']
            for field in ('row_count','column_profile','keyed_row_hash','sampled_differences','comparison_rules'):
                local[field] = None if measurement is None else (measurement[field] if field == 'row_count' else
                    {'SFX_USERS.'+pc_users.MAPPINGS[mapping]:measurement[field]})
            if mapping == 'm_SFX_APP_USER':
                local.update(status='red',reason='Held on APP_USER display-name truncation decision; isolated PC/dbt proof has hash_difference=0 and does not clear the escalation' if measurement and measurement['keyed_row_hash']['difference'] == 0 else 'Held on APP_USER display-name truncation decision; see independent PC/dbt proof for current measurements')
        if target == 'duckdb' and obj['subject_area'] == 'users' and obj['target_type'] == 'retire':
            approved = (obj['name'] in retirement_users.DEAD | retirement_users.DEPENDENTS
                        and obj['name'] in manifest.get('dead' if obj['name'] in retirement_users.DEAD else 'dead_dependents', [])
                        and retire_evidence['passed'])
            local.update(status='retire_verified' if approved else 'red', retirement_evidence=retire_evidence,
                       reason=(retire_evidence['reason'] if approved else 'Retirement evidence failed or manifest declaration disagrees')+'; '+retirement_users.CAVEAT,
                       row_count=None, column_profile=None, keyed_row_hash=None, sampled_differences=None)

        row['targets'] = {'duckdb': local, 'snowflake': unavailable_cell(SNOWFLAKE_DISABLED)}
        row.update(local)
        if obj['subject_area'] == 'users':
            row.update(local_duckdb=local['status'], snowflake='red', snowflake_reason=SNOWFLAKE_DISABLED)
        result['rows'].append(row)
    rows = result['rows']
    targets = parity_counts(rows)
    areas = {area: parity_counts([r for r in rows if r['subject_area'] == area])
             for area in sorted({r['subject_area'] for r in rows})}
    total = sum(r['licence_dependency_count'] for r in rows)
    result['summary'] = dict(rows=len(rows), **targets['duckdb'], targets=targets, by_subject_area=areas,
        measured=sum(r['targets']['duckdb']['row_count'] is not None for r in rows),
        migrated=0, licence_remaining=total, licence_total=total,
        licence_by_system=dict(Counter(r['licence_dependency'] for r in rows if r['licence_dependency']!='none')))
    users = [r for r in rows if r['subject_area'] == 'users']
    result['summary']['users'] = dict(local_green=sum(r['status'] == 'green' for r in users),
        local_red=sum(r['status'] == 'red' for r in users),
        local_retire_verified=sum(r['status'] == 'retire_verified' for r in users), snowflake='red')
    return result


def render_readme(board):
    def count_row(label, counts):
        cells = [f"{counts[target]['green']} green / {counts[target]['red']} red" +
                 (f" / {counts[target]['retire_verified']} retire_verified" if counts[target].get('retire_verified') else '') for target in TARGETS]
        return '| ' + ' | '.join([label, *cells]) + ' |'

    def escape(value):
        return str(value).replace('|', r'\|')

    summary = board['summary']
    lines = ['# Migration board', '', '## Parity by subject area', '',
             'An object counts as green only when its DuckDB column is green.',
             SNOWFLAKE_DISABLED + '.', '',
             '| Subject area | DuckDB | Snowflake |', '|---|---:|---:|',
             count_row('**Total**', summary['targets'])]
    lines.extend(count_row(escape(area), counts) for area, counts in summary['by_subject_area'].items())
    lines += ['', '## Object parity', '', 'See [board.json](board.json) for reasons and measurement evidence.', '',
              '| Object | Subject area | DuckDB | Snowflake |', '|---|---|---|---|']
    for row in board['rows']:
        cells = [row['targets'][target]['status'] for target in TARGETS]
        lines.append('| ' + ' | '.join([escape(row['name']), escape(row['subject_area']), *cells]) + ' |')
    waves = list(board['waves'].values())
    lines += ['', '## Waves', '', '| Count | Wave 1 | Wave 2 | Wave 3 | Wave 4 |',
              '|---|---:|---:|---:|---:|', '| Total | ' + ' | '.join(str(w['total']) for w in waves) + ' |']
    for field in ('by_kind', 'by_target'):
        for key in sorted({k for w in waves for k in w[field]}):
            lines.append(f'| {field}: {key} | ' + ' | '.join(str(w[field].get(key, 0)) for w in waves) + ' |')
    lines += ['', '## Licence counters', '', '| Counter | Remaining | Target |', '|---|---:|---:|']
    lines.extend(f"| {k} | {v['remaining']} | {v['target']} |"
                 for k, v in board['licence_counters'].items() if 'remaining' in v)
    lines += ['', 'All objects remain not_started. Parity measurements do not migrate or retire objects.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser()
    default_output = ROOT/'migration/dw-exit/board/board.json'
    parser.add_argument('--manifest',type=Path,default=ROOT/'migration/dw-exit/manifest.yaml')
    parser.add_argument('--output',type=Path,default=default_output)
    parser.add_argument('--target',choices=TARGETS,default=os.environ.get('PARITY_TARGET','duckdb'),
                        help='Build both columns; snowflake is a legacy offline mode that skips DuckDB measurement')
    args = parser.parse_args()
    manifest = yaml.safe_load(args.manifest.read_text())
    counters = build()['counters']
    before = after = None
    ready, errors = set(), {}
    try:
        if args.target == 'duckdb' and manifest['objects']:
            names = {r for obj in manifest['objects'] for r in obj.get('output_relations',[])
                     if not r.startswith('SFX_SPARK.') and r != 'SFX_USERS.M_TEAM_COUNTS_OUTPUT'}
            ns = os.environ.get('NS',RunConfig.from_env().before_namespace)
            port = os.environ.get('TD_PG_PORT',str(54500+zlib.crc32(ns.encode())%1000))
            dsn = os.environ.get('BOARD_SOURCE_DSN',f'host=127.0.0.1 port={port} dbname=teradata user=postgres')
            before, source_ready, source_errors = source_snapshot(dsn,names)
            after, ready, errors = materialize(before,source_ready,ROOT/'migration/dw-exit/billing/initial')
            errors.update(source_errors)
            outputs = {r for obj in manifest['objects'] if obj['subject_area'] == 'users'
                       and obj['target_type'] != 'retire' for r in obj.get('output_relations', [])}
            after, users_ready, users_errors = materialize(before, source_ready & outputs,
                ROOT/'migration/dw-exit/users', os.environ.get('BUSINESS_DATE','20261109'), 'users', after)
            if '*' in users_errors:
                errors.update({r.removeprefix('SFX_'): users_errors['*'] for r in outputs})
            else:
                errors.update(users_errors)
                errors.update(report_outputs.materialize(before, after, dsn, users_ready,
                    os.environ.get('BUSINESS_DATE','20261109'), 'users'))
            ready.update(users_ready)
            users_ready, users_errors, spark_evidence = spark_users.materialize(before, after, manifest['objects'], ns)
            ready.update(users_ready)
            errors.update(users_errors)
        pc_results = pc_evidence = None
        if args.target == 'duckdb' and manifest['objects'] and (pc_users.OUT/'capture.json').exists():
            try:
                pc_results, pc_evidence = pc_users.proofs(ns, ROOT/'warehouse/landing', os.environ.get('BUSINESS_DATE','20261109'))
            except (OSError, ValueError, duckdb.Error) as error:
                pc_results = {m:dict(status='red', reason='PC evidence unavailable: '+str(error), measurement=None) for m in pc_users.MAPPINGS}
        payload = build_board(manifest,before,after,ready,errors,target=args.target,counters=counters,pc_results=pc_results)
        if pc_evidence is not None:
            payload['powercenter_evidence'] = pc_evidence
        if args.target == 'duckdb' and manifest['objects']:
            payload['spark_evidence'] = spark_evidence
        args.output.write_text(json.dumps(payload,indent=2,default=str)+'\n')
        if args.output.resolve() == default_output:
            default_output.with_name('README.md').write_text(render_readme(payload) + markdown(payload['rows'], 'users'))
            default_output.with_name('users-pr.md').write_text(markdown(payload['rows'], 'users') + compact_markdown(payload['rows']))
        print(json.dumps(payload['summary'],sort_keys=True))
    finally:
        if before is not None:
            before.close()
        if after is not None:
            after.close()


if __name__ == '__main__':
    main()
