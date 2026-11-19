"""Run the unchanged report against isolated PostgreSQL and local S3 fixtures."""

import argparse
import configparser
import gzip
import json
import runpy
import sys
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from psycopg import ClientCursor

from lakehouse.parity.readers import postgres_connection
from lakehouse.runtime.ingest import business_date
from lakehouse.runtime.layout import ROOT, data_root
from lakehouse.runtime.session import create_session
from lakehouse.runtime.users_activity_report import SUMMARY_COLUMNS, top_user_source


class MissingObject(Exception):
    response = {'Error': {'Code': 'NoSuchKey'}}


def prepare(source, day):
    source.mkdir(parents=True, exist_ok=True)
    days = [(day - timedelta(days=n), *[n + value for value in range(1, 12)])
            for n in (0, 1, 29, 30, 31)]
    for offset, users in {
        0: [('u1', 5, {'edits': 3, 'views': 2}), ('u2', 4, {'edits': 4})],
        1: [('u1', 6, {'views': 6}), ('u3', 4, {'uploads': 4})],
        29: [('u4', 2, {})],
        30: [('outside', 99, {'views': 99})],
    }.items():
        path = top_user_source(day - timedelta(days=offset), source)
        path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(path, 'wt', encoding='utf-8') as handle:
            for uid, total, actions in users:
                handle.write(json.dumps({'user_id': uid, 'total': total, 'actions': actions}) + '\n')
    return days


def legacy(source, day, days):
    destination = data_root() / 'oracle/activity'

    class Bucket:
        def get_object(self, *, Key, **_):
            path = source / Key
            if not path.exists():
                raise MissingObject(Key)
            return {'Body': BytesIO(path.read_bytes())}

        def put_object(self, *, Body, Key, **_):
            path = destination / Key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(Body)

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.combine(day, datetime.min.time(), tzinfo=tz)

    config = configparser.ConfigParser()
    config.read_dict({'aws': {'region': 'test'}, 'database': {
        'host': 'test', 'port': '5432', 'database': 'test', 'user': 'test'},
        's3': {'data_lake_bucket': 'test'}})
    conn = postgres_connection()
    conn.cursor_factory = ClientCursor
    names = ', '.join(f'{column} bigint' for column in SUMMARY_COLUMNS[1:])
    try:
        with conn.cursor() as cursor:
            cursor.execute(f'CREATE TEMP TABLE analytics_daily_summary (report_date date, {names})')
            cursor.executemany('INSERT INTO analytics_daily_summary VALUES (' + ','.join(
                ['%s'] * len(SUMMARY_COLUMNS)) + ')', days)
        modules = {
            'boto3': SimpleNamespace(client=lambda *args, **kwargs: Bucket()),
            'botocore.exceptions': SimpleNamespace(ClientError=MissingObject),
            'bucket_owner': SimpleNamespace(expected_bucket_owner=lambda: 'test'),
            'runtime_config': SimpleNamespace(load_config=lambda: config, required_secret=lambda _: 'test'),
            'psycopg2': SimpleNamespace(connect=lambda **_: conn),
        }
        with patch.dict(sys.modules, modules), patch('datetime.datetime', FrozenDateTime):
            runpy.run_path(str(ROOT.parent / 'etl/scripts/user_activity_daily.py'), run_name='__main__')
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--business-date', required=True)
    parser.add_argument('--source', required=True, type=Path)
    args = parser.parse_args()
    day = business_date(args.business_date)
    days = prepare(args.source, day)
    legacy(args.source, day, days)
    spark = create_session()
    try:
        schema = 'report_date DATE, ' + ', '.join(f'{column} LONG' for column in SUMMARY_COLUMNS[1:])
        spark.createDataFrame(days, schema).write.mode('overwrite').parquet(
            str(args.source / 'daily_summary.parquet'))
    finally:
        spark.stop()


if __name__ == '__main__':
    main()
