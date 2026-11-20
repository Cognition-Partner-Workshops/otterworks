import importlib.util
from pathlib import Path

import duckdb
import pytest
from sqlglot import exp

from parity import local_billing, local_documents, object_board


ROOT = Path(__file__).resolve().parents[3]
BILLING = ROOT/'migration/dw-exit/billing'


@pytest.mark.parametrize('populated', [False, True])
def test_storage_stage_reads_converted_documents_only(populated):
    with duckdb.connect() as db:
        db.execute('CREATE SCHEMA DOCUMENTS')
        db.execute('CREATE SCHEMA BILLING')
        db.execute('CREATE TABLE DOCUMENTS.STORAGE_USAGE_DAILY (CUSTOMER_ID BIGINT, USAGE_DT DATE, BYTES_USED BIGINT)')
        db.execute('CREATE TABLE BILLING.SUBSCRIPTION (CUSTOMER_ID BIGINT, SUBSCRIPTION_ID BIGINT)')
        db.execute('CREATE TABLE BILLING.INVOICE_HDR (CUSTOMER_ID BIGINT, INVOICE_ID BIGINT)')
        db.execute('CREATE TABLE BILLING.USAGE_DAILY (USAGE_ID BIGINT, CUSTOMER_ID BIGINT, SUBSCRIPTION_ID BIGINT, USAGE_DT DATE, UNITS BIGINT, USAGE_TYPE VARCHAR)')
        db.execute('CREATE TABLE BILLING.INVOICE_LINE (INVOICE_LINE_ID BIGINT, INVOICE_ID BIGINT, LINE_NO INTEGER, DESCRIPTION VARCHAR, QUANTITY INTEGER, UNIT_PRICE DECIMAL(18,2), LINE_AMOUNT DECIMAL(18,2))')
        if populated:
            db.execute("INSERT INTO DOCUMENTS.STORAGE_USAGE_DAILY VALUES (1,'2026-11-09',1073741824),(1,'2026-12-01',999)")
            db.execute('INSERT INTO BILLING.SUBSCRIPTION VALUES (1,10)')
            db.execute('INSERT INTO BILLING.INVOICE_HDR VALUES (1,100)')
        for _ in range(2):
            for statement in local_billing.statements(BILLING/'15_storage.sql', '20261109'):
                db.execute(statement.sql(dialect='duckdb'))
        assert db.execute('SELECT UNITS FROM BILLING.USAGE_DAILY').fetchall() == ([(1073741824,)] if populated else [])
        assert db.execute('SELECT LINE_NO, LINE_AMOUNT FROM BILLING.INVOICE_LINE').fetchall() == ([(900, .25)] if populated else [])


def test_storage_stage_rejects_another_writer(tmp_path):
    path = tmp_path/'15_storage.sql'
    path.write_text('INSERT INTO BILLING.USAGE_DAILY SELECT * FROM BILLING.STORAGE_USAGE_INPUT;')
    with pytest.raises(ValueError, match='single writer'):
        list(local_billing.statements(path, '20261109'))


@pytest.mark.parametrize('passed', [False, True])
def test_billing_storage_finance_gate_does_not_hide_parity_failures(passed):
    rows = [dict(name=name, subject_area='billing', status='green' if passed else 'red')
            for name in ('SFX_BILLING.USAGE_DAILY', 'SFX_BILLING.INVOICE_LINE')]
    object_board.documents_apply_storage(rows, None)
    assert {row['status'] for row in rows} == ({'amber'} if passed else {'red'})
    assert 'billing' not in object_board.HELD_BACK_AREAS


@pytest.mark.parametrize('missing', [False, True])
def test_board_materializes_documents_from_staging_not_legacy_storage(missing):
    with duckdb.connect() as before:
        names = set()
        for area, directory in (('BILLING', BILLING), ('DOCUMENTS', local_documents.CONVERSIONS)):
            before.execute('CREATE SCHEMA SFX_'+area)
            for statement in local_billing.statements(directory/'00_tables.sql', '20261109'):
                for table in statement.find_all(exp.Table):
                    table.set('db', exp.to_identifier('SFX_'+area))
                for column in statement.find_all(exp.ColumnDef):
                    column.set('constraints', [])
                before.execute(statement.sql(dialect='duckdb'))
            names.update('SFX_'+area+'.'+r[0] for r in before.execute(
                'SELECT table_name FROM information_schema.tables WHERE table_schema=?', ['SFX_'+area]).fetchall())
        before.execute("INSERT INTO SFX_DOCUMENTS.STG_STORAGE_USAGE_DAILY VALUES (1,1,1,'2026-11-09',100,2)")
        before.execute("INSERT INTO SFX_DOCUMENTS.STORAGE_USAGE_DAILY VALUES (1,1,1,'2026-11-09',9999,2)")
        if missing:
            before.execute('DROP TABLE SFX_DOCUMENTS.STG_STORAGE_USAGE_DAILY')
        after, ready, errors = object_board.materialize(before, names, BILLING)
        try:
            if missing:
                assert not ready and 'Converted documents storage input unavailable' in errors['*']
            else:
                assert not errors
                assert after.execute('SELECT BYTES_USED FROM DOCUMENTS.STORAGE_USAGE_DAILY').fetchall() == [(100,)]
                assert after.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name='STORAGE_USAGE_INPUT'").fetchone()[0] == 0
        finally:
            after.close()


def test_deploy_orders_documents_storage_before_monthly_and_close(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location('billing_deploy', BILLING/'deploy.py')
    deploy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(deploy)
    queries = []

    class Cursor:
        sfqid = 'offline'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, query, params=None):
            queries.append(query)

        def fetchall(self):
            return []

        def fetchone(self):
            return [0]

        def cursor(self):
            return self

    monkeypatch.setattr(deploy, 'connect', lambda *args: Cursor())
    deploy.run('20261109', tmp_path/'evidence.json')
    storage = next(i for i,q in enumerate(queries) if '.OPS."10_STORAGE_MONTHLY"' in q)
    monthly = next(i for i,q in enumerate(queries) if q.startswith('CALL ') and '.BILLING.P_MONTHLY_INVOICE' in q)
    close = next(i for i,q in enumerate(queries) if 'SET\nPRIOR_PERIOD_END_DT' in q)
    assert storage < monthly < close
    assert not any('STORAGE_USAGE_INPUT' in q for q in queries)
