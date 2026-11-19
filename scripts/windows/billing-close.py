"""Native analyst close commands; invoke through the adjacent PowerShell wrappers."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zlib

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from warehouse.run_config import RunConfig

RUNS = ROOT / 'migration/dw-exit/.runs/windows-close-duckdb'
PYTHON = ROOT / 'warehouse/.venv/Scripts/python.exe'
INFA_PYTHON = ROOT / 'etl/informatica/.venv/Scripts/python.exe'
SNAPSHOT = 'sfx_windows_close_baseline'


def run(*args, cwd=ROOT, env=None):
    subprocess.run([str(a) for a in args], cwd=cwd, env=env, check=True)


def configure():
    config = RunConfig(os.environ.get('RUN_TOKEN', 'sfx1119'))
    os.environ.update(config.environment())
    os.environ.setdefault('NS', config.before_namespace)
    os.environ.setdefault('TD_PG_PORT', str(54500 + zlib.crc32(os.environ['NS'].encode()) % 1000))
    os.environ.update(TD_PORT=os.environ['TD_PG_PORT'], TD_HOST='127.0.0.1',
                      TD_PG_HOST='127.0.0.1', TD_DB='teradata', TD_PG_DB='teradata',
                      TD_USER='postgres', TD_PG_USER='postgres',
                      PYTHONPATH=str(ROOT / 'warehouse/teradata'),
                      SFX_QUERY_TAG_LABEL='sfx1119')
    RUNS.mkdir(parents=True, exist_ok=True)
    return config


def legacy(args):
    run('docker', 'compose', '-f', 'warehouse/teradata/docker-compose.teradata.yml',
        'up', '-d', '--wait', '--pull', 'never')
    with psycopg.connect(host='127.0.0.1', port=os.environ['TD_PG_PORT'], user='postgres',
                         dbname='teradata', autocommit=True) as conn:
        if conn.execute("SELECT to_regclass('sfx_billing.gl_journal_line')").fetchone()[0]:
            conn.execute('TRUNCATE sfx_billing.gl_journal_line')
    print('Reset local demo GL before loading the reproducible BTEQ fixture', flush=True)
    run(PYTHON, 'warehouse/teradata/jobs/daily_chain', '--rows', args.rows, '--seed', '1110',
        '--business-date', args.business_date)
    with psycopg.connect(host='127.0.0.1', port=os.environ['TD_PG_PORT'], user='postgres',
                         dbname='postgres', autocommit=True) as conn:
        conn.execute(sql.SQL('DROP DATABASE IF EXISTS {}').format(sql.Identifier(SNAPSHOT)))
        conn.execute(sql.SQL('CREATE DATABASE {} TEMPLATE teradata').format(sql.Identifier(SNAPSHOT)))
    print('BTEQ baseline preserved locally before PowerCenter', flush=True)
    with psycopg.connect(host='127.0.0.1', port=os.environ['TD_PG_PORT'], user='postgres',
                         dbname=SNAPSHOT) as conn:
        tables = conn.execute("SELECT tablename FROM pg_tables WHERE schemaname='sfx_billing' ORDER BY tablename").fetchall()
        evidence = {'rows': args.rows, 'business_date': args.business_date, 'tables': {}}
        for (table,) in tables:
            rows = conn.execute(sql.SQL('SELECT * FROM {}').format(sql.Identifier('sfx_billing', table))).fetchall()
            evidence['tables'][table] = {'rows': len(rows), 'sha256': hashlib.sha256(
                '\n'.join(sorted(map(repr, rows))).encode()).hexdigest()}
        path = RUNS / 'legacy-snapshot.json'
        if path.exists():
            previous = json.loads(path.read_text())
            if previous['rows'] == args.rows and previous['business_date'] == args.business_date:
                if previous != evidence:
                    raise RuntimeError('BTEQ fixture changed on rerun; snapshot hashes differ')
                print('BTEQ rerun: all snapshot table row counts and hashes MATCH', flush=True)
        path.write_text(json.dumps(evidence, indent=2) + '\n')
    os.environ.update(LANDING_DIR=str(ROOT / 'warehouse/landing'),
                      PMROOTDIR=str(ROOT / 'etl/informatica/infa_shared' / os.environ['NS']))
    run(INFA_PYTHON, '-m', 'runner', 'startworkflow', '-f', 'SFX_BILLING',
        'wf_SFX_BILLING_DAILY', cwd=ROOT / 'etl/informatica')
    print('\nBTEQ CLOSE: currency | invoice count | total amount', flush=True)
    print((ROOT / 'warehouse/exports/period_close.psv').read_text(), flush=True)


def migrated(args):
    env = {k: v for k, v in os.environ.items() if not k.startswith('SNOWFLAKE_')}
    run(PYTHON, ROOT / 'scripts/windows/duckdb-close.py', '--business-date', args.business_date,
        '--rows', args.rows, '--output', RUNS, env=env)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['legacy', 'migrated'])
    parser.add_argument('--rows', type=int, default=20000)
    parser.add_argument('--business-date', default='20261109')
    args = parser.parse_args()
    configure()
    (legacy if args.command == 'legacy' else migrated)(args)


if __name__ == '__main__':
    main()
