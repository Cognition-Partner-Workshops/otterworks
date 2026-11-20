from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

from parity import pc_billing

ROOT = Path(__file__).resolve().parents[3]
MODELS = ROOT/'warehouse/dbt/models/pc/billing'


def query(table):
    config = {}
    result = pc_billing.model_query(MODELS/('pc_billing__'+table.lower()+'.sql'), config, '20261109')
    return result, config


@pytest.fixture
def db():
    with duckdb.connect() as connection:
        connection.execute('CREATE SCHEMA PC_FILES')
        connection.execute('CREATE SCHEMA PC_BILLING')
        connection.execute('CREATE SCHEMA PC_SRC')
        for name, count in (('CUSTOMER_ACCOUNT', 9), ('INVOICE_HDR', 18), ('INVOICE_LINE', 7), ('PAYMENT', 7)):
            columns = ', '.join(f'C{i} VARCHAR' for i in range(1, count+1))
            connection.execute(f'CREATE TABLE PC_FILES.{name} ({columns}, METADATA$FILE_ROW_NUMBER BIGINT)')
        connection.execute('CREATE TABLE PC_SRC.GL_ACCOUNT (ACCOUNT_NUMBER VARCHAR, GL_ACCOUNT_ID BIGINT)')
        yield connection


def test_all_shipped_models_accept_empty_inputs(db):
    for table in pc_billing.TABLES:
        sql, config = query(table)
        db.execute('CREATE TABLE PC_BILLING.'+table+' AS '+sql)
        assert db.execute('SELECT * FROM PC_BILLING.'+table).fetchall() == []
        assert config['materialized'] in ('table', 'incremental')


def test_explicit_line_and_payment_expressions(db):
    db.execute("INSERT INTO PC_FILES.INVOICE_LINE VALUES ('1', '2', '3.9', ' item ', '2.9', '1.236', NULL, 1)")
    line, _ = query('INVOICE_LINE')
    assert db.execute(line).fetchall() == [(1, 2, 3, 'item', 2, Decimal('1.24'), Decimal('2.48'))]
    db.execute("INSERT INTO PC_FILES.PAYMENT VALUES ('1', '2', '3', '2026-11-09', '1.236', ' card ', ' ref ', 1)")
    payment, _ = query('PAYMENT')
    row = db.execute(payment).fetchone()
    assert row[:3] == (1, 2, 3)
    assert row[4:] == (Decimal('1.24'), 'CARD', 'ref')
    db.execute("INSERT INTO PC_FILES.PAYMENT VALUES ('2', '2', '3', '2026-11-09', NULL, 'card', 'ref', 2)")
    assert len(db.execute(payment).fetchall()) == 1


def test_gl_routes_sequence_and_tax_fallback(db):
    db.execute("INSERT INTO PC_FILES.INVOICE_HDR (C1,C4,C7,C8,C9,METADATA$FILE_ROW_NUMBER) VALUES ('5','2026-11-09','usd','108.25','inv5',1)")
    staging, _ = query('STG_INVOICE_HDR')
    db.execute('CREATE TABLE PC_BILLING.STG_INVOICE_HDR AS '+staging)
    db.execute("INSERT INTO PC_SRC.GL_ACCOUNT VALUES ('1200',1),('2300',2),('2200',3)")
    posting, config = query('GL_JOURNAL_LINE')
    rows = db.execute(posting+' ORDER BY JOURNAL_LINE_ID').fetchall()
    assert [row[0] for row in rows] == [8000000000001, 8000000000002, 8000000000003]
    assert [(row[3], row[6], row[7]) for row in rows] == [
        (1, Decimal('108.25'), Decimal('0.00')),
        (2, Decimal('0.00'), Decimal('100.00')),
        (3, Decimal('0.00'), Decimal('8.25'))]
    assert 'CREDIT_NOTE_ID is null' in config['pre_hook'][1]


def test_invalid_model_input_does_not_become_green(db):
    db.execute("INSERT INTO PC_FILES.PAYMENT (C1,C4) VALUES ('bad','2026-11-09')")
    payment, _ = query('PAYMENT')
    with pytest.raises(duckdb.ConversionException):
        db.execute(payment).fetchall()
    with pytest.raises(ValueError, match='local PostgreSQL only'):
        pc_billing.materialize(None, None, 'host=remote.example dbname=teradata', 'unused', None)
