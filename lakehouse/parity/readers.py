import csv
import json
import os
from datetime import datetime
from pathlib import Path

import psycopg

from lakehouse.runtime.layout import ROOT
from lakehouse.runtime.session import create_session


def postgres_connection(database=None):
    dsn = os.environ.get('TD_PG_DSN', '')
    defaults = {'host': ('HOST', 'localhost'), 'port': ('PORT', '5432'),
                'dbname': ('DB', 'teradata'), 'user': ('USER', 'postgres'),
                'password': ('PASSWORD', '')}
    options = {
        key: os.environ.get('TD_PG_' + env, default)
        for key, (env, default) in defaults.items()
        if not dsn or 'TD_PG_' + env in os.environ}
    if database is not None:
        options['dbname'] = database
    return psycopg.connect(dsn, **options)


class Readers:
    def __init__(self, business_date):
        self.business_date = business_date
        self.spark = None

    def close(self):
        if self.spark is not None:
            self.spark.stop()

    def read(self, side):
        kind = side['kind']
        if kind in ('json', 'jsonl'):
            path = self.path(side)
            names = side['columns']
            try:
                with path.open(encoding='utf-8') as handle:
                    rows = [json.load(handle)] if kind == 'json' else [json.loads(line) for line in handle if line.strip()]
            except FileNotFoundError:
                if kind == 'jsonl' and side.get('missing_is_empty', False):
                    return [], names
                raise
            if any(not isinstance(row, dict) or not set(names) <= row.keys() for row in rows):
                raise ValueError(f'{path}: JSON objects must contain the configured columns')
            return rows, names
        if kind == 'postgres_sql':
            with postgres_connection(side.get('database')) as conn:
                conn.read_only = True
                with conn.cursor() as cursor:
                    cursor.execute(side['sql'].replace('{business_date}', self.business_date))
                    names = [col.name.lower() for col in cursor.description]
                    self.validate_columns(names)
                    return [dict(zip(names, row)) for row in cursor.fetchall()], names
        if kind == 'file':
            path = self.path(side)
            with path.open(newline='', encoding='utf-8') as handle:
                reader = csv.reader(handle, delimiter=side.get('delimiter', '|'))
                names = side.get('columns')
                if side.get('header', False):
                    header = next(reader, None)
                    if header is None and names is None:
                        raise ValueError('Empty header file requires explicit columns')
                    if names is not None and header is not None and names != header:
                        raise ValueError('File header differs from configured columns')
                    names = names or header
                if not names:
                    raise ValueError('Headerless files require columns')
                names = [name.lower() for name in names]
                self.validate_columns(names)
                rows = []
                for number, row in enumerate(reader, 1):
                    if len(row) != len(names):
                        raise ValueError(f'{path}: row {number} has wrong field count')
                    rows.append(dict(zip(names, row)))
                return rows, names
        if self.spark is None:
            self.spark = create_session()
        if kind == 'spark_sql':
            frame = self.spark.sql(side['sql'].replace('{business_date}', self.business_date))
        elif kind == 'delta_table':
            frame = self.spark.table(side['table']) if 'table' in side else self.spark.read.format('delta').load(str(self.path(side)))
        elif kind == 'parquet':
            frame = self.spark.read.parquet(str(self.path(side)))
        else:
            raise ValueError(f'Unknown reader kind: {kind}')
        names = [name.lower() for name in frame.columns]
        self.validate_columns(names)
        return [dict(zip(names, row)) for row in frame.collect()], names

    def path(self, side):
        path = Path(side['path'].format(business_date=self.business_date,
                                        iso_date=datetime.strptime(self.business_date, '%Y%m%d').date().isoformat(),
                                        NS=os.environ['NS'],
                                        LEGACY_NS=os.environ.get('LEGACY_NS', 'sfx-d1110-before')))
        return path if path.is_absolute() else ROOT.parent / path

    @staticmethod
    def validate_columns(names):
        if len(names) != len(set(names)):
            raise ValueError('Reader column names must be unique (case-insensitive)')
