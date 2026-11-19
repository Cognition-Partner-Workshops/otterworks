"""Freeze actual post-chain emulator rows, not a reimplementation of its results."""

import sys as _run_sys
from pathlib import Path as _RunPath
_run_sys.path.insert(0, str(_RunPath(__file__).resolve().parents[3]))
from warehouse.run_config import render as _run_render

import argparse
import io
import json
import re
import sys
from decimal import Decimal
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'warehouse/teradata'), str(ROOT / 'warehouse'), str(Path(__file__).resolve().parents[1])]

from bteq import Runner
from seed.columns import TABLES
from parity.connection import COMMENT, connect, validate_date
from parity.ladder import identifier
from parity.sql import compose, identifier as sql_identifier
from psycopg import sql

SNOWFLAKE_TYPE = re.compile(r'NUMBER\(38,(?:[0-9]|[12][0-9]|3[0-7])\)|NUMBER\(\d{1,2},\d{1,2}\)|DATE|TIMESTAMP_NTZ|VARCHAR(?:\(\d{1,8}\))?')


def snow_type(pg_type):
    if pg_type.startswith('numeric'):
        return pg_type.replace('numeric', 'NUMBER')
    if pg_type in ('bigint', 'integer', 'smallint'):
        return 'NUMBER(38,0)'
    if pg_type == 'date':
        return 'DATE'
    if pg_type.startswith('timestamp'):
        return 'TIMESTAMP_NTZ'
    if pg_type == 'text':
        return 'VARCHAR'
    if re.fullmatch(r'character(?: varying)?\(\d+\)', pg_type):
        return re.sub(r'character(?: varying)?', 'VARCHAR', pg_type)
    raise ValueError(f'Unsupported source type: {pg_type}')


def column_ddl(columns):
    """Column list for CREATE TABLE: validated identifiers and allow-listed types only."""
    for _, kind in columns:
        if not SNOWFLAKE_TYPE.fullmatch(kind):
            raise ValueError(f'Unsupported column type: {kind!r}')
    return ', '.join(identifier(n) + ' ' + t for n, t in columns)


def source_rows(conn, schema, table):
    return conn.execute(compose('SELECT * FROM {}', sql_identifier(schema + '.' + table, 'postgres', preserve_case=True))).fetchall()


def upload(connection, name, columns, rows):
    typed = []
    for index, (column, kind) in enumerate(columns):
        if kind == 'NUMBER':
            scale = max((max(0, -row[index].as_tuple().exponent)
                         for row in rows if isinstance(row[index], Decimal)), default=0)
            kind = f'NUMBER(38,{scale})'
        typed.append((column, kind))
    columns = typed
    target = compose('{}', sql_identifier(_run_render('__RUN_DATABASE__.TD_BASELINE.') + name))
    ddl = column_ddl(columns)
    with connection.cursor() as cursor:
        cursor.execute(compose('CREATE TABLE IDENTIFIER(?) ({}) COMMENT = ?', sql.SQL(ddl)), (target, COMMENT))
        for offset in range(0, len(rows), 2000):
            cursor.executemany(compose('INSERT INTO {} VALUES ({})', sql.SQL(target), sql.SQL(','.join('?' for _ in columns))), rows[offset:offset+2000])
        cursor.execute('SELECT COUNT(*) FROM IDENTIFIER(?)', (target,))
        assert cursor.fetchone()[0] == len(rows)
        cursor.execute('SELECT * FROM IDENTIFIER(?)', (target,))
        assert Counter(rows) == Counter(cursor.fetchall()), f'{name}: source/upload mismatch'
        query_id = cursor.sfqid
    return {'name': name, 'rows': len(rows), 'source_equals_uploaded': True, 'query_id': query_id}


def capture(output, business_date):
    business_date = validate_date(business_date)
    evidence = []
    with Runner(output=io.StringIO()) as td, connect('baseline_capture', 'LOAD') as sf:
        with sf.cursor() as cursor:
            cursor.execute(_run_render('CREATE SCHEMA IF NOT EXISTS __RUN_DATABASE__.TD_BASELINE COMMENT = ?'), (COMMENT,))
        names = [t.name for t in TABLES if t.area == 'billing']
        names += ['STG_' + n for n in names]
        names += ['V_ACCOUNT_INVOICES', 'V_SUBSCRIPTION_PLANS', 'V_INVOICE_BASE', 'V_INVOICE_REVENUE']
        for name in names:
            source = 'sfx_billing.' + name.lower()
            columns = td.columns(source)
            rows = source_rows(td.conn, 'sfx_billing', name.lower())
            evidence.append(upload(sf, name, [(n, snow_type(t)) for n, t in columns], rows))
            print(name, len(rows), flush=True)
        source = 'sfx_documents.storage_usage_daily'
        rows = source_rows(td.conn, 'sfx_documents', 'storage_usage_daily')
        evidence.append(upload(sf, 'STORAGE_USAGE_INPUT',
                               [(n, snow_type(t)) for n, t in td.columns(source)], rows))
        for name, query in [('M_SUBSCRIPTION_PLANS', 'EXEC SFX_BILLING.M_SUBSCRIPTION_PLANS(?)'),
                            ('M_CURRENCY_TOTALS', 'EXEC SFX_BILLING.M_CURRENCY_TOTALS(?)')]:
            td.execute(query, (business_date,))
            assert td.errorcode == 0, td.output.getvalue()
            types = ['NUMBER(38,0)', 'NUMBER(38,0)', 'VARCHAR(10)', 'NUMBER(14,2)'] if 'SUBSCRIPTION' in name else ['VARCHAR(3)', 'NUMBER(38,0)', 'NUMBER(38,2)']
            evidence.append(upload(sf, name, list(zip(td.headers, types)), td.rows))
    output.write_text(json.dumps(evidence, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--business-date', default='20261109')
    args = parser.parse_args()
    capture(args.output, args.business_date)
