"""Capture and materialize the BTEQ exports using their actual SELECT statements."""
import argparse
import datetime as dt
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from capture import ROOT, Runner, upload
from bteq.parser import commands
from parity.connection import COMMENT, connect, validate_date


def source_queries(business_date):
    business_date = validate_date(business_date)
    day = dt.datetime.strptime(business_date, '%Y%m%d').date()
    end = day.replace(day=1) - dt.timedelta(days=1)
    start = end.replace(day=1)
    encoded = lambda d: (d.year-1900)*10000+d.month*100+d.day
    text = (ROOT / 'warehouse/teradata/scripts/billing/13_period_close.bteq').read_text()
    for name, value in {'BUSINESS_DATE': business_date, 'PERIOD_START_INT': encoded(start),
                        'PERIOD_END_INT': encoded(end)}.items():
        text = text.replace('${' + name + '}', str(value))
    return [s for s in commands(text) if s.startswith('SELECT')]


def converted_queries(business_date):
    day = f"TO_DATE('{validate_date(business_date)}','YYYYMMDD')"
    return {
        'INVOICE_PERIODS': f"SELECT INVOICE_ID, PRIOR_PERIOD_END_DT AS PRIOR_DT, INVOICE_MONTH AS MONTH_NO, PERIOD_KEY, INVOICE_PERIOD, {day} AS RUN_DT FROM SFX_D1110_AFTER.BILLING.INVOICE_HDR",
        'PERIOD_CLOSE': f"SELECT MIN(RTRIM(CURRENCY_CD)) AS CURRENCY_CD, COUNT(*) AS INVOICE_COUNT, SUM(TOTAL_AMOUNT) AS TOTAL_AMOUNT FROM SFX_D1110_AFTER.BILLING.INVOICE_HDR WHERE BILL_DT >= DATEADD(month, -1, DATE_TRUNC(month, {day})) AND BILL_DT < DATE_TRUNC(month, {day}) GROUP BY UPPER(RTRIM(CURRENCY_CD))",
    }


def run(capture, business_date):
    business_date = validate_date(business_date)
    with connect('capture_exports' if capture else 'converted_exports') as sf:
        if capture:
            with Runner(output=io.StringIO()) as td:
                types = [['NUMBER(38,0)', 'DATE', 'NUMBER(38,0)', 'NUMBER(38,0)', 'VARCHAR(7)', 'DATE'],
                         ['VARCHAR(3)', 'NUMBER(38,0)', 'NUMBER(38,2)']]
                for name, query, kinds in zip(('INVOICE_PERIODS', 'PERIOD_CLOSE'), source_queries(business_date), types):
                    td.execute(query)
                    assert td.errorcode == 0, td.output.getvalue()
                    upload(sf, name, list(zip(td.headers, kinds)), td.rows)
        else:
            queries = converted_queries(business_date)
            with sf.cursor() as cursor:
                for name, query in queries.items():
                    cursor.execute(f"CREATE OR REPLACE TABLE SFX_D1110_AFTER.BILLING.{name} COMMENT = '{COMMENT}' AS {query}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--capture', action='store_true')
    parser.add_argument('--business-date', default='20261109')
    args = parser.parse_args()
    run(args.capture, args.business_date)
