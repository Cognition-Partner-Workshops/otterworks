"""Build or compile each workload with an attributed Snowflake connection."""

import argparse
import json
import os
import sys
from pathlib import Path

import snowflake.connector
from dbt.cli.main import dbtRunner

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'workloads/pipeline'))
from pipeline import CONSUMERS, phase_context, attr  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workload', choices=list(CONSUMERS))
    parser.add_argument('--project-dir', type=Path, default=ROOT / 'workloads/dbt')
    parser.add_argument('--compile-only', action='store_true')
    parser.add_argument('--results-dir', type=Path)
    args, dbt_args = parser.parse_known_args()
    os.environ.pop('SNOWFLAKE_HOST', None)
    original_connect = snowflake.connector.connect
    project_dir = args.project_dir.resolve()
    try:
        for workload, (csid, _) in CONSUMERS.items():
            if args.workload and args.workload != workload:
                continue
            phase, commit, session_url, run_id = phase_context(workload)
            names = attr.names([workload])
            endpoint = attr.Endpoint.from_csid(csid, workload)
            tag = attr.query_tag_json(
                endpoint, phase=phase, commit=commit, run_id=run_id, session_url=session_url,
            )
            os.environ['DBT_DATABASE'] = names[f'db_{workload}']
            os.environ['DBT_WAREHOUSE'] = names[f'wh_{workload}']
            os.environ['DBT_QUERY_TAG'] = tag

            def attributed_connect(**kwargs):
                params = attr.connection_params(
                    endpoint, account=os.environ.get('SFNFR_ACCOUNT') or os.environ['SNOWFLAKE_ACCOUNT'],
                    private_key_file=os.environ['SNOWFLAKE_PRIVATE_KEY_FILE'],
                    phase=phase, commit=commit, run_id=run_id, session_url=session_url,
                    role=os.environ.get('SFNFR_ROLE') or os.environ['SNOWFLAKE_ROLE'],
                )
                params['user'] = os.environ.get('SFNFR_USER') or os.environ['SNOWFLAKE_USER']
                params['session_parameters'].update({'TIMEZONE': 'UTC', 'WEEK_START': 1})
                for key in ('client_session_keep_alive', 'autocommit', 'client_prefetch_threads'):
                    if key in kwargs:
                        params[key] = kwargs[key]
                return original_connect(**params)

            snowflake.connector.connect = attributed_connect
            target_path = None
            if args.results_dir:
                target_path = (args.results_dir / workload).resolve()
                target_path.mkdir(parents=True, exist_ok=True)
            command = 'compile' if args.compile_only else 'build'
            print(f'=== dbt {command}: {workload} ===', flush=True)
            invocation = [
                command, '--project-dir', str(project_dir), '--profiles-dir', str(Path(__file__).parent),
                '--target', 'dev', '--select', f'path:models/{workload}', '--no-partial-parse',
                '--vars', json.dumps({
                    'reader_role': names['reader_role'],
                    'analyst_role': names['analyst_role'],
                    'email_masking_policy': names['email_masking_policy'],
                }),
            ]
            if target_path:
                invocation.extend(['--target-path', str(target_path)])
            result = dbtRunner().invoke([*invocation, *dbt_args])
            if not result.success:
                print(result.exception or f'dbt {command} failed')
                return 1
        return 0
    finally:
        snowflake.connector.connect = original_connect


if __name__ == '__main__':
    raise SystemExit(main())
