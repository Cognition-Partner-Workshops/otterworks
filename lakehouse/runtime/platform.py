import argparse
import csv
import os
from pathlib import Path

from .layout import ROOT, database, delta_path


FEEDS = {
    'DBC_QRYLOG': ('qrylog.csv', (
        'ProcID', 'CollectTimeStamp', 'QueryID', 'UserName', 'DefaultDatabase', 'AppID',
        'ClientID', 'StartTime', 'FirstRespTime', 'StatementType', 'StatementGroup',
        'QueryText', 'NumResultRows', 'AMPCPUTime', 'TotalIOCount', 'ErrorCode')),
    'DBC_QRYLOGOBJECTS': ('objectusage.csv', (
        'QueryID', 'ObjectDatabaseName', 'ObjectTableName', 'ObjectType', 'UsageType')),
    'DBC_TABLESV': ('tablesv.csv', (
        'DatabaseName', 'TableName', 'TableKind', 'CreateTimeStamp',
        'LastAccessTimeStamp', 'AccessCount')),
}


def feed_path(table):
    root = Path(os.environ.get('PLATFORM_DBQL_LANDING', ROOT.parent / 'warehouse/teradata/dbql'))
    return root.resolve() / FEEDS[table][0]


def read_feed(path, columns):
    with Path(path).open(newline='', encoding='utf-8') as handle:
        reader = csv.reader(handle, strict=True)
        if next(reader, None) != list(columns):
            raise ValueError(f'{path}: unexpected CSV header')
        rows = []
        for number, row in enumerate(reader, 2):
            if len(row) != len(columns):
                raise ValueError(f'{path}: wrong field count at row {number}')
            rows.append(tuple(row))
    return rows


def ingest(spark, date):
    from pyspark.sql import functions as F, types as T

    from .ingest import business_date

    day = business_date(date)
    feeds = [(name, columns, feed_path(name)) for name, (_, columns) in FEEDS.items()]
    loaded = [(name, columns, path, read_feed(path, columns)) for name, columns, path in feeds]
    counts = {}
    for name, columns, path, rows in loaded:
        schema = T.StructType([T.StructField(c.lower(), T.StringType()) for c in columns])
        frame = (spark.createDataFrame(rows, schema)
                 .withColumn('_business_date', F.lit(day))
                 .withColumn('_source_file', F.lit(str(path)))
                 .withColumn('_ingested_at', F.current_timestamp()))
        location = delta_path('bronze', 'platform', name)
        (frame.write.format('delta').mode('overwrite').partitionBy('_business_date')
         .option('replaceWhere', f"_business_date = '{day}'").save(str(location)))
        target = f'{database("bronze", "platform")}.{name.lower()}'
        spark.sql(f"CREATE TABLE IF NOT EXISTS {target} USING DELTA LOCATION '{location.as_uri()}'")
        counts[target] = len(rows)
        print(f'{target}: {len(rows)}', flush=True)
    return counts


def main():
    from .ingest import business_date
    from .session import create_session

    parser = argparse.ArgumentParser()
    parser.add_argument('--business-date', required=True)
    args = parser.parse_args()
    business_date(args.business_date)
    spark = create_session()
    try:
        ingest(spark, args.business_date)
    finally:
        spark.stop()


if __name__ == '__main__':
    main()
