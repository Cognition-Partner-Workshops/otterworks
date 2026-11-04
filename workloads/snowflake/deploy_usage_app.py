"""Deploy the doc_usage_dashboard Streamlit in Snowflake app as the workload's own service user."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'workloads/pipeline'))
import pipeline  # noqa: E402
from pipeline import CONSUMERS, attr, connect  # noqa: E402

WORKLOAD = 'doc_usage_dashboard'
APP_DIR = 'workloads/doc_usage_dashboard/app'
APP_FILES = ('streamlit_app.py', 'pyproject.toml')


def prepare_app(commit, directory, endpoint, run_id):
    directory.mkdir(parents=True, exist_ok=False)
    for name in APP_FILES:
        source = subprocess.check_output(['git', '-C', str(ROOT), 'show', f'{commit}:{APP_DIR}/{name}'])
        (directory / name).write_bytes(source)
    tag_sql = attr.streamlit_query_tag_sql(endpoint, commit=commit, run_id=run_id)
    (directory / 'query_tag.sql').write_text(tag_sql + '\n')
    return tag_sql


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--account', required=True)
    parser.add_argument('--private-key-file', required=True, help='service user private key')
    parser.add_argument('--public-key-file', type=Path, required=True, help='service user public key')
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--session-url', required=True, help='Devin session doing this dev-phase deploy')
    args = parser.parse_args()
    pipeline.SESSION_URL = args.session_url
    head = attr.current_commit(str(ROOT))
    pushed = subprocess.check_output(['git', '-C', str(ROOT), 'branch', '-r', '--contains', args.commit], text=True)
    if args.commit != head or not pushed.strip():
        raise ValueError('Deploy only the current, pushed HEAD')
    endpoint = attr.Endpoint.from_csid(CONSUMERS[WORKLOAD][0], WORKLOAD)
    reader = attr.role_name('reader')
    schema = f'{endpoint.database}.{attr.ANALYTICS_SCHEMA}'
    stage = f'{schema}.{WORKLOAD.upper()}_APP_STAGE'
    app = attr.streamlit_name(WORKLOAD)
    # The container runtime installs pyproject.toml dependencies from PyPI; egress is limited to the PyPI hosts.
    pypi_rule = f'{schema}.PYPI_EGRESS'
    pypi_eai = f'{attr.RUN_TOKEN}_EAI_{WORKLOAD.upper()}_PYPI'
    run_id = attr.make_run_id(WORKLOAD, 'runtime')
    tag_sql = prepare_app(args.commit, args.directory, endpoint, run_id)
    evidence = {'commit': args.commit, 'run_id': run_id, 'streamlit_query_tag_sql': tag_sql}

    with connect(WORKLOAD) as con:
        cur = con.cursor()
        cur.execute('USE SECONDARY ROLES NONE')
        for sql in (
            attr.service_user_ddl(endpoint, rsa_public_key=args.public_key_file.read_text(), role=reader),
            f'GRANT ROLE {reader} TO USER {endpoint.service_user}',
            f'GRANT USAGE ON WAREHOUSE {endpoint.warehouse} TO ROLE {reader}',
            f'GRANT CREATE STAGE, CREATE STREAMLIT ON SCHEMA {schema} TO ROLE {reader}',
            f"CREATE NETWORK RULE IF NOT EXISTS {pypi_rule} MODE = EGRESS TYPE = HOST_PORT "
            "VALUE_LIST = ('pypi.org', 'files.pythonhosted.org')",
            f'CREATE EXTERNAL ACCESS INTEGRATION IF NOT EXISTS {pypi_eai} '
            f'ALLOWED_NETWORK_RULES = ({pypi_rule}) ENABLED = TRUE',
            f'GRANT USAGE ON INTEGRATION {pypi_eai} TO ROLE {reader}',
        ):
            print(sql.split(' RSA_PUBLIC_KEY')[0], flush=True)
            cur.execute(sql)

    runtime = attr.connection_params(
        endpoint, account=args.account, private_key_file=args.private_key_file,
        phase='runtime', commit=args.commit, run_id=run_id, role=reader,
    )
    import snowflake.connector

    with snowflake.connector.connect(**runtime) as con:
        cur = con.cursor()
        cur.execute('USE SECONDARY ROLES NONE')
        evidence['deploy_session'] = cur.execute(
            'SELECT CURRENT_USER(), CURRENT_ROLE(), CURRENT_WAREHOUSE(), CURRENT_SESSION()').fetchone()
        cur.execute(f'CREATE STAGE IF NOT EXISTS {stage}')
        for file in sorted(args.directory.iterdir()):
            cur.execute(f"PUT 'file://{file}' @{stage}/{args.commit}/ AUTO_COMPRESS=FALSE OVERWRITE=TRUE")
        create = (
            f"CREATE OR REPLACE STREAMLIT {app} FROM '@{stage}/{args.commit}' "
            f"MAIN_FILE = 'streamlit_app.py' QUERY_WAREHOUSE = {endpoint.warehouse} "
            # Container runtime: the warehouse runtime runs as an owner's-rights procedure and rejects ALTER SESSION,
            # so it could not set the runtime QUERY_TAG. Queries still run on QUERY_WAREHOUSE.
            "RUNTIME_NAME = 'SYSTEM$ST_CONTAINER_RUNTIME_PY3_11' COMPUTE_POOL = SYSTEM_COMPUTE_POOL_CPU "
            f"EXTERNAL_ACCESS_INTEGRATIONS = ({pypi_eai}) "
            "TITLE = 'Storage quota by account'"
        )
        print(create, flush=True)
        cur.execute(create)
        evidence['streamlit'] = cur.execute(f"SHOW STREAMLITS LIKE '{app.split('.')[-1]}' IN SCHEMA {schema}").fetchall()

    with connect(WORKLOAD) as con:
        cur = con.cursor()
        cur.execute('USE SECONDARY ROLES NONE')
        for sql in attr.object_tag_ddl(WORKLOAD, [endpoint.csid], streamlit=True):
            print(sql, flush=True)
            cur.execute(sql)
        evidence['streamlit_tag'] = cur.execute(
            f"SELECT SYSTEM$GET_TAG('{attr.TAG_FQN}', '{app}', 'streamlit')").fetchone()[0]
        evidence['deployed_at'] = cur.execute(
            "SELECT TO_CHAR(SYSDATE(), 'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"')").fetchone()[0]
    print(json.dumps(evidence, default=str, indent=2), flush=True)
    args.output.write_text(json.dumps(evidence, default=str, indent=2))
    if evidence['streamlit_tag'] != endpoint.csid:
        raise AssertionError('Streamlit app is missing its DEVIN_CSID tag')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
