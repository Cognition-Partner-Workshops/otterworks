"""Run every workload separately: dev profile, own warehouse, own JSON tag."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

import snowflake.connector
from dbt.cli.main import dbtRunner

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'workloads/pipeline'))
from pipeline import CONSUMERS, SESSION_URL, attr  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workload', choices=list(CONSUMERS))
    args, dbt_args = parser.parse_known_args()
    os.environ.pop('SNOWFLAKE_HOST', None)
    original_connect = snowflake.connector.connect
    for workload, (csid, _) in CONSUMERS.items():
        if args.workload and args.workload != workload:
            continue
        names = attr.names([workload])
        os.environ['DBT_DATABASE'] = names[f'db_{workload}']
        os.environ['DBT_WAREHOUSE'] = names[f'wh_{workload}']
        os.environ['DBT_QUERY_TAG'] = subprocess.check_output([
            'python3', str(ROOT / 'workloads/attribution/sf_attribution.py'), 'tag',
            '--workload', workload, '--csid', csid, '--phase', 'dev', '--session-url', SESSION_URL,
        ], text=True).strip()

        def attributed_connect(**kwargs):
            params = attr.connection_params(
                attr.Endpoint.from_csid(csid, workload), account=os.environ['SNOWFLAKE_ACCOUNT'],
                private_key_file=os.environ['SNOWFLAKE_PRIVATE_KEY_FILE'], phase='dev',
                commit=attr.current_commit(str(ROOT)), run_id=attr.make_run_id(workload, 'dev'),
                session_url=SESSION_URL, role=os.environ['SNOWFLAKE_ROLE'],
            )
            params['user'] = os.environ['SNOWFLAKE_USER']
            params['session_parameters'].update({'TIMEZONE': 'UTC', 'WEEK_START': 1})
            params['session_parameters']['QUERY_TAG'] = os.environ['DBT_QUERY_TAG']
            for key in ('client_session_keep_alive', 'autocommit', 'client_prefetch_threads'):
                if key in kwargs:
                    params[key] = kwargs[key]
            return original_connect(**params)

        snowflake.connector.connect = attributed_connect
        print(f'=== dbt build: {workload} ===', flush=True)
        result = dbtRunner().invoke([
            'build', '--project-dir', str(Path(__file__).parent), '--profiles-dir', str(Path(__file__).parent),
            '--target', 'dev', '--select', f'path:models/{workload}', '--no-partial-parse',
            '--vars', '{"reader_role": "' + names['reader_role'] + '", "analyst_role": "' + names['analyst_role']
            + '", "email_masking_policy": "' + names['email_masking_policy'] + '"}', *dbt_args,
        ])
        if not result.success:
            print(result.exception or 'dbt build failed')
            return 1
    snowflake.connector.connect = original_connect
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
