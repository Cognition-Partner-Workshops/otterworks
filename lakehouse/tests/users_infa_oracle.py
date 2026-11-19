"""Provision an isolated PostgreSQL DB and run the five legacy users sessions."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from psycopg import sql

from lakehouse.parity.readers import postgres_connection
from lakehouse.runtime.ingest import business_date
from lakehouse.runtime.layout import ROOT, data_root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--business-date', required=True)
    parser.add_argument('--landing', required=True, type=Path)
    args = parser.parse_args()
    business_date(args.business_date)
    repo = ROOT.parent
    root = data_root() / 'oracle/infa'
    root.mkdir(parents=True, exist_ok=True)
    database = 'users_infa'
    with postgres_connection() as conn:
        conn.autocommit = True
        if not conn.execute('select 1 from pg_database where datname = %s', (database,)).fetchone():
            conn.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(database)))
        config = {'HOST': conn.info.host, 'PORT': str(conn.info.port),
                  'USER': conn.info.user, 'PASSWORD': conn.info.password}
    subprocess.run([str(repo / 'warehouse/.venv/bin/python'), '-m', 'bteq.setup'], check=True, cwd=repo,
                   env={**os.environ, 'TD_PG_DSN': '', 'TD_PG_DB': database,
                        'PYTHONPATH': str(repo / 'warehouse/teradata'),
                        **{f'TD_PG_{key}': value for key, value in config.items()}})
    params = root / 'users.par'
    params.write_text('[Global]\n$$LOAD_DATE=' + args.business_date + '\n')
    env = {**os.environ, 'TD_DB': database, 'LANDING_DIR': str(args.landing.resolve()),
           'PMROOTDIR': str(root),
           **{f'TD_{key}': value for key, value in config.items()}}
    for name in ('STG_APP_USER', 'APP_USER', 'ROLE_GRANT', 'LOGIN_EVENT', 'TEAM_MEMBER'):
        subprocess.run([sys.executable, '-m', 'runner', 'startsession', '-f', 'SFX_CONTENT',
                        '-w', 'wf_SFX_CONTENT_DAILY', '-paramfile', str(params), 's_m_SFX_' + name],
                       check=True, cwd=repo / 'etl/informatica', env=env)


if __name__ == '__main__':
    main()
