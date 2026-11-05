"""Deploy the doc_usage_dashboard Streamlit in Snowflake app as the workload's own service user."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'workloads/pipeline'))
from pipeline import CONSUMERS, attr, connect  # noqa: E402
from git_utils import require_pushed_commit  # noqa: E402
from query_recording import RecordingCursor  # noqa: E402

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


def streamlit_ddl(commit, run_id, endpoint=None):
    endpoint = endpoint or attr.Endpoint.from_csid(CONSUMERS[WORKLOAD][0], WORKLOAD)
    schema = f'{endpoint.database}.{attr.ANALYTICS_SCHEMA}'
    stage = f'{schema}.{WORKLOAD.upper()}_APP_STAGE'
    app = attr.streamlit_name(WORKLOAD)
    pypi_eai = f'{attr.RUN_TOKEN}_EAI_{WORKLOAD.upper()}_PYPI'
    return (
        f"CREATE OR REPLACE STREAMLIT {app} FROM '@{stage}/{commit}' "
        "MAIN_FILE = 'streamlit_app.py' "
        f"QUERY_WAREHOUSE = {endpoint.warehouse} "
        "RUNTIME_NAME = 'SYSTEM$ST_CONTAINER_RUNTIME_PY3_11' COMPUTE_POOL = SYSTEM_COMPUTE_POOL_CPU "
        f"EXTERNAL_ACCESS_INTEGRATIONS = ({pypi_eai}) "
        "TITLE = 'Storage quota by account'"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--account', required=True)
    parser.add_argument('--private-key-file', required=True, help='service user private key')
    parser.add_argument('--public-key-file', type=Path, help='optional service user public key')
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--session-url', help='Devin session doing this dev-phase deploy')
    parser.add_argument('--query-record', type=Path)
    args = parser.parse_args()
    if args.session_url:
        os.environ['SESSION_URL'] = args.session_url
    require_pushed_commit(args.commit, str(ROOT))
    os.environ['SF_COMMIT'] = args.commit
    endpoint = attr.Endpoint.from_csid(CONSUMERS[WORKLOAD][0], WORKLOAD)
    reader = attr.role_name('reader')
    schema = f'{endpoint.database}.{attr.ANALYTICS_SCHEMA}'
    stage = f'{schema}.{WORKLOAD.upper()}_APP_STAGE'
    app = attr.streamlit_name(WORKLOAD)
    # The container runtime installs pyproject.toml dependencies from PyPI; egress is limited to the PyPI hosts.
    pypi_rule = f'{schema}.PYPI_EGRESS'
    pypi_eai = f'{attr.RUN_TOKEN}_EAI_{WORKLOAD.upper()}_PYPI'
    run_id_key = f"SF_RUN_ID_{WORKLOAD.upper()}"
    run_id = os.environ.get(run_id_key) or attr.make_run_id(WORKLOAD, 'runtime')
    os.environ[run_id_key] = run_id
    tag_sql = prepare_app(args.commit, args.directory, endpoint, run_id)
    evidence = {'commit': args.commit, 'run_id': run_id, 'streamlit_query_tag_sql': tag_sql}
    run_ids = {WORKLOAD: run_id}

    with connect(WORKLOAD) as con:
        cur = con.cursor()
        if args.query_record:
            cur = RecordingCursor(
                cur, args.query_record, commit=args.commit,
                run_ids=run_ids, step='deploy_app',
            )
        cur.execute('USE SECONDARY ROLES NONE')
        if args.public_key_file:
            sql = attr.service_user_ddl(
                endpoint, rsa_public_key=args.public_key_file.read_text(), role=reader,
            )
            print(sql.split(' RSA_PUBLIC_KEY')[0], flush=True)
            cur.execute(sql)
        else:
            cur.execute(f"SHOW USERS LIKE {attr.sql_string(endpoint.service_user)}")
            users = cur.fetchall()
            if not any(str(row[0]).upper() == endpoint.service_user for row in users):
                raise RuntimeError(
                    f"Service user {endpoint.service_user} is missing; provide --public-key-file to create it"
                )
        for sql in (
            f'GRANT ROLE {reader} TO USER {endpoint.service_user}',
            f'GRANT USAGE ON WAREHOUSE {endpoint.warehouse} TO ROLE {reader}',
            f'GRANT CREATE STAGE, CREATE STREAMLIT ON SCHEMA {schema} TO ROLE {reader}',
            f"CREATE NETWORK RULE IF NOT EXISTS {pypi_rule} MODE = EGRESS TYPE = HOST_PORT "
            "VALUE_LIST = ('pypi.org', 'files.pythonhosted.org')",
            f'CREATE EXTERNAL ACCESS INTEGRATION IF NOT EXISTS {pypi_eai} '
            f'ALLOWED_NETWORK_RULES = ({pypi_rule}) ENABLED = TRUE',
            f'GRANT USAGE ON INTEGRATION {pypi_eai} TO ROLE {reader}',
        ):
            cur.execute(sql)

    runtime = attr.connection_params(
        endpoint, account=args.account, private_key_file=args.private_key_file,
        phase='runtime', commit=args.commit, run_id=run_id, role=reader,
    )
    import snowflake.connector

    with snowflake.connector.connect(**runtime) as con:
        cur = con.cursor()
        if args.query_record:
            cur = RecordingCursor(
                cur, args.query_record, commit=args.commit,
                run_ids=run_ids, step='deploy_app',
            )
        cur.execute('USE SECONDARY ROLES NONE')
        evidence['deploy_session'] = cur.execute(
            'SELECT CURRENT_USER(), CURRENT_ROLE(), CURRENT_WAREHOUSE(), CURRENT_SESSION()').fetchone()
        cur.execute(f'CREATE STAGE IF NOT EXISTS {stage}')
        for file in sorted(args.directory.iterdir()):
            cur.execute(f"PUT 'file://{file}' @{stage}/{args.commit}/ AUTO_COMPRESS=FALSE OVERWRITE=TRUE")
        create = streamlit_ddl(args.commit, run_id, endpoint)
        print(create, flush=True)
        cur.execute(create)
        evidence['streamlit'] = cur.execute(f"SHOW STREAMLITS LIKE '{app.split('.')[-1]}' IN SCHEMA {schema}").fetchall()

    with connect(WORKLOAD) as con:
        cur = con.cursor()
        if args.query_record:
            cur = RecordingCursor(
                cur, args.query_record, commit=args.commit,
                run_ids=run_ids, step='deploy_app',
            )
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
