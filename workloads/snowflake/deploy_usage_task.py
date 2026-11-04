"""Deploy the pushed usage dbt project and verify a manually triggered hourly task."""

import argparse
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'workloads/pipeline'))
from pipeline import CONSUMERS, attr, connect  # noqa: E402

WORKLOAD = 'doc_usage_dashboard'


def task_sql(commit, run_id):
    endpoint = attr.Endpoint.from_csid(CONSUMERS[WORKLOAD][0], WORKLOAD)
    names = attr.names([WORKLOAD])
    body = (
        f"BEGIN\n  CALL {endpoint.database}.RAW.LOAD_RAW();\n"
        f"  EXECUTE DBT PROJECT {names[f'dbt_project_{WORKLOAD}']} "
        "ARGS = 'build --target runtime --select path:models/doc_usage_dashboard';\nEND;"
    )
    return attr.create_task_sql(
        endpoint, schedule='USING CRON 0 * * * * UTC', body=body,
        commit=commit, run_id=run_id, phase='runtime',
    )


def prepare_project(commit, directory, runtime_tag):
    archive = subprocess.check_output(['git', '-C', str(ROOT), 'archive', commit, 'workloads/dbt'])
    directory.mkdir(parents=True, exist_ok=False)
    with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
        stream.extractall(directory, filter='data')
    project = directory / 'workloads/dbt'
    names = attr.names([WORKLOAD])
    profile = yaml.safe_load((project / 'runtime_profile.template.yml').read_text())
    target = profile['otterworks']['outputs']['runtime']
    target.update(role=os.environ['SNOWFLAKE_ROLE'], database=names[f'db_{WORKLOAD}'],
                  warehouse=names[f'wh_{WORKLOAD}'], query_tag=runtime_tag)
    target['session_parameters']['QUERY_TAG'] = runtime_tag
    (project / 'profiles.yml').write_text(yaml.safe_dump(profile, sort_keys=False))
    config = yaml.safe_load((project / 'dbt_project.yml').read_text())
    config['vars'] = {key: names[key] for key in ('reader_role', 'analyst_role')}
    (project / 'dbt_project.yml').write_text(yaml.safe_dump(config, sort_keys=False))
    return project


def project_files(project):
    return sorted(file for file in project.rglob('*') if file.is_file() and file.suffix in ('.sql', '.yml'))


def query_is_compliant(query_type, query_text, query_tag, first_in_session, runtime_tag):
    if query_tag == runtime_tag:
        return True
    # Native dbt's first tag setter is recorded before its own tag takes effect.
    setter = re.fullmatch(
        r"\s*(?i:alter\s+session\s+set\s+query_tag)\s*=\s*('(?:[^'\\]|\\.|'')*')\s*;?\s*",
        query_text,
    )
    return bool(first_in_session and query_type == 'ALTER_SESSION'
                and setter and setter[1] == attr.sql_string(runtime_tag))


def verify_run(cur, names, task, runtime_tag, started):
    history_sql = (
        'SELECT NAME,STATE,SCHEDULED_TIME,QUERY_START_TIME,COMPLETED_TIME,QUERY_ID,ERROR_CODE,ERROR_MESSAGE '
        f"FROM TABLE({names[f'db_{WORKLOAD}']}.INFORMATION_SCHEMA.TASK_HISTORY("
        f"TASK_NAME=>'{task.split('.')[-1]}',SCHEDULED_TIME_RANGE_START=>TO_TIMESTAMP_LTZ(%s),"
        'SCHEDULED_TIME_RANGE_END=>CURRENT_TIMESTAMP(),RESULT_LIMIT=>10)) ORDER BY SCHEDULED_TIME'
    )
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        rows = cur.execute(history_sql, (started,)).fetchall()
        if rows and rows[0][1] in ('SUCCEEDED', 'FAILED', 'CANCELLED'):
            break
        time.sleep(5)
    else:
        raise TimeoutError('Task did not finish within 15 minutes')
    row = rows[0]
    print('TASK_HISTORY:', row, flush=True)
    if row[1] != 'SUCCEEDED':
        raise RuntimeError(f'Task failed: {row}')
    query_sql = (
        'SELECT QUERY_ID,START_TIME,ROLE_NAME,QUERY_TYPE,LEFT(QUERY_TEXT,60),QUERY_TAG,QUERY_TEXT,SESSION_ID '
        f"FROM TABLE({names[f'db_{WORKLOAD}']}.INFORMATION_SCHEMA.QUERY_HISTORY_BY_WAREHOUSE("
        f"WAREHOUSE_NAME=>'{names[f'wh_{WORKLOAD}']}',END_TIME_RANGE_START=>TO_TIMESTAMP_LTZ(%s),"
        'END_TIME_RANGE_END=>TO_TIMESTAMP_LTZ(%s),RESULT_LIMIT=>10000)) '
        'WHERE START_TIME >= %s AND START_TIME <= %s ORDER BY START_TIME'
    )
    print('QUERY_HISTORY SQL:', query_sql, '\nPARAMETERS:', row[3], row[4], row[3], row[4], flush=True)
    queries = cur.execute(query_sql, (row[3], row[4], row[3], row[4])).fetchall()
    if len(queries) >= 10000:
        raise AssertionError('Query history result limit reached')
    first_query_sql = (
        'SELECT QUERY_ID,COUNT(*) OVER() '
        f"FROM TABLE({names[f'db_{WORKLOAD}']}.INFORMATION_SCHEMA.QUERY_HISTORY_BY_SESSION("
        'SESSION_ID=>%s,END_TIME_RANGE_END=>TO_TIMESTAMP_LTZ(%s),RESULT_LIMIT=>10000,'
        'INCLUDE_CLIENT_GENERATED_STATEMENT=>TRUE)) ORDER BY START_TIME,QUERY_ID LIMIT 1'
    )
    print('FIRST SESSION QUERY SQL:', first_query_sql, flush=True)
    first_queries = {}
    proof = []
    for query in queries:
        if query[5] != runtime_tag and query[7] not in first_queries:
            first = cur.execute(first_query_sql, (query[7], row[4])).fetchall()
            if not first or first[0][1] >= 10000:
                raise AssertionError('Missing or truncated session history')
            first_queries[query[7]] = first[0][0]
        first_in_session = first_queries.get(query[7]) == query[0]
        proof.append((*query, first_in_session))
        print((*query[:6], query[7], first_in_session), flush=True)
    strict_mismatches = [query for query in proof if query[5] != runtime_tag]
    mismatches = [query for query in proof if not query_is_compliant(query[3], query[6], query[5], query[8], runtime_tag)]
    print('Strict QUERY_TAG mismatch count:', len(strict_mismatches), 'of', len(queries), flush=True)
    print('QUERY_TAG mismatch count after bootstrap exception:', len(mismatches), 'of', len(queries), flush=True)
    if not queries or mismatches:
        raise AssertionError('Missing queries or runtime query-tag mismatch')
    return {'task_history': row, 'query_history_sql': query_sql, 'first_query_sql': first_query_sql,
            'first_queries': first_queries, 'queries': proof, 'strict_mismatch_count': len(strict_mismatches),
            'mismatch_count': len(mismatches)}


def verify_or_suspend(cur, names, task, runtime_tag, started):
    try:
        return verify_run(cur, names, task, runtime_tag, started)
    except Exception:
        cur.execute(f'ALTER TASK {task} SUSPEND')
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    pushed = subprocess.check_output([
        'git', '-C', str(ROOT), 'ls-remote', 'origin', 'refs/heads/devin/1793825355-sf-pipeline',
    ], text=True).split()[0]
    if args.commit != pushed or args.commit != attr.current_commit(str(ROOT)):
        raise ValueError('Deploy only the current, pushed branch HEAD')
    names = attr.names([WORKLOAD])
    endpoint = attr.Endpoint.from_csid(CONSUMERS[WORKLOAD][0], WORKLOAD)
    tag = attr.query_tag_json(endpoint, phase='runtime', commit=args.commit,
                              run_id=attr.make_run_id(WORKLOAD, 'runtime'))
    run_id = json.loads(tag)['run_id']
    project = prepare_project(args.commit, args.directory, tag)
    ddl = task_sql(args.commit, run_id)
    evidence = {'commit': args.commit, 'runtime_tag': tag, 'task_ddl': ddl}
    with connect(WORKLOAD) as con:
        cur = con.cursor()
        cur.execute('USE SECONDARY ROLES NONE')
        cur.execute(f"CREATE STAGE IF NOT EXISTS {names[f'dbt_stage_{WORKLOAD}']}")
        for file in project_files(project):
            folder = file.relative_to(project).parent.as_posix()
            folder = '' if folder == '.' else folder + '/'
            cur.execute(f"PUT 'file://{file}' @{names[f'dbt_stage_{WORKLOAD}']}/{args.commit}/{folder} AUTO_COMPRESS=FALSE OVERWRITE=FALSE")
        create = (
            f"CREATE OR REPLACE DBT PROJECT {names[f'dbt_project_{WORKLOAD}']} "
            f"FROM '@{names[f'dbt_stage_{WORKLOAD}']}/{args.commit}' "
            "DBT_VERSION = '1.9.4' DEFAULT_TARGET = 'runtime' AUTO_COMPILE = FALSE"
        )
        print(create, flush=True)
        print(cur.execute(create).fetchall(), flush=True)
        print(ddl, flush=True)
        print(cur.execute(ddl).fetchall(), flush=True)
        for sql in attr.object_tag_ddl(WORKLOAD, [endpoint.csid]):
            print(sql, flush=True)
            cur.execute(sql)
        task = attr.task_name(WORKLOAD)
        cur.execute(f'ALTER TASK {task} RESUME')
        print('TASK DEFINITION:', cur.execute(f"SHOW TASKS LIKE 'REFRESH_DOC_USAGE_DASHBOARD' IN SCHEMA {endpoint.database}.ANALYTICS").fetchall(), flush=True)
        print('TASK PARAMETERS:', cur.execute(f"SHOW PARAMETERS LIKE 'QUERY_TAG' IN TASK {task}").fetchall(), flush=True)
        args.output.write_text(json.dumps(evidence, indent=2))
        cur.execute(f'ALTER SESSION SET QUERY_TAG = {attr.sql_string(tag)}')
        started = cur.execute('SELECT CURRENT_TIMESTAMP()').fetchone()[0]
        cur.execute(f'EXECUTE TASK {task}')
        try:
            evidence.update(verify_or_suspend(cur, names, task, tag, started))
        except Exception as error:
            evidence['verification_error'] = str(error)
            args.output.write_text(json.dumps(evidence, default=str, indent=2))
            raise
        args.output.write_text(json.dumps(evidence, default=str, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
