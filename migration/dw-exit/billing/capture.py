"""Freeze actual post-chain emulator rows, not a reimplementation of its results."""
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


def upload(connection, name, columns, rows):
    typed = []
    for index, (column, kind) in enumerate(columns):
        if kind == 'NUMBER':
            scale = max((max(0, -row[index].as_tuple().exponent)
                         for row in rows if isinstance(row[index], Decimal)), default=0)
            kind = f'NUMBER(38,{scale})'
        typed.append((column, kind))
    columns = typed
    target = 'SFX_D1110_AFTER.TD_BASELINE.' + identifier(name)
    ddl = ', '.join(identifier(n) + ' ' + t for n, t in columns)
    with connection.cursor() as cursor:
        cursor.execute(f"CREATE TABLE {target} ({ddl}) COMMENT = '{COMMENT}'")
        for offset in range(0, len(rows), 2000):
            cursor.executemany(f"INSERT INTO {target} VALUES ({','.join('?' for _ in columns)})", rows[offset:offset+2000])
        cursor.execute(f'SELECT COUNT(*) FROM {target}')
        assert cursor.fetchone()[0] == len(rows)
        cursor.execute(f'SELECT * FROM {target}')
        assert Counter(rows) == Counter(cursor.fetchall()), f'{name}: source/upload mismatch'
        query_id = cursor.sfqid
    return {'name': name, 'rows': len(rows), 'source_equals_uploaded': True, 'query_id': query_id}


def capture(output, business_date):
    business_date = validate_date(business_date)
    evidence = []
    with Runner(output=io.StringIO()) as td, connect('baseline_capture', 'LOAD') as sf:
        with sf.cursor() as cursor:
            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS SFX_D1110_AFTER.TD_BASELINE COMMENT = '{COMMENT}'")
        names = [t.name for t in TABLES if t.area == 'billing']
        names += ['STG_' + n for n in names]
        names += ['V_ACCOUNT_INVOICES', 'V_SUBSCRIPTION_PLANS', 'V_INVOICE_BASE', 'V_INVOICE_REVENUE']
        for name in names:
            source = 'sfx_billing.' + name.lower()
            columns = td.columns(source)
            rows = td.conn.execute('SELECT * FROM ' + source).fetchall()
            evidence.append(upload(sf, name, [(n, snow_type(t)) for n, t in columns], rows))
            print(name, len(rows), flush=True)
        source = 'sfx_documents.storage_usage_daily'
        rows = td.conn.execute('SELECT * FROM ' + source).fetchall()
        evidence.append(upload(sf, 'STORAGE_USAGE_INPUT',
                               [(n, snow_type(t)) for n, t in td.columns(source)], rows))
        for name, routine in [('M_SUBSCRIPTION_PLANS', 'M_SUBSCRIPTION_PLANS'), ('M_CURRENCY_TOTALS', 'M_CURRENCY_TOTALS')]:
            td.execute(f"EXEC SFX_BILLING.{routine}('{business_date}')")
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
