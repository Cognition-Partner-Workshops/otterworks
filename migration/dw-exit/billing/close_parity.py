"""Strict local Postgres/export versus DuckDB billing close parity."""
import argparse
from collections import Counter, defaultdict
import csv
import datetime as dt
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import sys
import zlib

import duckdb
import psycopg
from psycopg import sql

sys.path.insert(0, str(Path(__file__).resolve().parent))
from duckdb_close import export_queries


def value(v, trim=True):
    if v is None:
        return None
    text = str(v)
    if isinstance(v, str):
        return text.rstrip(' ') if trim else text
    try:
        number = Decimal(text)
        if number.is_finite():
            return format(number.normalize(), 'f')
    except InvalidOperation:
        pass
    return text


def compare(columns, before, after):
    numeric = {i for i, c in enumerate(columns) if c.endswith(('_ID', '_AMOUNT', '_COUNT', '_FEE', '_PRICE', '_TOTAL'))
               or c in ('MONTH_NO', 'PERIOD_KEY', 'LINE_NO', 'QUANTITY', 'UNITS', 'BYTES_USED', 'INVOICE_MONTH', 'RATE')}
    def normalized(row, trim=True):
        result = []
        for i, v in enumerate(row):
            if i in numeric and v is not None and str(v) != '':
                v = Decimal(str(v))
            elif trim and v is not None and columns[i].endswith(('_DT', '_TS', '_DATE', '_TIMESTAMP')):
                text = str(v).rstrip(' ')
                try:
                    v = dt.datetime.fromisoformat(text).isoformat() if 'T' in text or ' ' in text else dt.date.fromisoformat(text).isoformat()
                except ValueError:
                    pass
            result.append(value(v, trim=trim))
        return result
    def hashes(rows, trim=True):
        return Counter((normalized(row, trim)[0], hashlib.sha256(json.dumps(normalized(row, trim),
                        ensure_ascii=False).encode()).hexdigest()) for row in rows)
    bh, ah = hashes(before), hashes(after)
    delta = (bh-ah) + (ah-bh)
    raw_before, raw_after = hashes(before, False), hashes(after, False)
    raw_delta = (raw_before-raw_after) + (raw_after-raw_before)
    money = [i for i, c in enumerate(columns) if c.endswith(('AMOUNT', 'MONTHLY_FEE', 'UNIT_PRICE', 'CONTROL_TOTAL'))]
    groups = [i for i, c in enumerate(columns) if c in ('CURRENCY_CD', 'GL_ACCOUNT_ID', 'ACCOUNT_NUMBER')]
    def totals(rows):
        result = defaultdict(lambda: defaultdict(Decimal))
        for row in rows:
            key = json.dumps([value(row[i]) for i in groups])
            for i in money:
                if row[i] is not None and str(row[i]) != '':
                    result[key][columns[i]] += Decimal(str(row[i]))
        return {k: {c: value(v) for c, v in sorted(t.items())} for k, t in sorted(result.items())}
    bt, at = totals(before), totals(after)
    keys = sorted({str(k) for k, h in delta})[:5]
    samples = {key: {'before': [normalized(r) for r in before if str(normalized(r)[0]) == key][:3],
                     'after': [normalized(r) for r in after if str(normalized(r)[0]) == key][:3]} for key in keys}
    return {'before_rows': len(before), 'after_rows': len(after), 'hash_differences': sum(delta.values()),
            'strict_hash_differences': sum(raw_delta.values()),
            'key_columns': columns[:1], 'money_groups': [columns[i] for i in groups],
            'money_before': bt, 'money_after': at, 'money_equal': bt == at,
            'sample_differing_keys': keys, 'samples': samples,
            'passed': not delta and bt == at}


def markdown(results):
    lines = ['| Relation | Legacy rows | DuckDB rows | Hash differences | Strict differences | Money sums | Result |',
             '|---|---:|---:|---:|---:|---|---|']
    for name, r in results.items():
        lines.append(f"| {name} | {r['before_rows']} | {r['after_rows']} | {r['hash_differences']} | {r['strict_hash_differences']} | {'equal' if r['money_equal'] else 'DIFFER'} | {'PASS' if r['passed'] else 'FAIL'} |")
    return '\n'.join(lines) + '\n'


def run(database, legacy_exports, output, business_date):
    results = {}
    ns = os.environ.get('NS', 'sfg1120-before')
    port = os.environ.get('TD_PG_PORT', str(54500 + zlib.crc32(ns.encode()) % 1000))
    with duckdb.connect(str(database), read_only=True) as target, psycopg.connect(
            host=os.environ.get('TD_PG_HOST', '127.0.0.1'), port=port,
            dbname=os.environ.get('TD_PG_DB', 'teradata'), user=os.environ.get('TD_PG_USER', 'postgres'),
            password=os.environ.get('TD_PG_PASSWORD', '')) as source:
        tables = target.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='BILLING' AND table_type='BASE TABLE' ORDER BY table_name").fetchall()
        for (table,) in tables:
            if table == 'STORAGE_USAGE_INPUT':
                schema, source_table = 'sfx_documents', 'storage_usage_daily'
            else:
                schema, source_table = 'sfx_billing', table.lower()
            cur = target.execute('SELECT * FROM BILLING."' + table + '"')
            columns = [c[0].upper() for c in cur.description]
            after = cur.fetchall()
            before = source.execute(sql.SQL('SELECT {} FROM {}.{}').format(
                sql.SQL(',').join(sql.Identifier(c.lower()) for c in columns),
                sql.Identifier(schema), sql.Identifier(source_table))).fetchall()
            results[table] = compare(columns, before, after)
        for name, query in export_queries(business_date).items():
            cur = target.execute(query)
            columns = [c[0].upper() for c in cur.description]
            after = cur.fetchall()
            with (legacy_exports / (name + '.psv')).open(newline='', encoding='utf-8') as handle:
                before = list(csv.reader(handle, delimiter='|'))
            results[name + '.psv'] = compare(columns, before, after)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'parity.json').write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
    report = markdown(results)
    (output / 'parity.md').write_text(report, encoding='utf-8')
    print(report, end='')
    return 0 if all(r['passed'] for r in results.values()) else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--legacy-exports', type=Path, default=Path('warehouse/exports'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--business-date', default='20261109')
    args = parser.parse_args()
    return run(args.database, args.legacy_exports, args.output, args.business_date)


if __name__ == '__main__':
    sys.exit(main())
