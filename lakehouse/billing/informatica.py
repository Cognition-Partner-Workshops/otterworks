"""Ordered PowerCenter billing writers, isolated from the BTEQ serving states."""

import argparse
import ast
import csv
import datetime as dt
import json
import operator
import os
import re
import tempfile
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from defusedxml import ElementTree as ET
from pyspark.sql import types as T

from lakehouse.orchestration.graph import business_date
from lakehouse.runtime.layout import ROOT, data_root
from lakehouse.runtime.session import create_session
from lakehouse.runtime.informatica_settings import resolve
from warehouse.seed.columns import TABLES


REPOSITORY = ROOT.parent / 'etl/informatica/repository/SFX_BILLING/wf_SFX_BILLING_DAILY.XML'
FOLDER = ET.parse(REPOSITORY).find('.//FOLDER')
ORDER = ('STG_CUSTOMER_ACCOUNT', 'CUSTOMER_ACCOUNT', 'STG_INVOICE_HDR',
         'INVOICE_HDR', 'INVOICE_LINE', 'GL_JOURNAL_LINE', 'PAYMENT')
BASE = {'CUSTOMER_ACCOUNT': 'silver_billing.customer_account',
        'STG_CUSTOMER_ACCOUNT': 'silver_billing.stg_customer_account',
        'STG_INVOICE_HDR': 'silver_billing.stg_invoice_hdr',
        'INVOICE_HDR': 'gold_billing.closed_invoice_hdr',
        'INVOICE_LINE': 'gold_billing.monthly_invoice_line',
        'GL_JOURNAL_LINE': 'gold_billing.monthly_gl_journal_line',
        'PAYMENT': 'silver_billing.payment', 'GL_ACCOUNT': 'silver_billing.gl_account'}
METADATA = {t.name: t for t in TABLES if t.area == 'billing'}
TARGETS = {t.get('NAME'): list(t.findall('TARGETFIELD')) for t in FOLDER.findall('TARGET')}


def atomic(path, write):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='',
                                         dir=path.parent, delete=False) as handle:
            name = Path(handle.name)
            write(handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if name is not None:
            name.unlink(missing_ok=True)


def save(path, value):
    atomic(path, lambda h: json.dump(value, h, default=str, sort_keys=True))


def text(value):
    if value is None:
        return ''
    if isinstance(value, dt.datetime):
        return value.strftime('%m/%d/%Y %H:%M:%S.') + f'{value.microsecond:06d}'
    return str(value)


def records(path, rows, columns):
    def write(handle):
        writer = csv.writer(handle, delimiter='|', lineterminator='\n')
        for row in rows:
            writer.writerow([text(row.get(c)) for c in columns])
    atomic(path, write)


def columns(table):
    base = table.removeprefix('STG_')
    return [c.name.lower() for c in METADATA[base].columns]


def shape(row, table):
    result = {}
    for field in TARGETS.get(table, []):
        name, kind = field.get('NAME').lower(), field.get('DATATYPE')
        value = row.get(name)
        if value is not None:
            if kind in ('bigint', 'integer'):
                value = int(Decimal(value))
                bits = 64 if kind == 'bigint' else 32
                if not -(2 ** (bits - 1)) <= value < 2 ** (bits - 1):
                    raise ValueError('integer out of range')
            elif kind == 'decimal':
                value = Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                if not value.is_finite() or abs(value) >= Decimal('1000000000000'):
                    raise ValueError('numeric out of range')
            elif kind == 'date':
                if isinstance(value, dt.datetime):
                    value = value.date()
                elif isinstance(value, str):
                    value = dt.date.fromisoformat(value)
            elif kind in ('varchar', 'char'):
                value = text(value)
                limit = int(field.get('PRECISION'))
                if len(value) > limit:
                    if value[limit:].strip(' '):
                        raise ValueError('value too long')
                    value = value[:limit]
                if kind == 'char':
                    value = value.rstrip(' ')
        result[name] = value
    if not table.startswith('STG_') and result.get(columns(table)[0]) is None:
        raise ValueError('null primary identifier')
    return result


def decimal(value, scale=2):
    if value is None:
        return None
    if isinstance(value, str):
        match = re.match(r'\s*[-+]?(\d+(\.\d*)?|\.\d+)', value)
        if not match:
            raise ValueError('invalid decimal')
        value = match[0].strip()
    return Decimal(value).quantize(Decimal(1).scaleb(-int(scale)), rounding=ROUND_HALF_UP)


def integer(value):
    if value is None:
        return None
    match = re.match(r'[-+]?\d+(\.\d*)?', str(value).strip())
    if not match:
        raise ValueError('invalid integer')
    return int(Decimal(match[0]))


def evaluate(expression, row, currency='USD'):
    expression = expression.replace('$$CURRENCY_DEFAULT', 'CURRENCY_DEFAULT')
    tree = ast.parse(expression, mode='eval')
    functions = {
        'TO_BIGINT': integer, 'TO_INTEGER': integer, 'TO_DECIMAL': decimal,
        'TO_DATE': lambda v, fmt: None if v is None else dt.datetime.strptime(v, '%Y-%m-%d'),
        'LTRIM': lambda v: None if v is None else str(v).lstrip(' '),
        'RTRIM': lambda v: None if v is None else str(v).rstrip(' '),
        'UPPER': lambda v: None if v is None else str(v).upper(),
        'NVL': lambda a, b: b if a is None else a,
        'ROUND': decimal,
    }

    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return currency if node.id == 'CURRENCY_DEFAULT' else row[node.id]
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in functions:
            return functions[node.func.id](*(visit(a) for a in node.args))
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Mult, ast.Add, ast.Sub)):
            a, b = visit(node.left), visit(node.right)
            return None if a is None or b is None else {ast.Mult: operator.mul, ast.Add: operator.add,
                                                       ast.Sub: operator.sub}[type(node.op)](a, b)
        raise ValueError('Unsupported billing expression: ' + expression)
    return visit(tree)


def flat_rows(landing, table, day):
    names = columns(table)
    path = Path(landing) / 'billing' / table / (day + '.psv')
    with path.open(newline='', encoding='utf-8') as handle:
        for row in csv.reader(handle, delimiter='|', quoting=csv.QUOTE_NONE):
            if row:
                source = next(s for s in FOLDER.findall('SOURCE') if s.get('NAME') == 'FF_' + table)
                limits = [int(f.get('PRECISION')) for f in source.findall('SOURCEFIELD')]
                yield dict(zip([c.upper() for c in names],
                               [v[:n] or None for v, n in zip(row, limits)] + [None] * len(names)))


def transformed(table, raw, errors, currency):
    mapping = next(m for m in FOLDER.findall('MAPPING') if m.get('NAME') == 'm_SFX_' + table)
    transformation = next(t for t in mapping.findall('TRANSFORMATION') if t.get('TYPE') == 'Expression')
    fields = [f for f in transformation.findall('TRANSFORMFIELD') if f.get('PORTTYPE') == 'OUTPUT']
    for row in raw:
        try:
            result = {}
            for field in fields:
                value = evaluate(field.get('EXPRESSION'), row, currency)
                if value is not None and field.get('DATATYPE') == 'string':
                    value = str(value)[:int(field.get('PRECISION'))]
                result[field.get('NAME').removeprefix('o_').lower()] = value
            yield result
        except (ValueError, TypeError, InvalidOperation, OverflowError):
            errors.append({'stage': transformation.get('NAME'), 'row': row})


def bad_record(rt, row, names):
    return ','.join([str(rt)] + ['D,' + text(row.get(c).date() if isinstance(row.get(c), dt.datetime)
                                           else row.get(c)) for c in names])


def mapping(table, prior, raw, accounts=(), gl_accounts=(), currency='USD', tax_rate='0.0825', sequence=8000000000001):
    errors, rejects = [], []
    names = columns(table)
    rows = [dict(r) for r in prior]
    lookup = {r.get(names[0]) for r in prior}
    customer_ids = {r['customer_id'] for r in accounts}

    def write(row, rt=0, instance=None):
        instance = instance or table
        try:
            target = shape(row, table)
            if rt == 3:
                raise ValueError('DD_REJECT')
            matches = [i for i, r in enumerate(rows) if target[names[0]] is not None and r[names[0]] == target[names[0]]]
            if rt == 1 and matches:
                for i in matches:
                    rows[i].update(target)
            elif rt == 0 and matches and table != 'GL_JOURNAL_LINE' and not table.startswith('STG_'):
                raise ValueError('duplicate primary identifier')
            else:
                rows.append(target)
        except (ValueError, InvalidOperation, OverflowError):
            rejects.append({'target': instance, 'record': bad_record(rt, row, [c for c in names
                                           if c != 'credit_note_id' or table != 'GL_JOURNAL_LINE'])})

    if table.startswith('STG_'):
        rows = []
    if table in ('CUSTOMER_ACCOUNT', 'INVOICE_HDR'):
        for row in raw:
            rt = 0 if row.get(names[0]) not in lookup or row.get(names[0]) is None else 1
            if table == 'INVOICE_HDR' and (row.get('customer_id') not in customer_ids or
                                          row.get('customer_id') is None or row.get('total_amount') is None or
                                          row.get('invoice_dt') is None):
                write(row, 3, 'INVOICE_HDR1')
            else:
                write(row, rt)
    elif table == 'GL_JOURNAL_LINE':
        eligible = [r for r in raw if r.get('total_amount') is not None and r['total_amount'] != 0]
        ids = {r['invoice_id'] for r in eligible if r['invoice_id'] is not None}
        rows = [r for r in rows if r.get('credit_note_id') is not None or r.get('invoice_id') not in ids]
        rate = Decimal(tax_rate)
        calculated = []
        for r in raw:
            try:
                tax = r.get('tax_amount')
                if tax is None and r.get('total_amount') is not None:
                    tax = decimal(r['total_amount'] * rate / (1 + rate))
                if r.get('total_amount') is not None and r['total_amount'] != 0:
                    calculated.append((r, tax))
            except ArithmeticError:
                errors.append({'stage': 'EXP_JOURNAL', 'row': r})
        for branch, account, description in [(0, '1200', 'Accounts receivable '),
                                              (1, '2300', 'Deferred revenue '),
                                              (2, '2200', 'Sales tax payable ')]:
            gl_id = next((g['gl_account_id'] for g in gl_accounts if g['account_number'] == account), None)
            for r, tax in calculated:
                if branch == 2 and (tax is None or tax == 0):
                    continue
                total = r['total_amount']
                if sequence > 9223372036854775807:
                    raise OverflowError('Sequence end value exceeded')
                row = dict(journal_line_id=sequence, invoice_id=r['invoice_id'], credit_note_id=None,
                           gl_account_id=gl_id, posting_dt=r.get('invoice_dt'),
                           currency_cd=None if r.get('currency_cd') is None else r['currency_cd'].strip(' ').upper()[:3],
                           debit_amount=total if branch == 0 else Decimal(0),
                           credit_amount=Decimal(0) if branch == 0 else (total - tax if branch == 1 else tax),
                           description=(description + text(r.get('invoice_number')))[:120])
                write(row, 0, 'GL_JOURNAL_LINE' + (str(branch) if branch else ''))
                sequence += 1
    else:
        for row in transformed(table, raw, errors, currency):
            if table == 'INVOICE_LINE' and (row['invoice_id'] is None or row['invoice_line_id'] is None):
                continue
            if table == 'PAYMENT' and (row['payment_id'] is None or row['amount'] is None):
                continue
            write(row, 1 if table in ('PAYMENT', 'INVOICE_LINE') else 0)
    return rows, rejects, errors, sequence


def output(root, table, rows, rejects, errors):
    names = columns(table)
    canonical = sorted(rows, key=lambda r: tuple(text(r.get(c)) for c in names))
    records(root / (table.lower() + '.psv'),
            [dict(ordinal=i, **r) for i, r in enumerate(canonical, 1)], ['ordinal'] + names)
    records(root / (table.lower() + '_rejects.psv'),
            [dict(ordinal=i, **r) for i, r in enumerate(sorted(rejects, key=lambda r: r['target']), 1)],
            ['ordinal', 'target', 'record'])
    records(root / (table.lower() + '_errors.psv'), [{'transformation_errors': len(errors)}], ['transformation_errors'])
    transformation_rejects = []
    mapping = next(m for m in FOLDER.findall('MAPPING') if m.get('NAME') == 'm_SFX_' + table)
    for number, error in enumerate(errors, 1):
        transformation = next(t for t in mapping.findall('TRANSFORMATION') if t.get('NAME') == error['stage'])
        inputs = [f.get('NAME') for f in transformation.findall('TRANSFORMFIELD') if 'INPUT' in f.get('PORTTYPE', '')]
        row = {k.lower(): error['row'].get(k, error['row'].get(k.lower())) for k in inputs}
        payload = {k: None if v is None else text(v.date() if isinstance(v, dt.datetime) else v) for k, v in row.items()}
        transformation_rejects.append({'ordinal': number, 'stage': error['stage'], 'record': json.dumps(payload, sort_keys=True)})
    records(root / (table.lower() + '_transformation_rejects.psv'), transformation_rejects, ['ordinal', 'stage', 'record'])


def delta(spark, root, table, rows):
    types = {'bigint': T.LongType(), 'integer': T.IntegerType(), 'date': T.DateType(),
             'decimal': T.DecimalType(14, 2)}
    schema = T.StructType([T.StructField('ordinal', T.LongType(), False)] +
                          [T.StructField(f.get('NAME').lower(), types.get(f.get('DATATYPE'), T.StringType()))
                           for f in TARGETS[table]])
    ordered = sorted(rows, key=lambda r: tuple(text(r.get(c)) for c in columns(table)))
    frame = spark.createDataFrame([(i,) + tuple(r.get(f.name) for f in schema.fields[1:])
                                   for i, r in enumerate(ordered, 1)], schema)
    frame.write.format('delta').mode('overwrite').option('overwriteSchema', 'true').save(str(root / 'delta' / table.lower()))


def parameters():
    values = resolve('SFX_BILLING', 'wf_SFX_BILLING_DAILY', 's_m_SFX_GL_JOURNAL_LINE')
    return values['$$CURRENCY_DEFAULT'], values['$$SALES_TAX_RATE']


def run(spark, landing, day, destination, selected=None):
    business_date(day)
    state = {t: [{k: v.rstrip(' ') if isinstance(v, str) and next(
        c for c in METADATA[t.removeprefix('STG_')].columns if c.name.lower() == k).kind.startswith('C')
        and not t.startswith('STG_') else v for k, v in r.asDict().items()} for r in spark.table(model).collect()]
             for t, model in BASE.items()}
    result = {p.stem: json.loads(p.read_text()) for p in (destination / 'sessions').glob('*.json')} if selected else {}
    currency, tax_rate = parameters()
    counter = destination.parent / 'sequence.json'
    sequence = json.loads(counter.read_text())['next'] if counter.exists() else 8000000000001
    if not selected or not (destination / 'inputs.json').exists():
        save(destination / 'inputs.json', {'business_date': day, 'sequence_start': sequence,
                                          'currency_default': currency, 'sales_tax_rate': tax_rate})
        save(destination / 'inputs' / 'prior.json', state)
    if selected:
        required = {'CUSTOMER_ACCOUNT': ['STG_CUSTOMER_ACCOUNT'],
                    'INVOICE_HDR': ['STG_INVOICE_HDR', 'CUSTOMER_ACCOUNT'],
                    'GL_JOURNAL_LINE': ['STG_INVOICE_HDR']}.get(selected, [])
        for table in required:
            if result.get(table, {}).get('Status') == 'SUCCEEDED':
                state[table] = [shape(r, table) for r in json.loads(
                    (destination / 'state' / (table + '.json')).read_text())]
    prerequisites = {'CUSTOMER_ACCOUNT': ['STG_CUSTOMER_ACCOUNT'],
                     'INVOICE_HDR': list(ORDER[:3]), 'INVOICE_LINE': list(ORDER[:3]),
                     'GL_JOURNAL_LINE': ['INVOICE_HDR', 'INVOICE_LINE'], 'PAYMENT': ['GL_JOURNAL_LINE']}
    for table in ((selected,) if selected else ORDER):
        allowed = all(result.get(t, {}).get('Status') == 'SUCCEEDED' for t in prerequisites.get(table, []))
        if table == 'PAYMENT':
            allowed = allowed and result.get('GL_JOURNAL_LINE', {}).get('TgtFailedRows') == 0
        if not allowed:
            output(destination, table, state[table], [], [])
            delta(spark, destination, table, state[table])
            result[table] = {'Status': 'NOTSTARTED', 'TgtFailedRows': 0}
            save(destination / 'sessions' / (table + '.json'), result[table])
            continue
        raw = state['STG_CUSTOMER_ACCOUNT'] if table == 'CUSTOMER_ACCOUNT' else state['STG_INVOICE_HDR'] if table in (
            'INVOICE_HDR', 'GL_JOURNAL_LINE') else flat_rows(landing, table.removeprefix('STG_'), day)
        rows, rejects, errors, sequence = mapping(table, state[table], raw, state['CUSTOMER_ACCOUNT'],
                                                  state['GL_ACCOUNT'], currency, tax_rate, sequence)
        state[table] = rows
        delta(spark, destination, table, rows)
        output(destination, table, rows, rejects, errors)
        save(destination / 'state' / (table + '.json'), rows)
        result[table] = {'Status': 'SUCCEEDED', 'TgtFailedRows': len(rejects) + len(errors)}
        save(destination / 'sessions' / (table + '.json'), result[table])
        print(f'Informatica {table}: {len(rows)} target rows, {len(rejects)} writer rejects, {len(errors)} transformation errors', flush=True)
        if table == 'GL_JOURNAL_LINE':
            save(counter, {'next': sequence})
    save(destination / 'sessions.json', result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--business-date', required=True)
    parser.add_argument('--landing', type=Path, required=True)
    parser.add_argument('--table', choices=ORDER)
    args = parser.parse_args()
    business_date(args.business_date)
    root = data_root() / 'informatica' / args.business_date
    spark = None
    try:
        spark = create_session()
        run(spark, args.landing, args.business_date, root, args.table)
    except Exception as exc:
        table = args.table or 'GL_JOURNAL_LINE'
        failed = {'Status': 'FAILED', 'TgtFailedRows': 0, 'error': type(exc).__name__ + ': ' + str(exc)}
        save(root / 'sessions' / (table + '.json'), failed)
        result = {p.stem: json.loads(p.read_text()) for p in (root / 'sessions').glob('*.json')}
        save(root / 'sessions.json', result)
    finally:
        if spark is not None:
            spark.stop()


if __name__ == '__main__':
    main()
