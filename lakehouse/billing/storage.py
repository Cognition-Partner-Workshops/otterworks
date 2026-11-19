import argparse

from lakehouse.billing.reports import publish
from lakehouse.runtime.ingest import business_date
from lakehouse.runtime.layout import data_root
from lakehouse.runtime.session import create_session


def export(spark, day, destination):
    business_date(day)
    columns = ('customer_id', 'bytes_used', 'object_count')
    rows = spark.table('gold_documents.m_storage_totals').select(*columns).orderBy(
        'customer_id').toLocalIterator()
    publish(rows, columns, destination)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--business-date', required=True)
    args = parser.parse_args()
    business_date(args.business_date)
    spark = create_session()
    try:
        export(spark, args.business_date,
               data_root() / 'exports/billing' / args.business_date / 'storage_monthly.psv')
    finally:
        spark.stop()


if __name__ == '__main__':
    main()
