import csv
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path
import re
import sqlite3

import yaml

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    return {p.parent.name: list(csv.DictReader(p.open(), delimiter='|'))
            for p in (ROOT / 'fixtures/landing').rglob('*.psv')}


def test_realistic_values_and_types():
    data = fixture()
    spec = yaml.safe_load((ROOT / 'landing_columns.yml').read_text())
    for tables in spec.values():
        for table, columns in tables.items():
            for row in data[table]:
                for column, value in row.items():
                    assert not re.fullmatch(r'(?:user|email|account_name|first_name|last_name)_?\d+', value, re.I)
                    kind = columns[column]
                    if kind.startswith(('VARCHAR', 'CHAR')):
                        assert len(value) <= int(re.search(r'\d+', kind)[0])
                    elif kind in ('BIGINT', 'INTEGER'):
                        int(value)
                    elif kind.startswith('NUMBER'):
                        Decimal(value)
                    elif kind == 'DATE':
                        date.fromisoformat(value)
    assert len({r['CREATED_AT'][:10] for r in data['APP_USER']}) > 10
    assert len({r['INVOICE_DATE'] for r in data['INVOICE_HDR']}) > 10
    for row in data['APP_USER'] + data['SSO_IDENTITY']:
        assert re.fullmatch(r'[a-z]+\.[a-z]+@[a-z]+\.example', row['EMAIL'])
    for row in data['CUSTOMER_ACCOUNT']:
        assert re.fullmatch(r'ACC-\d{6}', row['ACCOUNT_NUMBER'])
        assert row['LEGAL_NAME'].endswith(' Works Ltd')
        assert row['CURRENCY_CODE'] in ('USD', 'EUR', 'GBP', 'CAD')


def test_foreign_keys_and_financial_arithmetic():
    data = fixture()
    keys = {name: {r[name + '_ID']: r for r in rows} for name, rows in data.items()}
    users = {r['USER_ID'] for r in data['APP_USER']}
    customers = {r['CUSTOMER_ID']: r for r in data['CUSTOMER_ACCOUNT']}
    for table, rows in data.items():
        for row in rows:
            for column, value in row.items():
                if column in ('OWNER_USER_ID', 'ACTOR_USER_ID', 'USER_ID', 'REVIEWER_USER_ID'):
                    assert value in users
                elif column == 'CUSTOMER_ID':
                    assert value in customers
                    assert row['CURRENCY_CODE'] == customers[value]['CURRENCY_CODE']
                elif column.endswith('_ID') and column != table + '_ID':
                    target = column[:-3]
                    if target in keys:
                        assert value in keys[target]
    lines = defaultdict(list)
    payments = defaultdict(Decimal)
    for row in data['INVOICE_LINE']:
        lines[row['INVOICE_HDR_ID']].append(row)
        assert Decimal(row['LINE_AMOUNT']) == int(row['QUANTITY']) * Decimal(row['UNIT_PRICE'])
    for row in data['PAYMENT']:
        payments[row['INVOICE_HDR_ID']] += Decimal(row['AMOUNT'])
    for row in data['INVOICE_HDR']:
        assert re.fullmatch(r'INV-2026-\d{6}', row['INVOICE_NUMBER'])
        detail = lines[row['INVOICE_HDR_ID']]
        assert Decimal(row['SUBTOTAL_AMOUNT']) == sum(Decimal(r['LINE_AMOUNT']) for r in detail)
        assert Decimal(row['TAX_AMOUNT']) == sum(Decimal(r['TAX_AMOUNT']) for r in detail)
        assert Decimal(row['TOTAL_AMOUNT']) == Decimal(row['SUBTOTAL_AMOUNT']) + Decimal(row['TAX_AMOUNT'])
        assert 0 < payments[row['INVOICE_HDR_ID']] <= Decimal(row['TOTAL_AMOUNT'])
        assert date.fromisoformat(row['DUE_DATE']) > date.fromisoformat(row['INVOICE_DATE'])
    for table in ('PAYMENT', 'CREDIT_NOTE', 'BILLING_ADJ', 'INVOICE_LINE'):
        for row in data[table]:
            invoice = keys['INVOICE_HDR'][row['INVOICE_HDR_ID']]
            assert row['CUSTOMER_ID'] == invoice['CUSTOMER_ID']
            assert row['CURRENCY_CODE'] == invoice['CURRENCY_CODE']
            if table == 'CREDIT_NOTE':
                assert 0 < Decimal(row['AMOUNT']) < Decimal(invoice['TOTAL_AMOUNT'])


def test_journal_balances_and_reconciles_to_invoice_run():
    data = fixture()
    accounts = {r['GL_ACCOUNT_ID']: r for r in data['GL_ACCOUNT']}
    journals = defaultdict(lambda: [Decimal(0), Decimal(0)])
    totals = defaultdict(Decimal)
    for row in data['GL_JOURNAL_LINE']:
        debit, credit = Decimal(row['DEBIT_AMOUNT']), Decimal(row['CREDIT_AMOUNT'])
        assert (debit > 0 and credit == 0) or (credit > 0 and debit == 0)
        account = accounts[row['GL_ACCOUNT_ID']]
        assert account['CURRENCY_CODE'] == row['CURRENCY_CODE']
        journals[row['JOURNAL_ID']][0] += debit
        journals[row['JOURNAL_ID']][1] += credit
        totals[row['CURRENCY_CODE'], account['ACCOUNT_CODE'][:4], 'DR'] += debit
        totals[row['CURRENCY_CODE'], account['ACCOUNT_CODE'][:4], 'CR'] += credit
    assert all(debit == credit for debit, credit in journals.values())
    for currency in ('USD', 'EUR', 'GBP', 'CAD'):
        invoices = [r for r in data['INVOICE_HDR'] if r['CURRENCY_CODE'] == currency]
        assert totals[currency, '1100', 'DR'] == sum(Decimal(r['TOTAL_AMOUNT']) for r in invoices)
        assert totals[currency, '4000', 'CR'] == sum(Decimal(r['SUBTOTAL_AMOUNT']) for r in invoices)
        assert totals[currency, '2100', 'CR'] == sum(Decimal(r['TAX_AMOUNT']) for r in invoices)
        receipts = sum(Decimal(r['AMOUNT']) for r in data['PAYMENT'] if r['CURRENCY_CODE'] == currency)
        assert totals[currency, '1000', 'DR'] == receipts == totals[currency, '1100', 'CR']


def test_balanced_journal_generic_normal_empty_and_errors():
    macro = (ROOT.parent / 'dbt/macros/balanced_journal.sql').read_text()
    query = macro.split('%}', 1)[1].rsplit('{%', 1)[0].replace('{{ model }}', 'journal')
    with sqlite3.connect(':memory:') as db:
        db.execute('create table journal (journal_id integer, debit_amount integer, credit_amount integer)')
        assert db.execute(query).fetchall() == []
        db.executemany('insert into journal values (?, ?, ?)', [(1, 100, 0), (1, 0, 100)])
        assert db.execute(query).fetchall() == []
        db.executemany('insert into journal values (?, ?, ?)', [(2, 50, 0), (3, None, 0)])
        assert set(db.execute(query).fetchall()) == {(2,), (3,)}
    schema = yaml.safe_load((ROOT.parent / 'dbt/models/staging/billing/schema.yml').read_text())
    model = next(m for m in schema['models'] if m['name'] == 'stg_billing__gl_journal_line')
    assert 'balanced_journal' in model['tests']
    account = next(c for c in model['columns'] if c['name'] == 'gl_account_id')
    assert {'relationships': {'to': "ref('stg_billing__gl_account')", 'field': 'gl_account_id'}} in account['tests']


def test_loader_includes_every_billing_table():
    spec = yaml.safe_load((ROOT / 'landing_columns.yml').read_text())
    procedure = (ROOT / 'migrations/V003__loaders_and_tasks.sql').read_text().split('$$;', 1)[0]
    assert all("'" + table + "'" in procedure for table in spec['billing'])
