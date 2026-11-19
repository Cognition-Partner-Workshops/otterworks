"""Invoke unchanged legacy PySpark scripts against an isolated feed/JDBC estate."""

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from psycopg import sql
import pyspark

from lakehouse.parity.readers import postgres_connection
from lakehouse.runtime.layout import ROOT, data_root
from lakehouse.runtime.session import create_session

from .spark import register_view
from .spark_inputs import JDBC, JOBS, SCHEMAS, TABLES, atomic_json, digest, directory, prepare, verify


def database():
    return 'billing_spark_' + os.environ['NS']


def driver_path():
    namespace = os.environ.get('LEGACY_NS', 'sfx-d1110-before')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', namespace):
        raise ValueError('Invalid legacy namespace')
    cache = (ROOT.parent / 'etl/spark/.cache').resolve()
    path = (cache / namespace / 'jars/postgresql-42.7.4.jar').resolve()
    if not path.is_relative_to(cache):
        raise ValueError('JDBC driver must stay inside the repository cache')
    if not path.is_file():
        raise FileNotFoundError('Run etl/spark/fixture/fetch_jars.sh with the legacy NS first')
    return path


def bootstrap(landing, day):
    """Load fixed schemas with psycopg Identifier composition, not raw SQL strings."""
    root = directory(landing, day)
    with postgres_connection('postgres') as admin:
        admin.autocommit = True
        if not admin.execute('SELECT 1 FROM pg_database WHERE datname=%s', (database(),)).fetchone():
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(database())))
    with postgres_connection(database()) as connection:
        connection.execute('CREATE SCHEMA IF NOT EXISTS sfx_billing')
        for table in TABLES:
            name = sql.Identifier('sfx_billing', table.lower())
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            connection.execute(sql.SQL('DROP TABLE IF EXISTS {}').format(name))
            columns = sql.SQL(', ').join(sql.SQL('{} {}').format(sql.Identifier(n.lower()), sql.SQL(t))
                                         for n, t in SCHEMAS[table])
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            connection.execute(sql.SQL('CREATE TABLE {} ({})').format(name, columns))
            with connection.cursor().copy(sql.SQL('COPY {} FROM STDIN').format(name)) as copy:
                for path in sorted((root / 'billing' / table).glob('*.psv')):
                    with path.open(newline='') as handle:
                        reader = csv.reader(handle, delimiter='|')
                        next(reader)
                        for row in reader:
                            copy.write_row([None if value == '' else value for value in row])
        for table in JDBC.values():
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            connection.execute(sql.SQL('DROP TABLE IF EXISTS {}').format(sql.Identifier('sfx_billing', table)))


def run(landing, day, jobs=JOBS, reset=True):
    signature = prepare(landing, day)
    root = data_root() / 'billing_spark_legacy' / day
    if reset:
        bootstrap(landing, day)
        if root.exists():
            shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    with postgres_connection(database()) as connection:
        host, port, user, password = (connection.info.host, connection.info.port,
                                      connection.info.user, connection.info.password or '')
    jar = driver_path()
    environment = {k: v for k, v in os.environ.items() if not k.startswith('AWS_')}
    environment.update(LANDING_DIR=str(directory(landing, day)), LAKE_DIR=str(root),
                       PYTHONPATH=str(ROOT.parent / 'etl/spark/jobs/py') + ':' + str(ROOT.parent),
                       SPARK_LOCAL_IP='127.0.0.1', TD_JDBC_URL=f'jdbc:postgresql://{host}:{port}/{database()}',
                       TD_JDBC_USER=user, TD_JDBC_PASSWORD=password)
    sources = ['etl/spark/jobs/py/common/runtime.py', 'etl/spark/jobs/py/common/schemas.py']
    for job in jobs:
        if job not in JOBS:
            raise ValueError('Unknown billing Spark job')
        source = 'etl/spark/jobs/py/' + job + '.py'
        sources.extend([source, 'etl/spark/submit/' + job + '.sh'])
        command = [str(Path(pyspark.__file__).parent / 'bin/spark-submit'), '--master', 'local[2]',
                   '--driver-memory', '768m', '--conf', 'spark.ui.enabled=false',
                   '--conf', 'spark.sql.shuffle.partitions=2', '--conf', 'spark.sql.session.timeZone=UTC',
                   '--jars', str(jar), str(ROOT.parent / source)]
        with (root / (job + '.log')).open('w') as log:
            # Fixed repository script allowlist, validated cache path and argv-only execution.
            # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-tainted-env-args.dangerous-subprocess-use-tainted-env-args
            subprocess.run(command, env=environment, cwd=ROOT.parent, stdout=log, shell=False,
                           stderr=subprocess.STDOUT, check=True)
        if verify(landing, day) != signature:
            raise ValueError('Shared billing Spark fixture changed during legacy execution')
        print('legacy.' + job + ': SUCCEEDED', flush=True)
    atomic_json(root / 'provenance.json', dict(business_date=day, input_signature=signature,
                sources={name: digest(ROOT.parent / name) for name in sources}, spark=pyspark.__version__,
                jdbc_driver_hash=digest(jar), runner_hash=digest(__file__),
                execution='Unchanged PySpark scripts; isolated PostgreSQL; local[2], UTC, two shuffle partitions'))
    spark = create_session()
    try:
        for job in jobs:
            register_view(spark, job, 'parquet', root / 'billing' / job, legacy=True)
    finally:
        spark.stop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--landing', type=Path, required=True)
    parser.add_argument('--business-date', required=True)
    parser.add_argument('--jobs', nargs='+', choices=JOBS, default=list(JOBS))
    parser.add_argument('--append-existing', action='store_true')
    args = parser.parse_args()
    run(args.landing, args.business_date, args.jobs, reset=not args.append_existing)


if __name__ == '__main__':
    main()
