"""Apply workload-scoped pipeline migrations after the V1.0-V1.7 foundation."""

import json
import os
import sys
from pathlib import Path

import snowflake.connector
from schemachange.cli import main
from schemachange.session.SnowflakeSession import SnowflakeSession

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'workloads/pipeline'))
from pipeline import CONSUMERS, attr, connect  # noqa: E402


def main_pipeline():
    original_connect = snowflake.connector.connect
    for workload in CONSUMERS:
        def attributed_connect(**kwargs):
            snowflake.connector.connect = original_connect
            try:
                return connect(workload)
            finally:
                snowflake.connector.connect = attributed_connect

        snowflake.connector.connect = attributed_connect

        def reset_query_tag(self, logger, extra_tag=None):
            # schemachange normally appends non-JSON text to QUERY_TAG.
            tag = attr.query_tag_json(
                attr.Endpoint.from_csid(CONSUMERS[workload][0], workload), phase='dev',
                commit=attr.current_commit(str(ROOT)), run_id=attr.make_run_id(workload, 'dev'),
                session_url=os.environ['SESSION_URL'],
            )
            self.execute_snowflake_query(f'ALTER SESSION SET QUERY_TAG = {attr.sql_string(tag)}', logger=logger)

        SnowflakeSession.reset_query_tag = reset_query_tag
        names = attr.names(list(CONSUMERS))
        sys.argv = ['schemachange', 'deploy', '--root-folder', str(Path(__file__).parent / 'pipeline_migrations' / workload),
                    '--change-history-table', names[f'history_{workload}'], '--create-change-history-table',
                    '--snowflake-warehouse', names[f'wh_{workload}'], '--vars', json.dumps(names)]
        if os.environ.get('DRY_RUN'):
            sys.argv.append('--dry-run')
        print(f'Applying pipeline migrations: {workload}', flush=True)
        main()
    snowflake.connector.connect = original_connect


if __name__ == '__main__':
    main_pipeline()
