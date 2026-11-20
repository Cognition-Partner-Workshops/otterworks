"""Measure declared outputs without changing migration or retirement state."""
import argparse
import datetime as dt
import re
import time
from decimal import Decimal
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
sys.path.insert(0, str(ROOT / 'migration/dw-exit/tools'))
from warehouse.run_config import RunConfig
from assess import board as wave_board
from warehouse.snowflake import capacity

CONVERSIONS = ['billing/10_load.sql', 'billing/20_routines.sql', 'billing/15_storage.sql', 'billing/25_invoice_monthly.sql',
               'billing/40_close.sql', 'billing/30_views.sql', 'warehouse/dbt/models/spark/billing_*']
SNOWFLAKE_DOWN = 'Snowflake login unavailable; no Snowflake objects created'
CHAIN = ROOT / 'migration/dw-exit/billing/chain.yaml'


def quote(name):
    return '"' + name.replace('"', '""') + '"'


def relation(name):
    parts = name.split('.')
    if len(parts) != 2:
        raise ValueError('Expected schema.relation')
    return '.'.join(map(quote, parts))


def comparable(value):
    # DOUBLE results compare at 12 significant digits: exp()/log() differ in the last ULP across engines.
    if isinstance(value, float):
        return float(f'{value:.12g}')
    if isinstance(value, (list, tuple)):
        return [comparable(v) for v in value]
    if isinstance(value, dict):
        return {k: comparable(v) for k, v in value.items()}
    return value


def canonical(value):
    return json.dumps(comparable(value), default=str, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


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
        floats = [row[columns.index(column)] for row in rows if isinstance(row[columns.index(column)], float)]
        if floats:
            profiles[column]['distinct'] = len({comparable(value) for value in floats})
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
                    # psycopg Identifier quotes both catalog-derived identifiers.
                    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                    cursor.execute(sql.SQL('SELECT * FROM {}.{}').format(sql.Identifier(schema),sql.Identifier(table)))
                    rows = cursor.fetchall()
                    definitions = []
                    for position, (column, dtype, precision, scale) in enumerate(cols):
                        if dtype == 'numeric' and precision is None:
                            # Unconstrained NUMERIC (e.g. a view's SUM) keeps the scale its values carry.
                            scale = max((-row[position].as_tuple().exponent for row in rows if isinstance(row[position], Decimal)), default=0)
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
                    if rows:
                        connection.executemany(f'INSERT INTO {relation(name)} VALUES ({", ".join("?" for _ in cols)})', rows)
                    ready.add(name)
                except (duckdb.Error, psycopg.Error, ValueError) as error:
                    errors[name] = 'source snapshot: '+type(error).__name__
                    source.rollback()
    return connection, ready, errors


FORMATS = (('YYYY', '%Y'), ('MM', '%m'), ('DD', '%d'))
PROCEDURE = re.compile(r'CREATE\s+OR\s+REPLACE\s+PROCEDURE\s+([\w.]+)\s*\((.*?)\)\s*RETURNS.*?\$\$(.*?)\$\$\s*;', re.S | re.I)
CALL = re.compile(r'^\s*CALL\s+([\w.]+)\s*\((.*?)\)\s*;?\s*$', re.M | re.I | re.S)


def strftime_format(text):
    for snowflake, duck in FORMATS:
        text = text.replace(snowflake, duck)
    return text


def to_duckdb(statement):
    """Transpile one Snowflake statement for the local target, keeping format-sensitive date calls."""
    for table in statement.find_all(exp.Table):
        table.set('catalog', None)
    def fix(node):
        if isinstance(node, exp.ToChar) and node.args.get('format') is not None:
            return exp.Anonymous(this='STRFTIME', expressions=[node.this, exp.Literal.string(strftime_format(node.args['format'].name))])
        if isinstance(node, exp.Anonymous) and node.name.upper() == 'TO_DATE' and len(node.expressions) == 2:
            value, fmt = node.expressions
            return exp.cast(exp.Anonymous(this='STRPTIME', expressions=[value, exp.Literal.string(strftime_format(fmt.name))]), 'DATE')
        return node
    return statement.transform(fix).sql(dialect='duckdb', comments=False)


def table_name(table):
    return (table.db + '.' + table.name).upper()


def literal(value):
    if value is None:
        return 'NULL'
    if isinstance(value, dt.date):
        return f"DATE '{value.isoformat()}'"
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    return str(value)


class Chain:
    """Execute converted Snowflake SQL and Snowflake Scripting routines against DuckDB."""

    def __init__(self, connection, ready, errors, variables=None):
        self.db, self.ready, self.errors = connection, ready, errors
        self.variables, self.procedures, self.seconds = variables or {}, {}, Counter()

    def render(self, text):
        text = RunConfig.from_env().render(text)
        for name, value in self.variables.items():
            text = text.replace('${' + name + '}', value)
        return text

    def execute(self, statement):
        if isinstance(statement, exp.Create):
            if not isinstance(statement.expression, exp.Query):
                return None
            target = table_name(statement.this)
            references = {table_name(t) for t in statement.expression.find_all(exp.Table)}
            statement.set('properties', None)
        elif isinstance(statement, exp.Insert):
            target = table_name(statement.this.find(exp.Table))
            references = {table_name(t) for t in statement.expression.find_all(exp.Table)}
            references.discard(target)
        elif isinstance(statement, (exp.Delete, exp.Update, exp.Merge)):
            target = table_name(statement.this.find(exp.Table) if not isinstance(statement.this, exp.Table) else statement.this)
            references = {table_name(t) for t in statement.find_all(exp.Table)} if not isinstance(statement, exp.Delete) else {target} & self.ready
        else:
            return None
        if not references <= self.ready:
            self.errors[target] = 'conversion input not materialized'
            return None
        start = time.perf_counter()
        try:
            # Converted repository SQL executes in a private in-memory DuckDB target.
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            cursor = self.db.execute(to_duckdb(statement))
            count = cursor.fetchone()[0] if cursor.description and not isinstance(statement, exp.Create) else None
        except duckdb.Error as error:
            self.ready.discard(target)
            self.errors[target] = 'conversion failed: ' + str(error).splitlines()[0]
            return None
        finally:
            self.seconds[target] += time.perf_counter() - start
        if isinstance(statement, (exp.Create, exp.Insert)):
            self.ready.add(target)
        return count

    def run_sql(self, text):
        count = None
        for statement in sqlglot.parse(text, read='snowflake'):
            if statement is not None:
                count = self.execute(statement)
        return count

    def run_text(self, text, label):
        text = self.render(text)
        for name, params, body in PROCEDURE.findall(text):
            names = [p.split()[0].upper() for p in params.split(',') if p.strip()]
            self.procedures[table_name(sqlglot.exp.to_table(name))] = (names, body)
        text = PROCEDURE.sub('', text)
        position = 0
        try:
            for call in CALL.finditer(text):
                self.run_sql(text[position:call.start()])
                self.call(call.group(1), call.group(2))
                position = call.end()
            self.run_sql(text[position:])
        except sqlglot.errors.ParseError:
            self.errors['*'] = 'conversion parse failed: ' + label

    def query(self, text):
        statement = sqlglot.parse_one(text, read='snowflake')
        if not {table_name(t) for t in statement.find_all(exp.Table)} <= self.ready:
            raise ValueError('result set input not materialized')
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        cursor = self.db.execute(to_duckdb(statement))
        return [c[0] for c in cursor.description], cursor.fetchall()

    def scalar(self, text):
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        return self.db.execute(to_duckdb(sqlglot.parse_one('SELECT ' + text, read='snowflake'))).fetchone()[0]

    def call(self, name, arguments):
        name, arguments = table_name(sqlglot.exp.to_table(self.render(name))), self.render(arguments)
        if name not in self.procedures:
            raise ValueError('procedure not converted: ' + name)
        params, body = self.procedures[name]
        values = [self.scalar(a.sql(dialect='snowflake')) for a in sqlglot.parse_one('SELECT ' + arguments, read='snowflake').expressions] if arguments.strip() else []
        scope, results, count = dict(zip(params, values)), {}, None
        def bind(text):
            for variable, value in scope.items():
                text = re.sub(r':' + variable + r'\b', lambda _: literal(value), text, flags=re.I)
                if variable in params:
                    text = re.sub(r'(?<![\w.:])' + variable + r'\b', lambda _: literal(value), text, flags=re.I)
            return text
        body = re.sub(r'^\s*(DECLARE\b.*?)?\bBEGIN\b', '', body, count=1, flags=re.S | re.I)
        body = re.sub(r'\bEND\s*;\s*$', '', body.strip(), flags=re.I)
        for statement in (s.strip() for s in body.split(';')):
            assign = re.fullmatch(r'(\w+)\s*:=\s*(.*)', statement, re.S)
            let = re.fullmatch(r'LET\s+(\w+)\s+RESULTSET\s*:=\s*(.*)', statement, re.S | re.I)
            returned = re.fullmatch(r'RETURN\s+(?:TABLE\s*\((\w+)\)|(\w+))', statement, re.I)
            if not statement:
                continue
            if let:
                results[let.group(1).upper()] = bind(let.group(2))
            elif assign:
                scope[assign.group(1).upper()] = count if assign.group(2).strip().upper() == 'SQLROWCOUNT' else self.scalar(bind(assign.group(2)))
            elif returned:
                return self.query(results[returned.group(1).upper()]) if returned.group(1) else scope.get(returned.group(2).upper())
            else:
                count = self.run_sql(bind(statement))
        return None


def prepare(before, names, inputs=None):
    after = duckdb.connect()
    ready, errors = set(), {}
    after.execute('CREATE SCHEMA BILLING')
    copies = {'BILLING.' + n.split('.')[1]: n for n in names if n.startswith('SFX_BILLING.') and not n.split('.')[1].startswith('V_')}
    for target, name in sorted({**copies, **(inputs or {})}.items()):
        if name not in names:
            errors[target] = 'source output unavailable: ' + name
            continue
        # DuckDB metadata and identifiers are local; relation()/quote() escape identifiers.
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        definitions = before.execute('DESCRIBE '+relation(name)).fetchall()
        # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        after.execute(f'CREATE TABLE {relation(target)} ({", ".join(quote(c[0])+" "+c[1] for c in definitions)})')
        if target.split('.')[1].startswith('STG_') or target in (inputs or {}):
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            rows = before.execute('SELECT * FROM '+relation(name)).fetchall()
            if rows:
                after.executemany(f'INSERT INTO {relation(target)} VALUES ({", ".join("?" for _ in definitions)})', rows)
            ready.add(target)
    return after, ready, errors


def materialize(before, names, conversion_dir, files=('10_load.sql', '30_views.sql')):
    after, ready, errors = prepare(before, names)
    chain = Chain(after, ready, errors)
    for filename in files:
        chain.run_text((conversion_dir / filename).read_text(), filename)
    return after, ready, errors


def chain_variables(business_date):
    day = dt.datetime.strptime(business_date, '%Y%m%d').date()
    first = day.replace(day=1)
    following = (first + dt.timedelta(days=32)).replace(day=1)
    return {'BUSINESS_DATE': business_date, 'MONTH_START': first.strftime('%Y%m%d'), 'MONTH_END': following.strftime('%Y%m%d')}


def export_text(value, folded=False):
    if value is None or value == '':
        return None
    text = value.isoformat() if isinstance(value, dt.date) else str(value)
    text = text.rstrip()
    if re.fullmatch(r'-?\d+(\.\d+)?', text):
        text = format(Decimal(text).normalize(), 'f')
    return text.upper() if folded else text


def store_export(connection, name, columns, rows, folded=()):
    connection.execute('CREATE SCHEMA IF NOT EXISTS EXPORT')
    target = relation('EXPORT.' + name)
    # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
    connection.execute(f'CREATE OR REPLACE TABLE {target} ({", ".join(quote(c)+" VARCHAR" for c in columns)})')
    values = [[export_text(v, c in folded) for c, v in zip(columns, row)] for row in rows]
    if values:
        connection.executemany(f'INSERT INTO {target} VALUES ({", ".join("?" for _ in columns)})', values)


def replay(before, names, conversion_dir, config, exports_dir):
    """Run the configured billing chain; capture each export beside its Teradata .psv file."""
    after, ready, errors = prepare(before, names, config.get('inputs'))
    chain = Chain(after, ready, errors, chain_variables(config['business_date']))
    timings = []
    for step in config['steps']:
        chain.seconds.clear()
        start = time.perf_counter()
        for filename in step.get('sql', []):
            chain.run_text((conversion_dir / filename).read_text(), filename)
        for name, text in step.get('exports', {}).items():
            folded = config.get('case_folded', {}).get(name, ())
            try:
                rendered = chain.render(text)
                call = CALL.fullmatch(rendered.strip())
                columns, rows = chain.call(call.group(1), call.group(2)) if call else chain.query(rendered)
                lines = (exports_dir / (name + '.psv')).read_text().splitlines()
                source = [line.split('|') for line in lines if line]
                if any(len(row) != len(columns) for row in source):
                    raise ValueError('export column count differs')
                store_export(after, name, columns, rows, folded)
                store_export(before, name, columns, source, folded)
                ready.add('EXPORT.' + name)
            except (duckdb.Error, ValueError, OSError, KeyError, sqlglot.errors.ParseError) as error:
                errors['EXPORT.' + name] = 'result set failed: ' + str(error).splitlines()[0]
        elapsed = time.perf_counter() - start
        split = Counter()
        for target, workload in step.get('workload_by_target', {}).items():
            split[workload] += chain.seconds.get(target, 0.0)
        split[step['workload']] += elapsed - sum(split.values())
        for workload, seconds in split.items():
            timings.append({'step': step['name'], 'scripts': step.get('scripts', []), 'workload': workload, 'seconds': round(seconds, 6)})
    return after, ready, errors, timings


SPARK_MODELS = ROOT / 'warehouse/dbt/models/spark'
DUCK_TYPES = {'BIGINT': 'BIGINT', 'TEXT': 'VARCHAR', 'DATE': 'DATE', 'TIMESTAMP': 'TIMESTAMP'}


def render_model(text):
    """Render a Spark replacement dbt model for DuckDB as its steady-state (incremental) daily run."""
    text = re.sub(r'\{\{\s*config\(.*?\)\s*\}\}', '', text, flags=re.S)
    text = re.sub(r'\{%\s*if\s+is_incremental\(\)\s*%\}(.*?)\{%\s*endif\s*%\}', r'\1', text, flags=re.S)
    text = re.sub(r"\{\{\s*source\('spark_billing',\s*'(\w+)'\)\s*\}\}", r'SPARK_RAW_BILLING.\1', text)
    return '\n'.join(line for line in text.splitlines() if not line.strip().startswith('--'))


def upper_columns(connection, name, query):
    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
    columns = [c[0] for c in connection.execute(f'SELECT * FROM ({query}) LIMIT 0').description]
    # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
    connection.execute(f'CREATE OR REPLACE TABLE {relation(name)} AS SELECT {", ".join(quote(c)+" AS "+quote(c.upper()) for c in columns)} FROM ({query})')


def spark_outputs(before, after, ready, errors, lake, landing):
    """Spark lake outputs (before) against their dbt replacement models run in DuckDB (after)."""
    sys.path.insert(0, str(ROOT / 'etl/spark/jobs/py'))
    from common.schemas import SCHEMAS, TABLES
    sets, timings = {}, []
    for connection in (before, after):
        connection.execute('CREATE SCHEMA IF NOT EXISTS SPARK')
    if (landing / 'billing').is_dir():
        after.execute('CREATE SCHEMA IF NOT EXISTS SPARK_RAW_BILLING')
        for table in TABLES['billing']:
            columns = {n: DUCK_TYPES.get(k, k) for n, k in SCHEMAS[table]}
            path = str(landing / 'billing' / table / '*.psv')
            after.execute(f'CREATE TABLE SPARK_RAW_BILLING.{quote(table)} AS SELECT * FROM read_csv(?, header=true, delim=?, quote=?, columns=?)',
                          [path, '|', '"', columns])
    for model in sorted(SPARK_MODELS.glob('billing_*/billing_*.sql')):
        job, name = model.stem, 'SPARK.' + model.stem
        sets[job] = [name]
        output = lake / 'billing' / job
        if not output.is_dir() or not (landing / 'billing').is_dir():
            errors[name] = 'Spark output not materialized locally; run migration/dw-exit/parity/spark_local.py'
            continue
        try:
            upper_columns(before, name, f"SELECT * FROM read_parquet('{(output / '*.parquet').as_posix()}')")
            start = time.perf_counter()
            upper_columns(after, name, to_duckdb(sqlglot.parse_one(render_model(model.read_text()), read='snowflake')))
            timings.append({'step': 'dbt ' + job, 'scripts': [job], 'workload': 'transform', 'seconds': round(time.perf_counter() - start, 6)})
            ready.add(name)
        except (duckdb.Error, sqlglot.errors.ParseError) as error:
            errors[name] = 'conversion failed: ' + str(error).splitlines()[0]
    return sets, timings


def render_html(payload):
    """Billing parity board: the four ladder rungs in order, then the DuckDB and Snowflake target columns."""
    from html import escape
    def rung(row, field):
        value = row.get(field)
        if value is None:
            return '<td class="na">n/a</td>'
        if field == 'row_count':
            ok, text = value['before'] == value['after'], f"{value['before']:,} / {value['after']:,}"
        elif field == 'column_profile':
            ok = all(canonical(v['before']) == canonical(v['after']) for v in value.values())
            text = 'match' if ok else 'differs'
        elif field == 'keyed_row_hash':
            gap = sum(v['difference'] for v in value.values())
            ok, text = gap == 0, f'{gap} rows differ'
        else:
            gap = sum(len(v) for v in value.values())
            ok, text = gap == 0, 'none' if gap == 0 else f'{gap} sampled keys'
        return f'<td class="{"green" if ok else "red"}">{escape(text)}</td>'
    rows = [r for r in payload['rows'] if r['subject_area'] == 'billing']
    body = ''.join(
        f'<tr><td>{escape(r["name"])}</td><td>{escape(r["kind"])}</td>'
        + ''.join(rung(r, f) for f in ('row_count', 'column_profile', 'keyed_row_hash', 'sampled_differences'))
        + f'<td class="{r["targets"]["duckdb"]}" title="{escape(r["reason"] or "")}">{r["targets"]["duckdb"]}</td>'
        + f'<td class="red" title="{escape(r["snowflake_reason"])}">red</td><td>{escape(r["reason"] or "")}</td></tr>'
        for r in rows)
    estimate = payload.get('capacity_estimate') or {'workloads': [], 'credits_per_run': 0, 'credits_per_month': 0}
    costs = ''.join(f'<tr><td>{escape(w["workload"])}</td><td>{escape(w["warehouse"])}</td><td>{escape(w["size"])}</td>'
                    f'<td>{w["duckdb_seconds"]:.3f}</td><td>{w["billed_seconds"]:.0f}</td><td>{w["credits_per_run"]:.4f}</td>'
                    f'<td>{w["credits_per_month"]:.2f}</td></tr>' for w in estimate['workloads'])
    green = sum(r['status'] == 'green' for r in rows)
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Billing parity board {escape(payload['run_token'])}</title>
<style>body{{font-family:sans-serif;margin:24px}}table{{border-collapse:collapse;margin-bottom:24px}}td,th{{border:1px solid #ccc;padding:4px 8px;font-size:13px}}
.green{{background:#d4f7d4}}.red{{background:#f9d0d0}}.na{{color:#888}}</style></head><body>
<h1>Billing parity board &middot; {escape(payload['run_token'])}</h1>
<p>{green} of {len(rows)} billing objects green on DuckDB. Snowflake: {escape(SNOWFLAKE_DOWN)}.</p>
<table><thead><tr><th>Object</th><th>Kind</th><th>1. Row counts (before / after)</th><th>2. Column profiles</th><th>3. Keyed row hashes</th>
<th>4. Sampled differences</th><th>DuckDB</th><th>Snowflake</th><th>Reason</th></tr></thead><tbody>{body}</tbody></table>
<h2>X-Small cost estimate from DuckDB run times</h2><p>{escape(estimate.get('basis', ''))}. Credits per run {estimate['credits_per_run']:.4f}; per month {estimate['credits_per_month']:.2f}.</p>
<table><thead><tr><th>Workload</th><th>Warehouse</th><th>Size</th><th>DuckDB s</th><th>Billed s</th><th>Credits / run</th><th>Credits / month</th></tr></thead>
<tbody>{costs}</tbody></table></body></html>
"""


def build_board(manifest, before=None, after=None, available=None, errors=None, target='duckdb', counters=None,
                result_sets=None, timings=None):
    if target not in ('duckdb', 'snowflake'):
        raise ValueError('Unsupported parity target')
    objects = manifest['objects']
    result = wave_board(objects, counters or {})
    result.update(run_token=RunConfig.from_env().token, target=target, rows=[])
    result['measurement_contract'] = {'source': 'PostgreSQL Teradata emulator snapshot',
        'local_target': 'DuckDB', 'conversions': CONVERSIONS,
        'non_relational_objects': 'declared output relations plus billing/chain.yaml result sets (BTEQ exports, Spark lake outputs)',
        'ladder': ['row_count', 'column_profile', 'keyed_row_hash', 'sampled_differences'],
        'snowflake': SNOWFLAKE_DOWN, 'migration_state': 'BEFORE'}
    available, errors = set(available or ()), errors or {}
    parity_seconds = 0.0
    for obj in objects:
        row = {key:obj[key] for key in ('id','name','kind','wave','owner','subject_area','licence_dependency')}
        row.update(status='red', migration_status='not_started', licence_dependency_count=int(obj['licence_dependency'] != 'none'),
                   row_count=None, column_profile=None, keyed_row_hash=None, sampled_differences=None, reason=None)
        pairs = [] if obj['system'] == 'spark' else [(s, s.removeprefix('SFX_')) for s in obj.get('output_relations') or []]
        pairs += [(s, s) for s in (result_sets or {}).get(obj['name'], [])]
        if obj['system'] == 'spark':
            if obj.get('source') and (ROOT / obj['source']).is_file():
                row.update(source=obj['source'], source_ref=obj.get('source_ref'))
                row['reason'] = 'Spark source available; output not materialized locally'
            else:
                row['reason'] = 'source on Spark baseline PR'
        if target == 'snowflake':
            row['reason'] = 'Snowflake target selected; execution disabled'
        elif not pairs:
            row['reason'] = row['reason'] or 'no declared output relation'
        elif obj['system'] != 'spark' or row.get('source'):
            measured, row['reason'], start = {}, None, time.perf_counter()
            for source, destination in pairs:
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
            if obj['subject_area'] == 'billing':
                parity_seconds += time.perf_counter() - start
        row['targets'] = {'duckdb': row['status'] if target == 'duckdb' else 'red', 'snowflake': 'red'}
        row['snowflake_reason'] = SNOWFLAKE_DOWN
        result['rows'].append(row)
    total = sum(r['licence_dependency_count'] for r in result['rows'])
    result['summary'] = dict(rows=len(objects), red=sum(r['status']=='red' for r in result['rows']),
        green=sum(r['status']=='green' for r in result['rows']), measured=sum(r['row_count'] is not None for r in result['rows']),
        migrated=0, licence_remaining=total, licence_total=total,
        licence_by_system=dict(Counter(r['licence_dependency'] for r in result['rows'] if r['licence_dependency']!='none')))
    if timings is not None:
        result['timings'] = timings + [{'step': 'parity ladder', 'scripts': [], 'workload': 'parity', 'seconds': round(parity_seconds, 6)}]
        result['capacity_estimate'] = capacity.estimate(result['timings'])
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest',type=Path,default=ROOT/'migration/dw-exit/manifest.yaml')
    parser.add_argument('--output',type=Path,default=ROOT/'migration/dw-exit/board/board.json')
    parser.add_argument('--target',choices=['duckdb','snowflake'],default=os.environ.get('PARITY_TARGET','duckdb'))
    parser.add_argument('--exports',type=Path,default=ROOT/'warehouse/exports')
    parser.add_argument('--spark-lake',type=Path,default=ROOT/'migration/dw-exit/.runs/spark/lake')
    parser.add_argument('--spark-landing',type=Path,default=ROOT/'migration/dw-exit/.runs/spark/landing')
    args = parser.parse_args()
    manifest = yaml.safe_load(args.manifest.read_text())
    from assess import build
    counters = build()['counters']
    before = after = None
    ready, errors, result_sets, timings = set(), {}, None, None
    try:
        if args.target == 'duckdb' and manifest['objects']:
            names = {r for obj in manifest['objects'] for r in obj.get('output_relations',[])}
            ns = os.environ.get('NS',RunConfig.from_env().before_namespace)
            port = os.environ.get('TD_PG_PORT',str(54500+zlib.crc32(ns.encode())%1000))
            dsn = os.environ.get('BOARD_SOURCE_DSN',f'host=127.0.0.1 port={port} dbname=teradata user=postgres')
            chain = yaml.safe_load(CHAIN.read_text())
            names |= set(chain.get('inputs', {}).values())
            before, source_ready, source_errors = source_snapshot(dsn,names)
            after, ready, errors, timings = replay(before,source_ready,ROOT/'migration/dw-exit/billing',chain,args.exports)
            result_sets = {name:['EXPORT.'+e for e in exports] for name,exports in chain['result_sets'].items()}
            spark_sets, spark_timings = spark_outputs(before, after, ready, errors, args.spark_lake, args.spark_landing)
            result_sets.update(spark_sets)
            timings += spark_timings
            for name, error in source_errors.items():
                errors.setdefault(name.removeprefix('SFX_'), error)
        payload = build_board(manifest,before,after,ready,errors,target=args.target,counters=counters,
                              result_sets=result_sets,timings=timings)
        args.output.with_name('billing.html').write_text(render_html(payload))
        args.output.write_text(json.dumps(payload,indent=2,default=str)+'\n')
        print(json.dumps(payload['summary'],sort_keys=True))
    finally:
        if before is not None:
            before.close()
        if after is not None:
            after.close()


if __name__ == '__main__':
    main()
