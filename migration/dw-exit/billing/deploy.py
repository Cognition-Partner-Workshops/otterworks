
import sys as _run_sys
from pathlib import Path as _RunPath
_run_sys.path.insert(0, str(_RunPath(__file__).resolve().parents[3]))
from warehouse.run_config import render as _run_render

import argparse
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'warehouse/teradata'), str(Path(__file__).resolve().parents[1])]
from snowflake.connector.util_text import split_statements
from parity.connection import COMMENT, connect, validate_date
from parity.ladder import identifier

SQL = Path(__file__).resolve().parent
MACRO_CALLS = {
    'M_SUBSCRIPTION_PLANS': _run_render('CALL __RUN_DATABASE__.BILLING.M_SUBSCRIPTION_PLANS(?)'),
    'M_CURRENCY_TOTALS': _run_render('CALL __RUN_DATABASE__.BILLING.M_CURRENCY_TOTALS(?)'),
}


def commands(text):
    return [statement for statement, _ in split_statements(io.StringIO(text))]


def run(business_date, output, initial=False):
    business_date = validate_date(business_date)
    evidence = []
    with connect('billing_initial_load' if initial else 'billing_fixed_load', 'TRANSFORM') as connection:
        with connection.cursor() as cursor:
            cursor.execute(_run_render('CREATE SCHEMA IF NOT EXISTS __RUN_DATABASE__.BILLING COMMENT = ?'), (COMMENT,))
            # An alternate display format exposes unresolved Teradata FORMAT casts.
            cursor.execute("ALTER SESSION SET DATE_OUTPUT_FORMAT = 'DD/MM/YYYY'")
            for path in sorted(SQL.glob('[0-3][0-9]_*.sql')):
                if initial and path.name in ('15_storage.sql', '35_reports.sql'):
                    continue
                candidate = SQL / 'initial' / path.name if initial and path.name != '00_tables.sql' else path
                for statement in commands(_run_render(candidate.read_text()).replace('${BUSINESS_DATE}', business_date)):
                    cursor.execute(statement)
                    evidence.append({'file': path.name, 'query_id': cursor.sfqid})
                print(path.name, 'deployed', flush=True)
                if path.name == '00_tables.sql':
                    cursor.execute(_run_render("SHOW TABLES LIKE 'STG_%' IN SCHEMA __RUN_DATABASE__.BILLING"))
                    tables = [row[1] for row in cursor.fetchall()]
                    for name in tables:
                        cursor.execute('INSERT INTO IDENTIFIER(?) SELECT * FROM IDENTIFIER(?)',
                                       (_run_render('__RUN_DATABASE__.BILLING.') + identifier(name),
                                        _run_render('__RUN_DATABASE__.TD_BASELINE.') + identifier(name)))
                    if not initial:
                        cursor.execute(_run_render('CREATE OR REPLACE TABLE __RUN_DATABASE__.BILLING.STORAGE_USAGE_INPUT '
                                       'CLONE __RUN_DATABASE__.TD_BASELINE.STORAGE_USAGE_INPUT COMMENT = ?'), (COMMENT,))
            cursor.execute('BEGIN')
            try:
                cursor.execute(_run_render("CALL __RUN_DATABASE__.BILLING.P_MONTHLY_INVOICE(?)"), (business_date,))
                evidence.append({'procedure_rows_updated': cursor.fetchone()[0], 'query_id': cursor.sfqid})
                close = SQL / 'initial/40_close.sql' if initial else SQL / '40_close.sql'
                for statement in commands(_run_render(close.read_text()).replace('${BUSINESS_DATE}', business_date)):
                    cursor.execute(statement)
                    evidence.append({'file': '40_close.sql', 'query_id': cursor.sfqid})
                cursor.execute('COMMIT')
            except Exception:
                cursor.execute('ROLLBACK')
                raise
            for macro, call in MACRO_CALLS.items():
                cursor.execute(call, (business_date,))
                result_query = cursor.sfqid
                cursor.execute('CREATE OR REPLACE TABLE IDENTIFIER(?) COMMENT = ? AS SELECT * FROM TABLE(RESULT_SCAN(?))',
                               (_run_render(f'__RUN_DATABASE__.BILLING.{macro}_OUTPUT'), COMMENT, result_query))
                evidence.append({'macro': macro, 'result_query_id': result_query, 'query_id': cursor.sfqid})
    output.write_text(json.dumps(evidence, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--business-date', default='20261109')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--initial', action='store_true')
    args = parser.parse_args()
    run(args.business_date, args.output, args.initial)
