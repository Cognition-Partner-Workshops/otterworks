"""Local-only execution of the checked-in converted billing SQL."""
import argparse
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import sys

import duckdb
from jinja2 import Environment, StrictUndefined
import sqlglot
from sqlglot import exp

ROOT = Path(__file__).resolve().parents[3]
SQL = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from warehouse.seed.columns import TABLES
from warehouse.seed.generate import generate


def business_day(value):
    return dt.datetime.strptime(value, '%Y%m%d').date()


def execute_sql(conn, text, business_date):
    business_day(business_date)
    text = text.replace('__RUN_DATABASE__.', '').replace('${BUSINESS_DATE}', business_date)
    for statement in sqlglot.parse(text, read='snowflake'):
        if statement is None:
            continue
        for table in statement.find_all(exp.Table):
            table.set('catalog', None)
        if isinstance(statement, exp.Create):
            statement.set('properties', None)
        translated = statement.sql(dialect='duckdb', comments=False)
        translated = re.sub(r"TO_DATE\(([^,]+), 'YYYYMMDD'\)", r"CAST(strptime(\1, '%Y%m%d') AS DATE)", translated)
        conn.execute(translated)


def load_landing(conn, landing, business_date):
    for table in TABLES:
        if table.area != 'billing' and table.name != 'STORAGE_USAGE_DAILY':
            continue
        target = 'BILLING.STG_' + table.name
        if table.name == 'STORAGE_USAGE_DAILY':
            target = 'BILLING.STORAGE_USAGE_INPUT'
            conn.execute('CREATE TABLE ' + target + ' (STORAGE_USAGE_ID BIGINT, CUSTOMER_ID BIGINT, '
                         'OWNER_USER_ID BIGINT, USAGE_DT DATE, BYTES_USED BIGINT, OBJECT_COUNT INTEGER)')
        path = landing / table.area / table.name / (business_date + '.psv')
        with path.open(newline='', encoding='utf-8') as handle:
            rows = list(csv.reader(handle, delimiter='|'))
        if any(len(row) != len(table.columns) for row in rows):
            raise ValueError(f'{path}: landing column count differs from seed schema')
        # Match the source loader: empty numeric/date fields are NULL, text stays empty.
        rows = [[None if v == '' and not c.kind.startswith(('V', 'C')) else v
                 for v, c in zip(row, table.columns)] for row in rows]
        if rows:
            conn.executemany('INSERT INTO ' + target + ' VALUES (' + ','.join('?' for _ in table.columns) + ')', rows)
        if table.is_set:
            conn.execute('CREATE OR REPLACE TABLE ' + target + ' AS SELECT DISTINCT * FROM ' + target)


def powercenter_models(conn, landing, business_date):
    """Materialize the existing dbt first-load models, without a dbt service."""
    conn.execute('CREATE SCHEMA PC_BILLING')
    conn.execute('CREATE SCHEMA PC_SRC')
    conn.execute('CREATE TABLE PC_SRC.GL_ACCOUNT AS SELECT GL_ACCOUNT_ID, ACCOUNT_NUMBER AS ACCOUNT_CODE FROM BILLING.STG_GL_ACCOUNT')
    env = Environment(undefined=StrictUndefined)
    names = ['stg_customer_account', 'stg_invoice_hdr', 'customer_account',
             'invoice_hdr', 'invoice_line', 'payment', 'gl_journal_line']
    for name in names:
        text = (ROOT / 'warehouse/dbt/models/pc/billing' / ('pc_billing__' + name + '.sql')).read_text()
        text = env.from_string(text).render(
            config=lambda **kwargs: '', is_incremental=lambda: False,
            ref=lambda value: 'PC_BILLING.' + value.split('__')[1],
            var=lambda key, default=None: business_date if key == 'load_date' else default)
        stage = re.search(r'@__RUN_DATABASE__\.PC_SRC\.LANDING_STAGE/(\w+)/\s*\(.*?\)', text, re.S)
        if stage:
            table = next(t for t in TABLES if t.area == 'billing' and t.name == stage[1])
            path = (landing / 'billing' / table.name / (business_date + '.psv')).resolve().as_posix().replace("'", "''")
            columns = ','.join("'c%d':'VARCHAR'" % (i+1) for i in range(len(table.columns)))
            reader = f"(SELECT *, row_number() OVER () AS SRC_ROW_NO FROM read_csv('{path}', delim='|', header=false, columns={{{columns}}}, nullstr=''))"
            text = text[:stage.start()] + reader + text[stage.end():]
            text = re.sub(r'\$(\d+)', r'c\1', text).replace('METADATA$FILE_ROW_NUMBER', 'SRC_ROW_NO')
        execute_sql(conn, 'CREATE TABLE PC_BILLING.' + name + ' AS ' + text, business_date)
    # Bind the older converted model port names to the current physical target names.
    aliases = {'ACCOUNT_NO': 'ACCOUNT_NUMBER', 'INVOICE_NO': 'INVOICE_NUMBER'}
    for name, key in [('stg_customer_account', 'CUSTOMER_ID'), ('stg_invoice_hdr', 'INVOICE_ID'),
                      ('customer_account', 'CUSTOMER_ID'), ('invoice_hdr', 'INVOICE_ID'),
                      ('invoice_line', 'INVOICE_LINE_ID'), ('payment', 'PAYMENT_ID')]:
        target = 'BILLING.' + name.upper()
        physical = {r[0].upper() for r in conn.execute('DESCRIBE ' + target).fetchall()}
        columns = [r[0].upper() for r in conn.execute('DESCRIBE PC_BILLING.' + name).fetchall()]
        assignments = [aliases.get(c, c) + '=s.' + c for c in columns
                       if c != key and aliases.get(c, c) in physical]
        conn.execute('UPDATE ' + target + ' AS t SET ' + ','.join(assignments)
                     + ' FROM PC_BILLING.' + name + ' s WHERE t.' + key + '=s.' + key)


def export_queries(business_date):
    day = business_day(business_date).isoformat()
    return {
        'invoice_monthly': 'SELECT CURRENCY_CD, COUNT(*) AS INVOICE_COUNT, SUM(TOTAL_AMOUNT) AS TOTAL_AMOUNT FROM BILLING.INVOICE_HDR GROUP BY CURRENCY_CD',
        'gl_trial_balance': "SELECT CAST(a.ACCOUNT_NUMBER AS VARCHAR) AS ACCOUNT_NUMBER, a.ACCOUNT_NAME, COALESCE(SUM(j.DEBIT_AMOUNT),0) AS DEBIT_AMOUNT, COALESCE(SUM(j.CREDIT_AMOUNT),0) AS CREDIT_AMOUNT FROM BILLING.GL_ACCOUNT a LEFT JOIN BILLING.GL_JOURNAL_LINE j USING (GL_ACCOUNT_ID) GROUP BY a.ACCOUNT_NUMBER,a.ACCOUNT_NAME UNION ALL SELECT 'TOTAL','All accounts',COALESCE(SUM(DEBIT_AMOUNT),0),COALESCE(SUM(CREDIT_AMOUNT),0) FROM BILLING.GL_JOURNAL_LINE",
        'period_close': f"SELECT MIN(RTRIM(CURRENCY_CD)) AS CURRENCY_CD, COUNT(*) AS INVOICE_COUNT, SUM(TOTAL_AMOUNT) AS TOTAL_AMOUNT FROM BILLING.INVOICE_HDR WHERE BILL_DT >= date_trunc('month', DATE '{day}') - INTERVAL 1 MONTH AND BILL_DT < date_trunc('month', DATE '{day}') GROUP BY UPPER(RTRIM(CURRENCY_CD))",
        'invoice_periods': f"SELECT INVOICE_ID, PRIOR_PERIOD_END_DT AS PRIOR_DT, INVOICE_MONTH AS MONTH_NO, PERIOD_KEY, INVOICE_PERIOD, DATE '{day}' AS RUN_DT FROM BILLING.INVOICE_HDR",
    }


def write_outputs(conn, output, business_date):
    output.mkdir(parents=True, exist_ok=True)
    queries = export_queries(business_date)
    tables = conn.execute("SELECT table_schema,table_name FROM information_schema.tables WHERE table_type='BASE TABLE' ORDER BY 1,2").fetchall()
    queries.update({schema.lower() + '__' + table.lower(): f'SELECT * FROM "{schema}"."{table}"' for schema, table in tables})
    manifest = {}
    for name, query in queries.items():
        cur = conn.execute(query)
        rows = cur.fetchall()
        columns = [c[0].upper() for c in cur.description]
        with (output / (name + '.psv')).open('w', newline='', encoding='utf-8') as handle:
            csv.writer(handle, delimiter='|', lineterminator='\n').writerows(rows)
        manifest[name] = {'columns': columns, 'rows': len(rows)}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return manifest


def run(landing, business_date, output):
    business_day(business_date)
    output.mkdir(parents=True, exist_ok=True)
    database = output / 'close.duckdb'
    if database.exists():
        database.unlink()
    with duckdb.connect(str(database)) as conn:
        conn.execute('CREATE SCHEMA BILLING')
        execute_sql(conn, (SQL / '00_tables.sql').read_text(), business_date)
        load_landing(conn, landing, business_date)
        execute_sql(conn, (SQL / '10_load.sql').read_text(), business_date)
        powercenter_models(conn, landing, business_date)
        execute_sql(conn, (SQL / '15_storage.sql').read_text(), business_date)
        routines = (SQL / '20_routines.sql').read_text().split('.P_MONTHLY_INVOICE ', 1)[1]
        body = routines.split('run_day :=', 1)[1].split(';', 1)[1].split('RETURN n;', 1)[0]
        body = re.sub(r'\bn := SQLROWCOUNT;', '', body)
        body = body.replace(':run_day', "DATE '" + business_day(business_date).isoformat() + "'")
        execute_sql(conn, body, business_date)
        execute_sql(conn, (SQL / '40_close.sql').read_text(), business_date)
        execute_sql(conn, (SQL / '30_views.sql').read_text(), business_date)
        manifest = write_outputs(conn, output, business_date)
    inputs = {str(path.relative_to(landing)): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in sorted(landing.glob('*/*/' + business_date + '.psv'))}
    (output / 'inputs.json').write_text(json.dumps({'business_date': business_date, 'landing_sha256': inputs}, indent=2) + '\n', encoding='utf-8')
    print(f'Wrote {len(manifest)} relations/exports to {output}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--business-date', default='20261109')
    parser.add_argument('--landing', type=Path)
    parser.add_argument('--rows', type=int, default=2000)
    parser.add_argument('--seed', type=int, default=1110)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    business_day(args.business_date)
    landing = args.landing or args.output / 'landing'
    if args.landing is None:
        generate(args.rows, args.seed, landing, args.business_date)
    run(landing, args.business_date, args.output)


if __name__ == '__main__':
    main()
