"""Run only documents sessions in an isolated local emulator database."""

import argparse
import csv
import os
from pathlib import Path

import psycopg
from psycopg import sql

from etl.informatica.runner.repo import Repository
from etl.informatica.runner.workflow import Integration
from lakehouse.runtime.documents_informatica import DOCUMENT, SHARE
from lakehouse.runtime.ingest import business_date
from lakehouse.runtime.layout import ROOT, data_root

from .readers import postgres_connection


def run(landing, day):
    business_date(day)
    root = data_root() / 'legacy_informatica'
    root.mkdir(parents=True, exist_ok=True)
    database = 'lakehouse_documents_infa_' + os.environ['NS']
    with postgres_connection() as source:
        settings = source.info.get_parameters()
        with psycopg.connect(**{**settings, 'dbname': 'postgres'}, autocommit=True) as admin:
            if not admin.execute('SELECT 1 FROM pg_database WHERE datname = %s', (database,)).fetchone():
                # Identifiers are quoted by psycopg, not interpolated as SQL text.
                # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(database)))
        with psycopg.connect(**{**settings, 'dbname': database}) as target:
            target.execute((ROOT.parent / 'etl/informatica/tests/fixture/bootstrap.sql').read_text())
            for table in ('sfx_documents.stg_document', 'sfx_documents.document', 'sfx_documents.doc_share',
                          'sfx_users.app_user', 'sfx_users.role_grant'):
                # Fixed table names are quoted by psycopg.
                # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                target.execute(sql.SQL('TRUNCATE {}').format(sql.Identifier(*table.split('.'))))
                if table.startswith('sfx_users.'):
                    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                    rows = source.execute(sql.SQL('SELECT * FROM {}').format(sql.Identifier(*table.split('.')))).fetchall()
                    with target.cursor().copy(sql.SQL('COPY {} FROM STDIN').format(sql.Identifier(*table.split('.')))) as writer:
                        for row in rows:
                            writer.write_row(row)
    os.environ.update(TD_HOST=settings['host'], TD_PORT=settings['port'], TD_DB=database,
                      TD_USER=settings['user'], LANDING_DIR=str(Path(landing).resolve()))
    params = root / 'business_date.par'
    params.write_text('[Global]\n$$LOAD_DATE=' + day + '\n')
    estate = ROOT.parent / 'etl/informatica'
    service = Integration(Repository(str(estate / 'repository')),
                          [str(estate / 'params/sfx_d1110_daily.par'), str(params)],
                          pmrootdir=str(root / 'logs'))
    metrics = []
    for name in ('stg_document', 'document', 'doc_share'):
        status, record, stats = service.run_session('SFX_CONTENT', 'wf_SFX_CONTENT_DAILY',
                                                    's_m_SFX_' + name.upper(), service._next_run_id())
        if status != 'SUCCEEDED':
            raise RuntimeError(f'{name}: {status}: {record["FIRST_ERROR_MSG"]}')
        t = next(iter(stats.targets.values()))
        metrics.append(dict(pipeline=name, source_rows=stats.rows_read,
                            transformation_errors=stats.transformation_errors, written_rows=stats.rows_written,
                            rejected_rows=stats.rows_rejected, inserted_rows=t.inserted, updated_rows=t.updated,
                            rows_before=t.rows_before, rows_after=t.rows_after))
        print(f'legacy.informatica.{name}: read={stats.rows_read} written={stats.rows_written} rejected={stats.rows_rejected}')
    with psycopg.connect(**{**settings, 'dbname': database}) as target:
        for name, columns in [('stg_document', DOCUMENT), ('document', DOCUMENT), ('doc_share', SHARE)]:
            # Fixed column and table names are quoted by psycopg.
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            rows = target.execute(sql.SQL('SELECT {} FROM {}').format(
                sql.SQL(', ').join(map(sql.Identifier, columns)), sql.Identifier('sfx_documents', name))).fetchall()
            with (root / (name + '.psv')).open('w', newline='') as handle:
                writer = csv.writer(handle, delimiter='|')
                writer.writerow(columns)
                writer.writerows(rows)
    with (root / 'metrics.psv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(metrics[0]), delimiter='|')
        writer.writeheader()
        writer.writerows(metrics)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--landing', type=Path, required=True)
    parser.add_argument('--business-date', required=True)
    args = parser.parse_args()
    run(args.landing, args.business_date)


if __name__ == '__main__':
    main()
