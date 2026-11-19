"""Independent Spark-feed transformations and atomic, retry-safe publications."""

import argparse
import fcntl
import json
import math
import os
import uuid
from pathlib import Path

from pyspark.sql import functions as F
from pyspark.sql.types import DateType, DecimalType, LongType, StringType, StructField, StructType, TimestampType

from lakehouse.runtime.layout import data_root
from lakehouse.runtime.session import create_session

from .spark_inputs import JDBC, JOBS, SCHEMAS, atomic_json, digest, directory, verify


def schema(table):
    types = {'BIGINT': LongType(), 'TEXT': StringType(), 'DATE': DateType(), 'TIMESTAMP': TimestampType()}
    fields = []
    for name, kind in SCHEMAS[table]:
        datatype = types.get(kind)
        if datatype is None:
            datatype = DecimalType(*map(int, kind[8:-1].split(',')))
        fields.append(StructField(name.lower(), datatype, True))
    return StructType(fields)


def inputs(spark, root, table):
    return (spark.read.schema(schema(table)).option('header', True).option('sep', '|')
            .option('escape', '"').csv(str(root / 'billing' / table / '*.psv')))


def churn_probability(status, customer):
    linear = -1.8 + 0.04 * (customer % 50) + (1.2 if status == 'closed' else 0.0)
    return 1.0 / (1.0 + math.exp(-linear))


def transform(job, read):
    if job == 'billing_churn_score':
        return read('SUBSCRIPTION').withColumn('churn_score', F.udf(churn_probability, 'double')('status', 'customer_id'))
    if job == 'billing_usage_append_daily':
        usage = read('USAGE_DAILY')
        return usage.join(usage.agg(F.max('usage_date').alias('_max')), usage.usage_date == F.col('_max')).drop('_max')
    if job == 'billing_invoice_summary_daily':
        return (read('INVOICE_HDR').alias('h').join(read('INVOICE_LINE').alias('l'), 'invoice_id')
                .groupBy('h.customer_id', 'h.invoice_date')
                .agg(F.count(F.lit(1)).alias('line_count'), F.sum('l.amount').alias('amount')))
    if job == 'billing_revenue_by_plan':
        return (read('PLAN_CATALOG').join(read('INVOICE_LINE'), 'plan_id').groupBy('plan_id', 'plan_name')
                .agg(F.sum('amount').alias('revenue')))
    if job == 'billing_payment_aging':
        return (read('INVOICE_HDR').alias('h').join(read('PAYMENT').alias('p'), 'invoice_id', 'left')
                .select('h.customer_id', 'invoice_id', F.datediff('p.payment_date', 'h.due_date').alias('days_late'),
                        'h.total_amount', F.col('p.amount').alias('paid_amount')))
    if job != 'billing_gl_trial_balance':
        raise ValueError('Unknown billing Spark job: ' + job)
    keys = ['gl_account_id', 'period', 'currency_code']
    ledger = (read('GL_JOURNAL_LINE').withColumn('period', F.date_format('posting_date', 'yyyy-MM'))
              .groupBy(*keys).agg(F.sum('debit_amt').alias('debits'), F.sum('credit_amt').alias('credits'),
                                  F.sum(F.col('debit_amt') - F.col('credit_amt')).alias('net')))
    credits = (read('CREDIT_NOTE').withColumn('period', F.date_format('posting_date', 'yyyy-MM'))
               .groupBy(*keys).agg(F.sum('amount').alias('credit_note_adjustments')))
    periods = ledger.select(*keys).union(credits.select(*keys)).distinct()
    return (periods.join(read('GL_ACCOUNT'), 'gl_account_id').join(ledger, keys, 'left').join(credits, keys, 'left')
            .select('gl_account_id', 'account_code', 'account_name', 'account_type', 'period', 'currency_code',
                    *[F.coalesce(F.col(c), F.lit(0)).alias(c) for c in
                      ('debits', 'credits', 'net', 'credit_note_adjustments')]))


def register_view(spark, job, surface, path, legacy=False):
    if job not in JOBS or surface not in ('parquet', 'jdbc'):
        raise ValueError('Invalid billing Spark output')
    name = ('legacy_' if legacy else '') + job + '_' + surface
    format = 'delta' if surface == 'jdbc' else 'parquet'
    frame = spark.read.format(format).load(str(path))
    names = [c.lower() for c in frame.columns]
    columns = ', '.join('`' + c + '`' for c in names)
    order = ', '.join('`' + c + '` ASC NULLS FIRST' for c in names)
    location = str(path.resolve()).replace('`', '``')
    spark.sql(f'CREATE OR REPLACE VIEW gold_billing.{name} AS SELECT {columns}, '
              f'row_number() OVER (ORDER BY {order}) AS parity_row FROM {format}.`{location}`')


def publish(spark, job, day, signature, frame, validate, root=None):
    if job not in JOBS:
        raise ValueError('Unknown billing Spark job')
    root = (root or data_root() / 'billing_spark') / job
    current = root / 'current'
    deliveries = json.loads((current / 'manifest.json').read_text())['deliveries'] if current.exists() else {}
    if day in deliveries:
        if deliveries[day] != signature and job == 'billing_usage_append_daily':
            raise ValueError('Changed completed billing Spark delivery requires explicit recovery')
        if deliveries[day] == signature:
            validate()
            return current
    if job == 'billing_usage_append_daily' and current.exists():
        frame = spark.read.parquet(str(current / 'parquet')).unionByName(frame)
    version = root / 'versions' / uuid.uuid4().hex
    frame.write.mode('error').parquet(str(version / 'parquet'))
    if job in JDBC:
        spark.read.parquet(str(version / 'parquet')).write.format('delta').save(str(version / 'jdbc'))
    validate()
    completed = {**deliveries, day: signature} if job == 'billing_usage_append_daily' else {day: signature}
    atomic_json(version / 'manifest.json', dict(deliveries=completed))
    link = root / 'next'
    link.unlink(missing_ok=True)
    link.symlink_to(version.relative_to(root), target_is_directory=True)
    os.replace(link, current)
    return current


def run(spark, landing, day, jobs):
    signature = verify(landing, day)
    root = directory(landing, day)
    for job in jobs:
        if job not in JOBS:
            raise ValueError('Unknown billing Spark job')
        code_signature = signature + ':' + digest(__file__)
        result = transform(job, lambda table: inputs(spark, root, table))
        current = publish(spark, job, day, code_signature, result,
                          lambda: verify_unchanged(landing, day, signature))
        for surface in ('parquet', 'jdbc') if job in JDBC else ('parquet',):
            register_view(spark, job, surface, current / surface)
        print(job + ': PUBLISHED', flush=True)


def verify_unchanged(landing, day, expected):
    if verify(landing, day) != expected:
        raise ValueError('Billing Spark delivery changed during execution')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--landing', type=Path, required=True)
    parser.add_argument('--business-date', required=True)
    parser.add_argument('--jobs', choices=JOBS, nargs='+', default=list(JOBS))
    args = parser.parse_args()
    root = data_root()
    root.mkdir(parents=True, exist_ok=True)
    with (root / 'billing-spark.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        spark = create_session()
        spark.conf.set('spark.sql.ansi.enabled', 'false')
        try:
            run(spark, args.landing, args.business_date, args.jobs)
        finally:
            spark.stop()


if __name__ == '__main__':
    main()
