"""Export synthetic Postgres snapshots and load each consumer's private RAW stage."""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'workloads/attribution'))
import sf_attribution as attr  # noqa: E402

SESSION_URL = 'https://partner-workshops.devinenterprise.com/sessions/c7aba848685a48e38d97b1f39435fda5'
CONSUMERS = {
    'doc_usage_dashboard': ('cs_doc_usage_dashboard_account_usage', ['storage_quotas', 'admin_users', 'documents']),
    'doc_search_api': ('cs_doc_search_api_top_items', ['analytics_events', 'documents']),
    'churn_model': ('cs_churn_model_account_score', ['users', 'admin_users', 'document_versions']),
}
AUTH_COLUMNS = 'id,email,display_name,avatar_url,email_verified,mfa_enabled,created_at,updated_at,last_login_at'


def phase_context(workload):
    phase = os.environ.get('SF_PHASE', 'dev')
    if phase not in attr.PHASES:
        raise ValueError(f"SF_PHASE must be one of {attr.PHASES}, got {phase!r}")
    commit = os.environ.get('SF_COMMIT') or attr.current_commit(str(ROOT))
    session_url = (os.environ.get('SESSION_URL') or SESSION_URL) if phase == 'dev' else None
    run_id = os.environ.get(f"SF_RUN_ID_{workload.upper()}") or attr.make_run_id(workload, phase)
    return phase, commit, session_url, run_id


def connect(workload):
    import snowflake.connector

    os.environ.pop('SNOWFLAKE_HOST', None)
    phase, commit, session_url, run_id = phase_context(workload)
    params = attr.connection_params(
        attr.Endpoint.from_csid(CONSUMERS[workload][0], workload),
        account=os.environ['SNOWFLAKE_ACCOUNT'],
        private_key_file=os.environ['SNOWFLAKE_PRIVATE_KEY_FILE'],
        phase=phase, commit=commit, run_id=run_id, session_url=session_url,
        role=os.environ['SNOWFLAKE_ROLE'], schema='RAW',
    )
    params['user'] = os.environ['SNOWFLAKE_USER']
    return snowflake.connector.connect(**params)


def export(directory, exported_at, duplicate_rows=False):
    stamp = datetime.fromisoformat(exported_at.replace('Z', '+00:00')) if exported_at else datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        raise ValueError('exported_at must have a UTC offset')
    stamp = stamp.astimezone(timezone.utc).isoformat()
    batch = str(uuid.uuid4())
    directory.mkdir(parents=True, exist_ok=False)
    for table in sorted({t for _, tables in CONSUMERS.values() for t in tables}):
        columns = AUTH_COLUMNS if table == 'users' else '*'
        sql = f"COPY (SELECT {columns}, '{batch}' AS _export_id, '{stamp}' AS _exported_at FROM {table} ORDER BY id) TO STDOUT WITH CSV HEADER NULL '\\N'"
        result = subprocess.run(
            ['docker', 'exec', 'sfnfr-postgres', 'psql', '-U', 'postgres', '-d', 'otterworks', '-c', sql],
            check=True, capture_output=True,
        )
        content = result.stdout
        if duplicate_rows:
            rows = list(csv.reader(io.StringIO(content.decode())))
            output = io.StringIO()
            writer = csv.writer(output, lineterminator='\n')
            writer.writerow(rows[0])
            writer.writerows(rows[1:] * 2)
            content = output.getvalue().encode()
        with gzip.open(directory / f'{table}.csv.gz', 'wb') as stream:
            stream.write(content)
    (directory / 'manifest.json').write_text(json.dumps({'export_id': batch, 'exported_at': stamp}))
    print(f'exported {batch} at {stamp} to {directory}')


def load(directory, suffix):
    for workload, (_, tables) in CONSUMERS.items():
        with connect(workload) as con:
            cur = con.cursor()
            cur.execute('USE SECONDARY ROLES NONE')
            for table in tables:
                file = (directory / f'{table}.csv.gz').resolve()
                path = f'{directory.name}{suffix}'
                if not path.replace('-', '').replace('_', '').isalnum():
                    raise ValueError('batch directory and suffix must be alphanumeric, hyphens or underscores')
                print(workload, cur.execute(
                    f"PUT 'file://{file}' @{attr.names([workload])[f'stage_{workload}']}/{table}/{path}/ AUTO_COMPRESS=FALSE OVERWRITE=FALSE"
                ).fetchall())
            print(workload, cur.execute('CALL RAW.LOAD_RAW()').fetchall())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['export', 'load', 'counts'])
    parser.add_argument('--directory', type=Path)
    parser.add_argument('--exported-at')
    parser.add_argument('--suffix', default='')
    parser.add_argument('--duplicate-rows', action='store_true')
    args = parser.parse_args()
    if args.action == 'export':
        export(args.directory, args.exported_at, args.duplicate_rows)
    elif args.action == 'load':
        load(args.directory, args.suffix)
    else:
        for workload in CONSUMERS:
            with connect(workload) as con:
                cur = con.cursor()
                cur.execute('USE SECONDARY ROLES NONE')
                print(workload, cur.execute(f'SELECT COUNT(*) FROM ANALYTICS.{workload.upper()}').fetchall())
                date_column = {'doc_usage_dashboard': 'snapshot_date', 'doc_search_api': 'window_end_date', 'churn_model': 'week_start_date'}[workload]
                print('by date:', cur.execute(f'SELECT {date_column},COUNT(*),HASH_AGG(*) FROM ANALYTICS.{workload.upper()} GROUP BY 1 ORDER BY 1').fetchall())
                if workload == 'doc_usage_dashboard':
                    print(cur.execute("SELECT * FROM ANALYTICS.DOC_USAGE_DASHBOARD WHERE ACCOUNT_ID IN ('00000000-0000-4000-8000-000000000101','00000000-0000-4000-8000-000000000102','00000000-0000-4000-8000-000000000103') ORDER BY SNAPSHOT_DATE,ACCOUNT_ID").fetchall())


if __name__ == '__main__':
    main()
