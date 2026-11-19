import argparse
import csv
from datetime import datetime
from pathlib import Path

from pyspark.sql import functions as F, types as T
from warehouse.seed.columns import TABLES

from .layout import database, delta_path
from .session import create_session


def business_date(value):
    if len(value) != 8 or not value.isascii() or not value.isdigit():
        raise ValueError('business-date must be YYYYMMDD')
    return datetime.strptime(value, '%Y%m%d').date()


def select_tables(names=None):
    wanted = {name.upper() for name in names} if names else {t.name for t in TABLES}
    unknown = wanted - {t.name for t in TABLES}
    if unknown:
        raise ValueError(f'Unknown tables: {sorted(unknown)}')
    return [t for t in TABLES if t.name in wanted]


def ingest(spark, landing, date, names=None):
    day = business_date(date)
    counts = {}
    for table in select_tables(names):
        source = Path(landing).resolve() / table.area / table.name / f'{date}.psv'
        # Python CSV matches the legacy loader, including quoted delimiters/newlines.
        with source.open(newline='', encoding='utf-8') as handle:
            rows = []
            for number, row in enumerate(csv.reader(handle, delimiter='|'), 1):
                if len(row) != len(table.columns):
                    raise ValueError(f'{source}: row {number} has {len(row)} fields; expected {len(table.columns)}')
                rows.append(tuple(None if v == '' and c.kind[0] not in 'VC' else v
                                  for v, c in zip(row, table.columns)))
        schema = T.StructType([T.StructField(c.name.lower(), T.StringType()) for c in table.columns])
        frame = (spark.createDataFrame(rows, schema)
                 .withColumn('_business_date', F.lit(day))
                 .withColumn('_source_file', F.lit(str(source)))
                 .withColumn('_ingested_at', F.current_timestamp()))
        path = delta_path('bronze', table.area, table.name)
        (frame.write.format('delta').mode('overwrite').partitionBy('_business_date')
         .option('replaceWhere', f"_business_date = '{day}'").save(str(path)))
        target = f'{database("bronze", table.area)}.{table.name.lower()}'
        spark.sql(f"CREATE TABLE IF NOT EXISTS {target} USING DELTA LOCATION '{path.as_uri()}'")
        counts[target] = len(rows)
        print(f'{target}: {len(rows)}', flush=True)
    return counts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--landing', type=Path, required=True)
    parser.add_argument('--business-date', required=True)
    parser.add_argument('--tables', nargs='+', help='Table names (space or comma separated)')
    args = parser.parse_args()
    names = [name for group in args.tables for name in group.split(',')] if args.tables else None
    business_date(args.business_date)
    select_tables(names)
    spark = create_session()
    try:
        ingest(spark, args.landing, args.business_date, names)
    finally:
        spark.stop()


if __name__ == '__main__':
    main()
