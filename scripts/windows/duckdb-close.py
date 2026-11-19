"""Local execution adapter for the unchanged billing conversions and dbt SELECTs."""
import argparse
import csv
import datetime as dt
from decimal import Decimal
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import sys

import duckdb
from jinja2 import Environment, StrictUndefined
import psycopg
import pyarrow as pa
import sqlglot
from sqlglot import exp
from sqlglot.dialects.snowflake import Snowflake
from sqlglot.time import format_time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'warehouse/teradata'))
from bteq import Runner
from bteq.parser import commands
from warehouse.parity.inventory import inventory

SPEC = importlib.util.spec_from_file_location('local_object_board',
    ROOT / 'migration/dw-exit/parity/object_board.py')
BOARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BOARD)
BILLING = ROOT / 'migration/dw-exit/billing'
MODELS = ROOT / 'warehouse/dbt/models/pc/billing'
ERRORS = (duckdb.Error, sqlglot.errors.SqlglotError, ValueError)


def copy_rows(con, name, rows):
    if not rows:
        return
    data = pa.table({f'c{i}': pa.array(values) for i, values in enumerate(zip(*rows))})
    con.register('__windows_input_rows', data)
    try:
        con.execute('INSERT INTO ' + BOARD.relation(name) + ' SELECT * FROM __windows_input_rows')
    finally:
        con.unregister('__windows_input_rows')


def translated(text, day):
    trees = sqlglot.parse(text.replace('${BUSINESS_DATE}', day.strftime('%Y%m%d')),
                         read='snowflake')
    for tree in trees:
        if tree is None:
            continue
        for table in tree.find_all(exp.Table):
            table.set('catalog', None)
        for function in list(tree.find_all(exp.Anonymous)):
            if function.name.upper() == 'TO_DATE' and len(function.expressions) == 2:
                value, pattern = function.expressions
                if isinstance(pattern, exp.Literal) and pattern.is_string:
                    pattern = format_time(pattern.this, Snowflake.TIME_MAPPING, Snowflake.TIME_TRIE)
                    function.replace(exp.Cast(
                        this=exp.StrToTime(this=value.copy(), format=exp.Literal.string(pattern)),
                        to=exp.DataType.build('DATE')))
        for placeholder in list(tree.find_all(exp.Placeholder)):
            if placeholder.name == 'run_day':
                placeholder.replace(exp.Cast(this=exp.Literal.string(day.isoformat()),
                                             to=exp.DataType.build('DATE')))
        yield tree.sql(dialect='duckdb', comments=False, unsupported_level=sqlglot.ErrorLevel.RAISE)


def execute(con, text, day, errors, label):
    try:
        statements = list(translated(text, day))
    except ERRORS as error:
        errors.append({'step': label, 'error': str(error)})
        return
    for statement in statements:
        try:
            con.execute(statement)
        except duckdb.Error as error:
            errors.append({'step': label, 'sql': statement, 'error': str(error)})


def count(con, name):
    try:
        return con.execute('SELECT COUNT(*) FROM ' + BOARD.relation(name)).fetchone()[0]
    except duckdb.Error:
        return None


def result(before, after, name, source, target):
    output = dict(name=name, before_count=count(before, source),
                  after_count=count(after, target), hash_match=None, passed=False)
    try:
        measured = BOARD.compare(before, after, source, target)
        output.update(measured=measured, hash_match=measured['keyed_row_hash']['difference'] == 0,
                      passed=measured['passed'])
    except ERRORS as error:
        output['error'] = str(error)
    return output


def print_results(label, results):
    for row in results:
        value = lambda v: 'N/A' if v is None else str(v)
        print(f"{label} {row['name']} | {value(row['before_count'])} | "
              f"{value(row['after_count'])} | hash_match={value(row['hash_match'])} | "
              f"{'GREEN' if row['passed'] else 'RED'}", flush=True)
        if row.get('error'):
            print('  ' + row['error'].splitlines()[0], flush=True)


def rows_table(con, name, headers, rows):
    kinds = []
    for index in range(len(headers)):
        values = [r[index] for r in rows if r[index] is not None]
        sample = values[0] if values else None
        if isinstance(sample, Decimal):
            scale = max(max(0, -v.as_tuple().exponent) for v in values)
            kind = f'DECIMAL(38,{scale})'
        elif isinstance(sample, dt.datetime):
            kind = 'TIMESTAMP'
        elif isinstance(sample, dt.date):
            kind = 'DATE'
        elif isinstance(sample, int):
            kind = 'BIGINT'
        else:
            kind = 'VARCHAR'
        kinds.append(kind)
    columns = ', '.join(BOARD.quote(n.upper()) + ' ' + k for n, k in zip(headers, kinds))
    con.execute('CREATE OR REPLACE TABLE ' + BOARD.relation(name) + ' (' + columns + ')')
    if rows:
        copy_rows(con, name, rows)


def bteq(dsn, day):
    names = {f'SFX_BILLING.{t}' for t in (
        'CUSTOMER_ACCOUNT', 'PLAN_CATALOG', 'SUBSCRIPTION', 'INVOICE_HDR', 'INVOICE_LINE',
        'PAYMENT', 'CREDIT_NOTE', 'TAX_RATE', 'USAGE_DAILY', 'BILLING_ADJ', 'GL_ACCOUNT',
        'GL_JOURNAL_LINE', 'V_ACCOUNT_INVOICES', 'V_SUBSCRIPTION_PLANS', 'V_INVOICE_BASE',
        'V_INVOICE_REVENUE')}
    names |= {'SFX_BILLING.STG_' + n.split('.')[1] for n in names if '.V_' not in n}
    names.add('SFX_DOCUMENTS.STORAGE_USAGE_DAILY')
    before, ready, source_errors = BOARD.source_snapshot(dsn, names, copy_rows=copy_rows)
    after, available, conversion_errors = BOARD.materialize(before, ready, BILLING, copy_rows=copy_rows)
    errors = [{'step': n, 'error': e} for n, e in {**source_errors, **conversion_errors}.items()]
    definitions = before.execute('DESCRIBE SFX_DOCUMENTS.STORAGE_USAGE_DAILY').fetchall()
    after.execute('CREATE TABLE BILLING.STORAGE_USAGE_INPUT (' + ','.join(
        BOARD.quote(c[0]) + ' ' + c[1] for c in definitions) + ')')
    storage = before.execute('SELECT * FROM SFX_DOCUMENTS.STORAGE_USAGE_DAILY').fetchall()
    if storage:
        copy_rows(after, 'BILLING.STORAGE_USAGE_INPUT', storage)
    execute(after, (BILLING / '15_storage.sql').read_text(), day, errors, '15_storage.sql')
    routines = (BILLING / '20_routines.sql').read_text()
    monthly = routines.split('run_day :=', 1)[1].split(';', 1)[1].split('RETURN n;', 1)[0]
    monthly = re.sub(r'\bn\s*:=\s*SQLROWCOUNT;', '', monthly)
    execute(after, monthly, day, errors, 'P_MONTHLY_INVOICE')
    execute(after, (BILLING / '40_close.sql').read_text(), day, errors, '40_close.sql')
    with Runner(connection=psycopg.connect(dsn), output=io.StringIO()) as td:
        for name in ('M_SUBSCRIPTION_PLANS', 'M_CURRENCY_TOTALS'):
            td.execute(f"EXEC SFX_BILLING.{name}('{day:%Y%m%d}')")
            if td.errorcode:
                errors.append({'step': name, 'error': 'Legacy macro execution failed'})
                continue
            rows_table(before, 'SFX_BILLING.' + name, td.headers, td.rows)
            routine = routines.split('BILLING.' + name + ' ', 1)[1].split('$$;', 1)[0]
            query = re.search(r'LET res RESULTSET :=\s*\((.*?)\);', routine, re.S).group(1)
            execute(after, 'CREATE TABLE BILLING.' + name + ' AS ' + query,
                    day, errors, name)
        end = day.replace(day=1) - dt.timedelta(days=1)
        encode = lambda d: (d.year - 1900) * 10000 + d.month * 100 + d.day
        source = (ROOT / 'warehouse/teradata/scripts/billing/13_period_close.bteq').read_text()
        for key, val in {'BUSINESS_DATE': day.strftime('%Y%m%d'),
                         'PERIOD_START_INT': encode(end.replace(day=1)),
                         'PERIOD_END_INT': encode(end)}.items():
            source = source.replace('${' + key + '}', str(val))
        queries = [s for s in commands(source) if s.startswith('SELECT')]
        for name, query in zip(('INVOICE_PERIODS', 'PERIOD_CLOSE'), queries):
            td.execute(query)
            if td.errorcode:
                errors.append({'step': name, 'error': 'Legacy report execution failed'})
                continue
            rows_table(before, 'SFX_BILLING.' + name, td.headers, td.rows)
    # Read the checked-in converted export SELECTs without importing their Snowflake runner.
    reports = (BILLING / 'reports.py').read_text()
    for name, query in re.findall(r"'(INVOICE_PERIODS|PERIOD_CLOSE)': _run_render\(\"(.*?)\"\)", reports):
        query = query.replace('?', "'" + day.strftime('%Y%m%d') + "'")
        execute(after, 'CREATE TABLE BILLING.' + name + ' AS ' + query, day, errors, name)
    outputs = sorted(n for n in names if n.startswith('SFX_BILLING.') and '.STG_' not in n)
    outputs += ['SFX_BILLING.' + n for n in
                ('M_SUBSCRIPTION_PLANS', 'M_CURRENCY_TOTALS', 'INVOICE_PERIODS', 'PERIOD_CLOSE')]
    results = [result(before, after, n.split('.')[1], n, n.removeprefix('SFX_')) for n in outputs]
    summaries = {}
    for label, con, name in (('legacy', before, 'SFX_BILLING.PERIOD_CLOSE'),
                             ('duckdb', after, 'BILLING.PERIOD_CLOSE')):
        try:
            summaries[label] = con.execute('SELECT * FROM ' + BOARD.relation(name)).fetchall()
        except duckdb.Error:
            summaries[label] = None
    before.close()
    after.close()
    return {'results': results, 'execution_errors': errors, 'close_summary': summaries}


def stage(con, table, path, fields):
    columns = ', '.join(f'FIELD{i} VARCHAR' for i in range(1, fields + 1))
    con.execute(f'CREATE TABLE PC_STAGE.{BOARD.quote(table)} ({columns}, "METADATA$FILE_ROW_NUMBER" BIGINT)')
    with path.open(newline='', encoding='utf-8') as handle:
        rows = [tuple((r[i] or None) if i < len(r) else None for i in range(fields)) + (n,)
                for n, r in enumerate(csv.reader(handle, delimiter='|', quoting=csv.QUOTE_NONE), 1) if r]
    if rows:
        copy_rows(con, 'PC_STAGE.' + table, rows)


def render_model(text, day, config):
    def capture(**values):
        config.update(values)
        return ''
    return Environment(undefined=StrictUndefined).from_string(text).render(
        config=capture, ref=lambda name: 'PC_BILLING.' + name.removeprefix('pc_billing__').upper(),
        var=lambda name, default=None: day.strftime('%Y%m%d') if name == 'load_date' else default,
        is_incremental=lambda: False)


def pc(dsn, day, landing):
    mappings = [r for r in inventory() if r['folder'] == 'SFX_BILLING']
    names = {'SFX_BILLING.' + r['target_table'] for r in mappings}
    names.add('SFX_BILLING.GL_ACCOUNT')
    before, ready, source_errors = BOARD.source_snapshot(dsn, names, copy_rows=copy_rows)
    after = duckdb.connect()
    for schema in ('PC_STAGE', 'PC_BILLING', 'PC_SRC'):
        after.execute('CREATE SCHEMA ' + schema)
    definitions = before.execute('DESCRIBE SFX_BILLING.GL_ACCOUNT').fetchall()
    after.execute('CREATE TABLE PC_SRC.GL_ACCOUNT (' + ','.join(
        BOARD.quote(c[0]) + ' ' + c[1] for c in definitions) + ')')
    data = before.execute('SELECT * FROM SFX_BILLING.GL_ACCOUNT').fetchall()
    if data:
        copy_rows(after, 'PC_SRC.GL_ACCOUNT', data)
    errors = [{'step': n, 'error': e} for n, e in source_errors.items()]
    order = ('stg_customer_account', 'customer_account', 'stg_invoice_hdr', 'invoice_hdr',
             'invoice_line', 'payment', 'gl_journal_line')
    executed = {}
    for table in order:
        model = 'pc_billing__' + table
        config = {}
        try:
            query = render_model((MODELS / (model + '.sql')).read_text(), day, config)
            stage_match = re.search(r'@[^\s]+/([A-Z_]+)/\s*\(.*?\)', query, re.S)
            if stage_match:
                source_table = stage_match.group(1)
                fields = max(map(int, re.findall(r'\$(\d+)', query)))
                stage(after, source_table, landing / 'billing' / source_table / (day.strftime('%Y%m%d') + '.psv'), fields)
                query = query[:stage_match.start()] + 'PC_STAGE.' + source_table + query[stage_match.end():]
                query = re.sub(r'\$(\d+)', r'FIELD\1', query)
                query = query.replace('METADATA$FILE_ROW_NUMBER', '"METADATA$FILE_ROW_NUMBER"')
            statement = next(translated(query, day))
            executed[model] = {'sql': statement, 'config': config, 'mode': 'full-refresh SELECT'}
            after.execute('CREATE TABLE PC_BILLING.' + BOARD.quote(table.upper()) + ' AS ' + statement)
        except (*ERRORS, OSError) as error:
            errors.append({'step': model, 'error': str(error)})
    results = [result(before, after, r['mapping'], 'SFX_BILLING.' + r['target_table'],
                      r['after_table']) for r in mappings]
    before.close()
    after.close()
    return {'results': results, 'execution_errors': errors, 'models': executed,
            'mode': 'checked-in dbt SELECTs transpiled to DuckDB; full refresh, no Snowflake hooks'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--business-date', default='20261109')
    parser.add_argument('--rows', type=int, default=20000)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    day = dt.datetime.strptime(args.business_date, '%Y%m%d').date()
    evidence = json.loads((args.output / 'legacy-snapshot.json').read_text())
    if evidence['rows'] != args.rows or evidence['business_date'] != args.business_date:
        parser.error('Run legacy with the same rows and business date first')
    port = os.environ['TD_PG_PORT']
    baseline = f'host=127.0.0.1 port={port} dbname=sfx_windows_close_baseline user=postgres'
    current = f'host=127.0.0.1 port={port} dbname=teradata user=postgres'
    billing = bteq(baseline, day)
    (args.output / 'billing-duckdb.json').write_text(json.dumps(billing, indent=2, default=str) + '\n')
    print_results('BTEQ', billing['results'])
    for label, rows in billing['close_summary'].items():
        print(f'{label.upper()} CLOSE: currency | invoice count | total amount', flush=True)
        if rows is None:
            print('UNAVAILABLE: report execution failed (see JSON)', flush=True)
        else:
            for row in rows:
                print(' | '.join(map(str, row)), flush=True)
    powercenter = pc(current, day, ROOT / 'warehouse/landing')
    (args.output / 'pc-duckdb.json').write_text(json.dumps(powercenter, indent=2, default=str) + '\n')
    print_results('PC', powercenter['results'])
    for group in (billing, powercenter):
        for error in group['execution_errors']:
            print(f"EXECUTION ERROR {error['step']}: {error['error'].splitlines()[0]}", flush=True)
    print('All comparisons printed; RED is measured evidence, not a successful migration.', flush=True)


if __name__ == '__main__':
    main()
