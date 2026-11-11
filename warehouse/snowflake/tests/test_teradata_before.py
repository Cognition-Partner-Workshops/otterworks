from contextlib import nullcontext
import csv
import gzip
from pathlib import Path
from types import SimpleNamespace

import pytest

from load import load_seed
from teradata_before import export_tables, TABLES
from test_seed_load import Cursor


class Connection:
    def __init__(self, empty=False, error=False):
        self.empty, self.error, self.queries = empty, error, []

    def cursor(self):
        return nullcontext(self)

    def execute(self, sql):
        self.queries.append(sql)
        if self.error:
            raise RuntimeError('source unavailable')
        table = sql.rsplit('.', 1)[-1]
        columns = {'INVOICE_HDR': ['invoice_id', 'invoice_dt', 'total_amount', 'due_date'],
                   'INVOICE_LINE': ['invoice_line_id', 'invoice_id', 'description'],
                   'GL_JOURNAL_LINE': ['journal_line_id', 'invoice_id', 'posting_dt', 'currency_cd']}[table]
        self.description = [(c,) for c in columns]
        self.values = {'INVOICE_HDR': (7, '2026-11-09', '419.96', '2026-12-25'),
                       'INVOICE_LINE': (8, 7, 'A|B\nC'),
                       'GL_JOURNAL_LINE': (9, 7, '2026-11-09', 'usd')}[table]

    def __iter__(self):
        return iter([] if self.empty else [self.values])


def test_export_processed_values_headers_and_billing_only(tmp_path):
    connection = Connection()
    prepared = export_tables(connection, tmp_path, '20261109')
    assert [r[1] for r in prepared] == list(TABLES)
    assert connection.queries == [f'SELECT * FROM SFX_BILLING.{name}' for name in TABLES]
    rows = {}
    for area, table, path, count in prepared:
        with gzip.open(path, 'rt', newline='') as stream:
            rows[table] = next(csv.DictReader(stream, delimiter='|'))
        assert area == 'billing' and count == 1
    assert rows['INVOICE_HDR']['TOTAL_AMOUNT'] == '419.96'
    assert rows['INVOICE_HDR']['DUE_DATE'] == '2026-12-25'
    assert rows['INVOICE_HDR']['INVOICE_HDR_ID'] == '7'
    assert rows['INVOICE_LINE']['DESCRIPTION'] == 'A|B\nC'
    assert rows['GL_JOURNAL_LINE']['JOURNAL_ID'] == '7'
    assert rows['GL_JOURNAL_LINE']['POSTING_DATE'] == '2026-11-09'
    cursor = Cursor(rows=1)
    load_seed(cursor, [(a, t, Path(p), n) for a, t, p, n in prepared],
              truncate=True, stage_prefix='teradata-before')
    assert sum(sql.startswith('DELETE FROM') for sql in cursor.commands) == 3
    assert cursor.commands.count('BEGIN') == cursor.commands.count('COMMIT') == 1
    assert not any('TRUNCATE' in sql for sql in cursor.commands)
    assert all('/teradata-before/billing/' in sql for sql in cursor.commands if sql.startswith('PUT'))
    assert all("FILES=('20261109.psv.gz')" in sql for sql in cursor.commands if sql.startswith('COPY'))


def test_export_empty_and_error_do_not_load(tmp_path):
    with pytest.raises(ValueError, match='run sfx-teradata-run first'):
        export_tables(Connection(empty=True), tmp_path, '20261109')
    with pytest.raises(RuntimeError, match='source unavailable'):
        export_tables(Connection(error=True), tmp_path, '20261109')
    with pytest.raises(ValueError, match='yyyymmdd'):
        export_tables(Connection(), tmp_path, '../bad')


def test_processed_manifest_must_be_complete(tmp_path, monkeypatch):
    import teradata_before
    monkeypatch.setattr(teradata_before.subprocess, 'run', lambda *a, **kw: SimpleNamespace(stdout='[]'))
    with pytest.raises(ValueError, match='Incomplete'):
        teradata_before.prepare_before(tmp_path, '20261109', 'python')


def test_v008_dates_and_revenue_normal_empty_and_sources():
    from datetime import date, timedelta
    import re
    import sqlite3
    import yaml
    from sfx_conn import ROOT

    sql = (ROOT / 'migrations/V008__processed_billing_compat.sql').read_text()
    views = dict(re.findall(r'CREATE OR REPLACE VIEW COMPAT\.(\w+).*?\nAS (SELECT.*?);', sql, re.S))
    contract = yaml.safe_load((ROOT / 'landing_columns.yml').read_text())['billing']
    with sqlite3.connect(':memory:') as db:
        db.create_function('DATEADD', 3, lambda unit, days, value: (date.fromisoformat(value) + timedelta(days=days)).isoformat() if value else None)
        db.create_function('TO_CHAR', 2, lambda value, pattern: value[:7] if value else None)
        for schema in ('RAW_BILLING', 'COMPAT'):
            db.execute(f"attach database ':memory:' as {schema}")
        for table in ('INVOICE_HDR', 'CUSTOMER_ACCOUNT', 'CREDIT_NOTE'):
            db.execute(f'create table RAW_BILLING.{table} (' + ','.join(c + ' NUMERIC' for c in contract[table]) + ')')
        db.execute('create table COMPAT.ACCOUNT (CUSTOMER_ID NUMERIC)')
        db.executemany('insert into COMPAT.ACCOUNT values (?)', [(1,), (2,), (3,)])
        db.executemany('insert into RAW_BILLING.CUSTOMER_ACCOUNT (CUSTOMER_ID,PAYMENT_TERMS_DAYS) values (?,?)', [(1, 45), (2, 15), (3, None)])
        db.executemany('insert into RAW_BILLING.INVOICE_HDR (INVOICE_ID,CUSTOMER_ID,INVOICE_DT,DUE_DATE,TOTAL_AMOUNT,CURRENCY_CD) values (?,?,?,?,?,?)',
                       [(1, 1, '2026-11-09', '2026-12-31', 10, 'usd'), (2, 2, '2026-11-09', None, 20, 'USD '), (3, 3, '2026-11-09', None, 30, 'USD')])
        query = views['INVOICE'].replace('DATEADD(day,', "DATEADD('day',")
        db.execute('create table COMPAT.INVOICE as ' + query)
        assert db.execute('select DUE_DATE from COMPAT.INVOICE order by INVOICE_ID').fetchall() == [('2026-12-31',), ('2026-11-24',), ('2026-12-09',)]
        revenue_rows = [('USD', '2026-11', 2, 50), ('usd', '2026-11', 1, 10)]
        assert sorted(db.execute(views['V_INVOICE_REVENUE']).fetchall()) == revenue_rows
        correction = (ROOT / 'migrations/V009__revenue_currency_labels.sql').read_text()
        revenue_query = re.search(r'\nAS (SELECT.*?);', correction, re.S).group(1)
        assert sorted(db.execute(revenue_query).fetchall()) == revenue_rows
        db.execute("insert into RAW_BILLING.CREDIT_NOTE (CREDIT_DT,ISSUE_DATE) values ('2026-11-09',NULL),('2026-11-09','2026-11-08')")
        credit = db.execute(views['CREDIT_NOTE']).fetchall()
        assert [row[-1] for row in credit] == ['2026-11-09', '2026-11-08']
        db.execute('delete from RAW_BILLING.INVOICE_HDR')
        db.execute('delete from RAW_BILLING.CREDIT_NOTE')
        db.execute('delete from COMPAT.INVOICE')
        assert db.execute(query).fetchall() == []
        assert db.execute(views['CREDIT_NOTE']).fetchall() == []
        assert db.execute(views['V_INVOICE_REVENUE']).fetchall() == []
