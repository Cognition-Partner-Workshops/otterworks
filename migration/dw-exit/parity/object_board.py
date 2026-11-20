"""Measure declared outputs without changing migration or retirement state."""
import argparse
import fnmatch
import importlib.util
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys
import shutil
import subprocess
import tempfile
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
from assess import build

TARGETS = ('duckdb', 'snowflake')
SNOWFLAKE_DISABLED = 'Snowflake login down; execution disabled'
OUTPUT_PARITY = 'All declared outputs are materialized and match the emulator in DuckDB'
RETIREMENT_PROOF = (
    'Unused evidence, a no-reader check that no non-retired manifest object and no consumer in '
    'consumers/registry.yaml reads the retired output, and owner sign-off in '
    'migration/dw-exit/retirements/<id>.yaml'
)
RETIREMENT_PENDING = 'retirement green condition pending s2.1'
NO_OUTPUT_PROOF = {
    'bteq': 'Run the report with the same fixture parameters, declare and capture its result or export as a relation, and pass DuckDB output parity',
    'macro': 'Invoke the macro equivalent with the same fixture parameters, declare and capture its result as a relation, and pass DuckDB output parity',
    'spark_job': 'Declare the Spark job output, materialize its local replacement, and pass DuckDB output parity',
}


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


def source_snapshot(dsn, names, areas=None):
    connection = duckdb.connect()
    ready, errors = set(), {}
    with psycopg.connect(dsn) as source:
        with source.cursor() as cursor:
            cursor.execute("SELECT table_schema,table_name,column_name,data_type,numeric_precision,numeric_scale FROM information_schema.columns WHERE table_schema LIKE 'sfx_%' ORDER BY table_schema,table_name,ordinal_position")
            columns = {}
            for schema, table, column, dtype, precision, scale in cursor:
                columns.setdefault((schema, table), []).append((column, dtype, precision, scale))
            index = {(s+'.'+t).upper(): (s,t,cols) for (s,t),cols in columns.items()}
            names = set(names)
            for config in (areas or {}).values():
                names.update(name for name in index if any(fnmatch.fnmatchcase(
                    name, 'SFX_'+config['schema']+'.'+pattern) for pattern in config.get('seed', [])))
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


AREA_ROOT = ROOT / 'migration/dw-exit'


def registered_areas():
    return {p.parent.name: dict(yaml.safe_load(p.read_text()), directory=p.parent)
            for p in sorted(AREA_ROOT.glob('*/area.yaml'))}


def materialize(before, names, conversion_dir=None, *, areas=None, database=None):
    areas = areas if areas is not None else registered_areas()
    if conversion_dir is not None:
        areas = {'billing': dict(schema='BILLING', seed=['STG_*'], directory=conversion_dir,
                                 sql=['10_load.sql', '30_views.sql'])}
    if database is None:
        database = Path(tempfile.mkdtemp(prefix='object-board-')) / 'after.duckdb'
    after = duckdb.connect(str(database))
    ready, errors = set(), {}
    for area, config in areas.items():
        schema = exp.Create(this=exp.Table(this=exp.Identifier(this=config['schema'], quoted=True)),
                            kind='SCHEMA', exists=True)
        after.execute(schema.sql(dialect='duckdb'))
    for name in sorted(names):
        source_schema, table = name.split('.')
        config = next((c for c in areas.values() if source_schema == 'SFX_'+c['schema']), None)
        if config is None:
            continue
        if table.startswith('V_'):
            continue
        target = config['schema']+'.'+table
        # DuckDB metadata and identifiers are local; relation()/quote() escape identifiers.
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        definitions = before.execute('DESCRIBE '+relation(name)).fetchall()
        # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        after.execute(f'CREATE TABLE {relation(target)} ({", ".join(quote(c[0])+" "+c[1] for c in definitions)})')
        if any(fnmatch.fnmatchcase(table, pattern) for pattern in config.get('seed', [])):
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            rows = before.execute('SELECT * FROM '+relation(name)).fetchall()
            if rows:
                after.executemany(f'INSERT INTO {relation(target)} VALUES ({", ".join("?" for _ in definitions)})', rows)
            ready.add(target)
    artifacts = [(c['directory'] / f) for c in areas.values() for f in c.get('sql', [])]
    for path in artifacts:
        filename = path.name
        text = RunConfig.from_env().render(path.read_text())
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
    for config in areas.values():
        if config.get('dbt'):
            after.close()
            try:
                run_dbt(config, database)
                ready.update(config['schema']+'.'+m['target'] for m in config['dbt'])
            except (subprocess.CalledProcessError, ValueError) as error:
                for model in config['dbt']:
                    errors[config['schema']+'.'+model['target']] = 'dbt failed: '+str(error)
            finally:
                after = duckdb.connect(str(database))
        for job in config.get('snowpark', []):
            target = config['schema']+'.'+job['target']
            try:
                run_snowpark(config, job, after)
                ready.add(target)
            except Exception as error:
                errors[target] = 'snowpark failed: '+str(error).splitlines()[0]
    return after, ready, errors


def run_dbt(config, database):
    with tempfile.TemporaryDirectory(prefix='board-dbt-') as temporary:
        directory = Path(temporary)
        project = directory / 'project'
        shutil.copytree(config.get('dbt_project', ROOT/'warehouse/dbt'), project,
                        ignore=shutil.ignore_patterns('target', 'logs', 'dbt_packages', 'profiles.yml'))
        for model in config['dbt']:
            path = project / model['model']
            path.write_text(path.read_text() + '\n{{ config(schema='+repr(config['schema'])+
                            ', alias='+repr(model['target'])+') }}\n')
        for path in (project/'models').rglob('*.yml'):
            document = yaml.safe_load(path.read_text()) or {}
            for source in document.get('sources', []):
                source['database'] = Path(database).stem
                source['schema'] = config['schema']
                for table in source.get('tables', []):
                    table['identifier'] = config.get('sources', {}).get(
                        source['name']+'.'+table['name'], table.get('identifier', table['name']))
            path.write_text(yaml.safe_dump(document))
        profile = yaml.safe_load((project/'dbt_project.yml').read_text())['profile']
        (directory/'profiles.yml').write_text(yaml.safe_dump({profile: {'target': 'duckdb', 'outputs': {
            'duckdb': {'type': 'duckdb', 'path': str(Path(database).resolve()),
                       'schema': config['schema'], 'threads': 1}}}}))
        command = [str(Path(sys.executable).with_name('dbt')), 'run', '--project-dir', str(project),
                   '--profiles-dir', str(directory), '--no-partial-parse', '--select']
        command += ['+'+Path(m['model']).stem for m in config['dbt']]
        result = subprocess.run(command, text=True, capture_output=True,
                                env=dict(os.environ, DBT_SEND_ANONYMOUS_USAGE_STATS='false'))
        if result.returncode:
            raise ValueError(result.stdout + result.stderr)


def run_snowpark(config, job, after):
    from snowflake.snowpark import Session
    from snowflake.snowpark import types

    with Session.builder.config('local_testing', True).create() as session:
        for local, remote in job.get('inputs', {}).items():
            source = after.table(relation(config['schema']+'.'+local))
            fields = []
            for column, datatype in zip(source.columns, source.types):
                dtype = str(datatype)
                kind = {'INTEGER': types.IntegerType(), 'SMALLINT': types.ShortType(),
                        'BIGINT': types.LongType(), 'FLOAT': types.FloatType(),
                        'DOUBLE': types.DoubleType(), 'BOOLEAN': types.BooleanType(),
                        'DATE': types.DateType(), 'TIMESTAMP': types.TimestampType(),
                        'BLOB': types.BinaryType(), 'VARCHAR': types.StringType()}.get(dtype)
                if dtype.startswith('DECIMAL('):
                    precision, scale = map(int, dtype[8:-1].split(','))
                    kind = types.DecimalType(precision, scale)
                if kind is None:
                    raise ValueError('Unsupported Snowpark input type: '+dtype)
                fields.append(types.StructField(column, kind))
            rows = source.fetchall()
            session.create_dataframe(rows, schema=types.StructType(fields)).write.save_as_table(remote, mode='overwrite')
        path = ROOT / job['job']
        spec = importlib.util.spec_from_file_location('board_snowpark_job', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = module.run(session)
        if result is None:
            result = session.table(job['output'])
        frame = result.to_pandas()
        after.register('_snowpark_result', frame)
        try:
            statement = exp.Create(this=exp.Table(
                db=exp.Identifier(this=config['schema'], quoted=True),
                this=exp.Identifier(this=job['target'], quoted=True)), kind='TABLE',
                replace=True, expression=exp.select('*').from_('_snowpark_result'))
            after.execute(statement.sql(dialect='duckdb'))
        finally:
            after.unregister('_snowpark_result')


def unavailable_cell(reason=None):
    return dict(status='red', reason=reason, row_count=None, column_profile=None,
                keyed_row_hash=None, sampled_differences=None)


def parity_counts(rows):
    return {target: {status: sum(row['targets'][target]['status'] == status for row in rows)
                     for status in ('green', 'red')} for target in TARGETS}


def build_board(manifest, before=None, after=None, available=None, errors=None, target='duckdb', counters=None, areas=None):
    if target not in TARGETS:
        raise ValueError('Unsupported parity target')
    objects = manifest['objects']
    if len({obj['id'] for obj in objects}) != len(objects):
        raise ValueError('Duplicate ids in manifest objects')
    areas = registered_areas() if areas is None else areas
    schemas = {'SFX_'+c['schema']: c['schema'] for c in areas.values()}
    result = wave_board(objects, counters or {})
    result.update(run_token=RunConfig.from_env().token, rows=[],
                  consumer_gates=[{key: c[key] for key in ('id', 'name')} for c in manifest.get('consumers', [])])
    result['measurement_contract'] = {'source': 'PostgreSQL Teradata emulator snapshot',
        'local_target': 'DuckDB', 'conversions': [area+'/'+f for area,c in areas.items() for f in c.get('sql', [])],
        'areas': {area: {k:v for k,v in c.items() if k != 'directory'} for area,c in areas.items()},
        'non_relational_objects': 'per-object DuckDB green condition', 'migration_state': 'BEFORE'}
    available, errors = set(available or ()), errors or {}
    for obj in objects:
        row = {key:obj[key] for key in ('id','name','kind','wave','owner','subject_area','licence_dependency')}
        row.update(migration_status='not_started', licence_dependency_count=int(obj['licence_dependency'] != 'none'))
        local = unavailable_cell()
        retiring = obj['target_type'] == 'retire'
        local['green_condition'] = (RETIREMENT_PROOF if retiring else
                                    OUTPUT_PARITY if obj.get('output_relations') else
                                    NO_OUTPUT_PROOF.get(obj['kind'], 'Declare a representative output and pass DuckDB output parity'))
        if retiring:
            local['reason'] = RETIREMENT_PENDING
        elif target == 'snowflake':
            local['reason'] = 'Snowflake target selected; execution disabled'
        elif obj['system'] == 'spark' and not (obj['subject_area'] in areas and any(
                schemas.get(s.split('.')[0], '')+'.'+s.split('.')[1] in available
                for s in obj.get('output_relations', []))):
            if obj.get('source') and (ROOT / obj['source']).is_file():
                row.update(source=obj['source'], source_ref=obj.get('source_ref'))
                local['reason'] = 'Spark source available; output not materialized locally'
            else:
                local['reason'] = 'source on Spark baseline PR'
        elif not obj.get('output_relations'):
            local['reason'] = 'no declared output relation'
        else:
            measured = {}
            for source in obj['output_relations']:
                schema, table = source.split('.')
                destination = schemas.get(schema, schema.removeprefix('SFX_'))+'.'+table
                if destination not in available:
                    local['reason'] = errors.get(destination, errors.get('*', 'output not materialized: '+destination))
                    break
                try:
                    measured[source] = compare(before, after, source, destination)
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
        row['targets'] = {'duckdb': local, 'snowflake': unavailable_cell(SNOWFLAKE_DISABLED)}
        row.update(local)
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
    return result


def render_readme(board):
    def count_row(label, counts, rows):
        duckdb = counts['duckdb']
        snowflake = counts['snowflake']
        reasons = Counter(row['targets']['duckdb']['reason'].split(':')[0]
                          for row in rows if row['targets']['duckdb']['status'] == 'red')
        top = sorted(reasons.items(), key=lambda item: (-item[1], item[0]))
        reason_text = '; '.join(f'{reason} ({count})' for reason, count in top) or '—'
        cells = [str(duckdb['green'] + duckdb['red']), str(duckdb['green']), str(duckdb['red']),
                 f"{snowflake['green']} green / {snowflake['red']} red", escape(reason_text)]
        return '| ' + ' | '.join([label, *cells]) + ' |'

    def escape(value):
        return str(value).replace('|', r'\|')

    summary = board['summary']
    lines = ['# Migration board', '', '## Parity by subject area', '',
             'An object counts as green only when its DuckDB column is green.',
             SNOWFLAKE_DISABLED + '.', '',
             '| Subject area | Total | DuckDB green | DuckDB red | Snowflake | DuckDB red reasons (count) |',
             '|---|---:|---:|---:|---:|---|',
             count_row('**Total**', summary['targets'], board['rows'])]
    lines.extend(count_row(escape(area), counts, (r for r in board['rows'] if r['subject_area'] == area))
                 for area, counts in summary['by_subject_area'].items())
    consumers = board['consumer_gates']
    if consumers:
        lines += ['', '## Scope', '',
                  f"`manifest.yaml` contains **{summary['rows']} entries under `objects`**, each with one board row.",
                  f"A raw `- id:` count also includes {len(consumers)} entries under `consumers` "
                  f"({summary['rows'] + len(consumers)} ID lines in all). These are reader/cutover gates, not parity objects:",
                  '']
        lines.extend(f"- `{c['name']}` (`{c['id']}`)" for c in consumers)
    lines += ['', '## DuckDB green conditions', '',
              '- Declared outputs: materialize and compare every output (row count, column profiles and keyed row hashes). '
              'Sessions inherit their mapping outputs; workflows and worklets inherit the outputs of their sessions/worklets.',
              '- BTEQ reports without a declared output: run with the same fixture parameters and declare and capture '
              'the report result or export as a relation for parity.',
              '- Macros without a declared output: invoke the equivalent with the same fixture parameters and '
              'declare and capture its result as a relation for parity.',
              '- Spark jobs without a declared output: declare the job output and materialize a local replacement '
              'before measuring parity; a source file alone is not proof.',
              '- Retirement candidates (including DBC catalog replacements) stay red pending s2.1 '
              '("Define when a retired object is green"). That step requires unused evidence, a check that '
              'no non-retired manifest object and no consumer in `consumers/registry.yaml` reads the retired output, '
              'and owner sign-off in `migration/dw-exit/retirements/<id>.yaml`.',
              '', 'Each DuckDB cell records its green condition.']
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
    parser.add_argument('--area', choices=sorted(registered_areas()))
    parser.add_argument('--target',choices=TARGETS,default=os.environ.get('PARITY_TARGET','duckdb'),
                        help='Build both columns; snowflake is a legacy offline mode that skips DuckDB measurement')
    args = parser.parse_args()
    manifest = yaml.safe_load(args.manifest.read_text())
    areas = registered_areas()
    if args.area:
        areas = {args.area: areas[args.area]}
    counters = build()['counters']
    before = after = None
    ready, errors = set(), {}
    try:
        if args.target == 'duckdb' and manifest['objects']:
            names = {r for obj in manifest['objects'] for r in obj.get('output_relations',[])}
            ns = os.environ.get('NS',RunConfig.from_env().before_namespace)
            port = os.environ.get('TD_PG_PORT',str(54500+zlib.crc32(ns.encode())%1000))
            dsn = os.environ.get('BOARD_SOURCE_DSN',f'host=127.0.0.1 port={port} dbname=teradata user=postgres')
            before, source_ready, source_errors = source_snapshot(dsn,names,areas)
            after, ready, errors = materialize(before,source_ready,areas=areas)
            errors.update(source_errors)
        payload = build_board(manifest,before,after,ready,errors,target=args.target,counters=counters,areas=areas)
        args.output.write_text(json.dumps(payload,indent=2,default=str)+'\n')
        if args.output.resolve() == default_output:
            default_output.with_name('README.md').write_text(render_readme(payload))
        print(json.dumps(payload['summary'],sort_keys=True))
    finally:
        if before is not None:
            before.close()
        if after is not None:
            after.close()


if __name__ == '__main__':
    main()
