import argparse
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'warehouse/teradata'), str(Path(__file__).resolve().parents[1])]
from snowflake.connector.util_text import split_statements
from parity.connection import COMMENT, connect, validate_date

SQL = Path(__file__).resolve().parent


def commands(text):
    return [statement for statement, _ in split_statements(io.StringIO(text))]


def run(business_date, output, initial=False):
    business_date = validate_date(business_date)
    evidence = []
    with connect('billing_initial_load' if initial else 'billing_fixed_load', 'TRANSFORM') as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS SFX_D1110_AFTER.BILLING COMMENT = '{COMMENT}'")
            # An alternate display format exposes unresolved Teradata FORMAT casts.
            cursor.execute("ALTER SESSION SET DATE_OUTPUT_FORMAT = 'DD/MM/YYYY'")
            for path in sorted(SQL.glob('[0-3][0-9]_*.sql')):
                if initial and path.name == '15_storage.sql':
                    continue
                candidate = SQL / 'initial' / path.name if initial and path.name != '00_tables.sql' else path
                for statement in commands(candidate.read_text().replace('${BUSINESS_DATE}', business_date)):
                    cursor.execute(statement)
                    evidence.append({'file': path.name, 'query_id': cursor.sfqid})
                print(path.name, 'deployed', flush=True)
                if path.name == '00_tables.sql':
                    cursor.execute("SHOW TABLES LIKE 'STG_%' IN SCHEMA SFX_D1110_AFTER.BILLING")
                    tables = [row[1] for row in cursor.fetchall()]
                    for name in tables:
                        cursor.execute(f'INSERT INTO SFX_D1110_AFTER.BILLING.{name} SELECT * FROM SFX_D1110_AFTER.TD_BASELINE.{name}')
                    if not initial:
                        cursor.execute(f"CREATE OR REPLACE TABLE SFX_D1110_AFTER.BILLING.STORAGE_USAGE_INPUT CLONE SFX_D1110_AFTER.TD_BASELINE.STORAGE_USAGE_INPUT COMMENT = '{COMMENT}'")
            cursor.execute('BEGIN')
            try:
                cursor.execute("CALL SFX_D1110_AFTER.BILLING.P_MONTHLY_INVOICE(?)", (business_date,))
                evidence.append({'procedure_rows_updated': cursor.fetchone()[0], 'query_id': cursor.sfqid})
                close = SQL / 'initial/40_close.sql' if initial else SQL / '40_close.sql'
                for statement in commands(close.read_text().replace('${BUSINESS_DATE}', business_date)):
                    cursor.execute(statement)
                    evidence.append({'file': '40_close.sql', 'query_id': cursor.sfqid})
                cursor.execute('COMMIT')
            except Exception:
                cursor.execute('ROLLBACK')
                raise
            for macro in ('M_SUBSCRIPTION_PLANS', 'M_CURRENCY_TOTALS'):
                cursor.execute(f'CALL SFX_D1110_AFTER.BILLING.{macro}(?)', (business_date,))
                result_query = cursor.sfqid
                cursor.execute(f"CREATE OR REPLACE TABLE SFX_D1110_AFTER.BILLING.{macro}_OUTPUT COMMENT = '{COMMENT}' AS SELECT * FROM TABLE(RESULT_SCAN('{result_query}'))")
                evidence.append({'macro': macro, 'result_query_id': result_query, 'query_id': cursor.sfqid})
    output.write_text(json.dumps(evidence, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--business-date', default='20261109')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--initial', action='store_true')
    args = parser.parse_args()
    run(args.business_date, args.output, args.initial)
