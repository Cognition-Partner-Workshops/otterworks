"""Versioned, headered wildcard-feed contract, separate from warehouse bronze."""

import argparse
import csv
import hashlib
import json
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from etl.spark.jobs.py.common.schemas import SCHEMAS
from lakehouse.runtime.ingest import business_date
from lakehouse.runtime.layout import ROOT, data_root

TABLES = ('PLAN_CATALOG', 'SUBSCRIPTION', 'INVOICE_HDR', 'INVOICE_LINE', 'PAYMENT',
          'GL_ACCOUNT', 'GL_JOURNAL_LINE', 'CREDIT_NOTE', 'USAGE_DAILY')
JOBS = ('billing_invoice_summary_daily', 'billing_revenue_by_plan', 'billing_payment_aging',
        'billing_usage_append_daily', 'billing_gl_trial_balance', 'billing_churn_score')
JDBC = {'billing_invoice_summary_daily': 'spark_invoice_summary',
        'billing_usage_append_daily': 'spark_usage_daily',
        'billing_gl_trial_balance': 'spark_gl_trial_balance'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def directory(landing, day):
    business_date(day)
    return Path(landing).resolve() / 'billing-spark' / day


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temporary.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')
    os.replace(temporary, path)


def verify(landing, day):
    root = directory(landing, day)
    raw = (root / 'manifest.json').read_bytes()
    manifest = json.loads(raw)
    expected = {str(p.relative_to(root)): digest(p) for p in root.glob('billing/*/*.psv')}
    if (manifest.get('version') != 1 or manifest.get('business_date') != day
            or manifest.get('schemas') != {t: [list(c) for c in SCHEMAS[t]] for t in TABLES}
            or expected != manifest.get('files')
            or any(not list((root / 'billing' / t).glob('*.psv')) for t in TABLES)):
        raise ValueError('Billing Spark input contract or wildcard file set changed')
    for name in expected:
        table = Path(name).parent.name
        with (root / name).open(newline='') as handle:
            if next(csv.reader(handle, delimiter='|'), None) != [n for n, _ in SCHEMAS[table]]:
                raise ValueError('Billing Spark header differs: ' + name)
    return hashlib.sha256(raw).hexdigest()


def prepare(landing, day):
    signature = verify(landing, day)
    atomic_json(data_root() / 'billing_spark_inputs' / (day + '.json'),
                dict(business_date=day, signature=signature, root=str(directory(landing, day))))
    return signature


def generate(landing, day):
    root = directory(landing, day)
    current = datetime.strptime(day, '%Y%m%d').date()
    older = current - timedelta(days=1)
    d, p = str(current), str(older)
    rows = {
        'PLAN_CATALOG': [(1, 'Plan|One', '10.00'), (2, None, '0.00'), (3, 'Unused', None)],
        'SUBSCRIPTION': [(1, 1, 1, p, None, 'closed'), (2, 49, 2, d, d, 'Closed'),
                         (3, 50, 1, d, None, None)],
        'INVOICE_HDR': [(1, 7, 'I1', p, d, 'USD', '10.00', 'open'),
                        (2, 8, 'I2', d, p, 'EUR', '-5.00', 'closed'),
                        (3, None, 'I3', d, None, None, '0.00', None),
                        (4, 7, 'I4', d, d, 'USD', '20.00', 'open')],
        'INVOICE_LINE': [(1, 1, 1, 1, '10.00', '10.00'), (2, 1, 1, 1, None, None),
                         (3, 2, 2, 1, '-5.00', '-5.00'), (4, 999, 999, 1, '99.00', '99.00'),
                         (5, 3, 1, 1, '0.00', '0.00')],
        'PAYMENT': [(1, 1, 7, d, '3.00', 'paid'), (2, 1, 7, d, '3.00', 'paid'),
                    (3, 2, 8, None, '5.00', 'paid'), (4, 999, 9, d, '9.00', 'paid')],
        'GL_ACCOUNT': [(1, '1000', 'Cash', 'ASSET'), (2, '2000', None, 'LIABILITY'),
                       (3, '3000', 'Unused', 'EQUITY')],
        'GL_JOURNAL_LINE': [(1, 1, 1, 1, None, '2.00', 'USD', d, 'INV', 7, 1),
                            (2, 1, 2, 1, '10.00', None, 'USD', d, 'INV', 7, 1),
                            (3, 2, 1, 1, '4.00', '1.00', 'EUR', p, 'INV', 8, 2),
                            (4, 3, 1, 2, '3.00', '0.00', None, d, 'INV', None, 3)],
        'CREDIT_NOTE': [(1, 1, 7, 2, d, 'USD', '-3.00', 'credit'),
                        (2, 2, 8, 1, p, 'EUR', None, None),
                        (3, 3, None, 999, d, 'USD', '8.00', 'unknown account')],
        'USAGE_DAILY': [(1, 7, p, 2, '2.00'), (2, 7, d, None, '0.00'),
                        (3, None, d, 4, None)],
    }
    for table, records in rows.items():
        target = root / 'billing' / table
        target.mkdir(parents=True, exist_ok=True)
        for index, date in enumerate((older, current)):
            with (target / (date.strftime('%Y%m%d') + '.psv')).open('w', newline='') as handle:
                writer = csv.writer(handle, delimiter='|', lineterminator='\n')
                writer.writerow([name for name, _ in SCHEMAS[table]])
                writer.writerows(records[index::2])
    manifest = dict(version=1, business_date=day,
                    schemas={t: SCHEMAS[t] for t in TABLES},
                    files={str(p.relative_to(root)): digest(p) for p in root.glob('billing/*/*.psv')},
                    generator_hash=digest(__file__),
                    schema_hash=digest(ROOT.parent / 'etl/spark/jobs/py/common/schemas.py'))
    atomic_json(root / 'manifest.json', manifest)
    return prepare(landing, day)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--landing', type=Path, required=True)
    parser.add_argument('--business-date', required=True)
    parser.add_argument('--generate', action='store_true')
    args = parser.parse_args()
    signature = (generate if args.generate else prepare)(args.landing, args.business_date)
    print('billing.spark.inputs: READY ' + signature)


if __name__ == '__main__':
    main()
