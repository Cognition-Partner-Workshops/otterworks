import argparse
import os
import tempfile
from pathlib import Path

from pyspark.sql import functions as F

from lakehouse.runtime.ingest import business_date
from lakehouse.runtime.layout import data_root
from lakehouse.runtime.session import create_session


REPORTS = {
    'subscription_plans': ('subscription_plans', ('subscription_id', 'customer_id', 'plan_code', 'monthly_fee')),
    'currency_daily': ('currency_daily', ('currency_cd', 'invoice_count', 'total_amount')),
    'invoice_monthly': ('currency_totals', ('currency_cd', 'invoice_count', 'total_amount')),
    'gl_trial_balance': ('gl_trial_balance', ('account_number', 'account_name', 'debit_amount', 'credit_amount')),
    'invoice_periods': ('invoice_periods', ('invoice_id', 'prior_dt', 'month_no', 'period_key', 'invoice_period', 'run_dt')),
    'period_close': ('period_close', ('currency_cd', 'invoice_count', 'total_amount')),
    'account_status': ('account_status', ('business_dt', 'status_cd', 'currency_cd', 'account_count')),
}


def publish(rows, columns, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='',
                                         dir=path.parent, prefix='.' + path.name, delete=False) as handle:
            temporary = Path(handle.name)
            for row in rows:
                values = ['' if row[name] is None else str(row[name]) for name in columns]
                if any(any(char in value for char in '|\r\n') for value in values):
                    raise ValueError('Report fields cannot contain pipes or newlines')
                handle.write('|'.join(values) + '\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def export(spark, day, names, destination):
    business_date(day)
    for name in names:
        model, columns = REPORTS[name]
        frame = spark.table('gold_billing.' + model).select(*columns)
        ordering = [(F.lower(F.rtrim(frame[c])) if c in ('status_cd', 'currency_cd', 'account_number') else frame[c])
                    .asc_nulls_last() for c in columns]
        rows = frame.orderBy(*ordering).toLocalIterator()
        filename = f'account_status_{day}' if name == 'account_status' else name
        path = destination / (filename + '.psv')
        publish(rows, columns, path)
        print(f'{name}: published {path}', flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--business-date', required=True)
    parser.add_argument('--reports', nargs='+', choices=REPORTS, default=list(REPORTS))
    args = parser.parse_args()
    business_date(args.business_date)
    spark = create_session()
    try:
        export(spark, args.business_date, args.reports,
               data_root() / 'exports/billing' / args.business_date)
    finally:
        spark.stop()


if __name__ == '__main__':
    main()
