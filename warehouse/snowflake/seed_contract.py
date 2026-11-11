"""Shared seed column shapes and headered Snowflake landing preparation."""
import csv
from decimal import Decimal
import gzip
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1]))
from warehouse.seed.columns import TABLES


def column_type(kind):
    types = {'B': 'BIGINT', 'I': 'INTEGER', 'N': 'NUMBER(12,2)',
             'Q': 'NUMBER(12,4)', 'D': 'DATE', 'T': 'TIMESTAMP_NTZ'}
    if kind in types:
        return types[kind]
    if kind[0] in ('C', 'V') and kind[1:].isdigit():
        return f'VARCHAR({int(kind[1:])})'
    raise ValueError(f'Unsupported seed type: {kind}')


def seed_spec():
    spec = {}
    for table in TABLES:
        spec.setdefault(table.area, {})[table.name] = {
            c.name: column_type(c.kind) for c in table.columns}
    return spec


def seed_rows(path, table):
    with path.open(newline='', encoding='utf-8') as stream:
        for number, values in enumerate(csv.reader(stream, delimiter='|'), 1):
            if len(values) != len(table.names):
                raise ValueError(f'{table.area}/{table.name} row {number}: expected {len(table.names)} columns, got {len(values)}')
            yield dict(zip(table.names, values))


def journal_rows(source, date):
    tables = {t.name: t for t in TABLES}

    def rows(name):
        return seed_rows(source / 'billing' / name / f'{date}.psv', tables[name])

    accounts = {r['ACCOUNT_NUMBER']: r['GL_ACCOUNT_ID'] for r in rows('GL_ACCOUNT')}
    for number in ('1000', '1200', '2200', '4000'):
        if number not in accounts:
            raise ValueError(f'Seed chart is missing posting account {number}')
    currencies = {r['INVOICE_ID']: r['CURRENCY_CD'] for r in rows('INVOICE_HDR')}
    line_id = journal_id = 0
    for name, date_column in (('INVOICE_HDR', 'INVOICE_DT'), ('PAYMENT', 'PAYMENT_DT'), ('CREDIT_NOTE', 'CREDIT_DT')):
        for row in rows(name):
            journal_id += 1
            if name == 'INVOICE_HDR':
                entries = (('1200', row['TOTAL_AMOUNT'], '0.00'),
                           ('4000', '0.00', row['SUBTOTAL_AMOUNT']),
                           ('2200', '0.00', row['TAX_AMOUNT']))
            elif name == 'PAYMENT':
                entries = (('1000', row['AMOUNT'], '0.00'), ('1200', '0.00', row['AMOUNT']))
            else:
                entries = (('4000', row['AMOUNT'], '0.00'), ('1200', '0.00', row['AMOUNT']))
            if sum(Decimal(e[1]) - Decimal(e[2]) for e in entries) != 0:
                raise ValueError(f'Unbalanced seed transaction: {name}/{row[next(iter(row))]}')
            for account, debit, credit in entries:
                line_id += 1
                yield dict(JOURNAL_LINE_ID=line_id, JOURNAL_ID=journal_id,
                           INVOICE_ID=row['INVOICE_ID'],
                           CREDIT_NOTE_ID=row.get('CREDIT_NOTE_ID', ''),
                           GL_ACCOUNT_ID=accounts[account], POSTING_DT=row[date_column],
                           CURRENCY_CD=row.get('CURRENCY_CD', currencies[row['INVOICE_ID']]),
                           DEBIT_AMOUNT=debit, CREDIT_AMOUNT=credit,
                           DESCRIPTION=f'Seed fixture {name.lower()} posting')


def prepare_seed(source, destination, date):
    source, destination = Path(source), Path(destination)
    for table in TABLES:
        path = source / table.area / table.name / f'{date}.psv'
        if not path.is_file():
            raise FileNotFoundError(f'Missing seed landing file: {table.area}/{table.name}/{date}.psv')
    result = []
    for table in TABLES:
        path = source / table.area / table.name / f'{date}.psv'
        fallback = table.name == 'GL_JOURNAL_LINE' and path.stat().st_size == 0
        fields = list(table.names)
        if table.name == 'GL_JOURNAL_LINE':
            fields.append('JOURNAL_ID')
        output = destination / table.area / table.name / f'{date}.psv.gz'
        output.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with gzip.open(output, 'wt', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, delimiter='|', lineterminator='\n')
            writer.writeheader()
            rows = journal_rows(source, date) if fallback else seed_rows(path, table)
            for row in rows:
                if table.name == 'GL_JOURNAL_LINE':
                    row.setdefault('JOURNAL_ID', row['INVOICE_ID'])
                writer.writerow(row)
                count += 1
        result.append((table.area, table.name, output, count))
        print(f'Prepared {table.area}.{table.name}: {count} rows' + (' (scaled journal fixture; shared seed journal is empty)' if fallback else ''))
    return result
