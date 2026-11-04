"""Apply pipeline migrations with fresh histories in disposable workload-local schemas."""

import argparse
import re
import sys
from pathlib import Path

import snowflake.connector
from schemachange.cli import main
from schemachange.JinjaTemplateProcessor import JinjaTemplateProcessor
from schemachange.session.SnowflakeSession import SnowflakeSession

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'workloads/pipeline'))
from pipeline import CONSUMERS, attr, connect  # noqa: E402


def run(directory):
    directory.mkdir(parents=True, exist_ok=False)
    names = attr.names(list(CONSUMERS))
    migrations = ROOT / 'workloads/snowflake'
    foundation = JinjaTemplateProcessor(migrations / 'migrations').render('V1.4.0__raw_customer_tables.sql', names)
    original_connect = snowflake.connector.connect
    original_reset = SnowflakeSession.reset_query_tag
    for workload in CONSUMERS:
        prefix = names[f'db_{workload}'] + '.RAW.'
        proof_schema = names[f'proof_schema_{workload}']
        proof_prefix = proof_schema + '.'
        with connect(workload) as con:
            con.cursor().execute(f'CREATE SCHEMA {proof_schema}')
        try:
            with connect(workload) as con:
                for ddl in re.findall(r'CREATE TABLE IF NOT EXISTS ' + re.escape(prefix) + r'.*?;', foundation + ';', re.S):
                    con.cursor().execute(ddl.replace(prefix, proof_prefix))
            folder = migrations / 'pipeline_migrations' / workload
            rendered = directory / workload
            rendered.mkdir()
            processor = JinjaTemplateProcessor(folder)
            for path in folder.glob('*.sql'):
                sql = processor.render(path.name, names).replace(prefix, proof_prefix)
                sql = sql.replace(names[f'history_{workload}'], names[f'proof_history_{workload}'])
                (rendered / path.name).write_text(sql)

            def attributed_connect(**kwargs):
                snowflake.connector.connect = original_connect
                try:
                    return connect(workload)
                finally:
                    snowflake.connector.connect = attributed_connect

            snowflake.connector.connect = attributed_connect
            SnowflakeSession.reset_query_tag = lambda *args, **kwargs: None
            sys.argv = ['schemachange', 'deploy', '--root-folder', str(rendered),
                        '--change-history-table', names[f'proof_history_{workload}'],
                        '--create-change-history-table', '--snowflake-warehouse', names[f'wh_{workload}']]
            print(f'FRESH HISTORY: {workload}', flush=True)
            main()
        finally:
            snowflake.connector.connect = original_connect
            SnowflakeSession.reset_query_tag = original_reset
            with connect(workload) as con:
                con.cursor().execute(f'DROP SCHEMA {proof_schema}')
    print('PASS: all workload migrations applied from fresh foundation tables and empty histories')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    run(parser.parse_args().directory)
