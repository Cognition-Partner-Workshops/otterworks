"""Shared settings and argv-only dispatch for the converted external jobs."""

import argparse
import configparser
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from .ingest import business_date


JOBS = {
    'analytics_daily.py': ('lakehouse.runtime.analytics_daily', ('ETL_DB_PASSWORD',)),
    'audit_archive_weekly.py': ('lakehouse.audit.archive', ()),
    'search_reindex_weekly.py': ('lakehouse.runtime.documents_external', ('ETL_MEILISEARCH_API_KEY',)),
    'storage_cleanup_daily.py': ('lakehouse.runtime.documents_external', ()),
    'user_activity_daily.py': ('lakehouse.runtime.users_activity_report', ()),
}


def check_job(job):
    if job not in JOBS:
        raise ValueError('Unknown external job')
    return JOBS[job]


def load_config():
    path = Path(os.environ.get('ETL_CONFIG_PATH', Path(__file__).with_name('external.ini')))
    config = configparser.ConfigParser()
    if not config.read(path):
        raise RuntimeError(f'ETL configuration not found: {path}')
    return config


def required_secret(name):
    value = os.environ.get(name)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f'Required ETL secret {name} is missing or empty')
    return value


def secrets_for(job, client):
    _, names = check_job(job)
    if not names:
        return {}
    response = client.get_secret_value(SecretId=os.environ.get(
        'ETL_SECRET_ID', 'otterworks/etl/' + job.removesuffix('.py')))
    try:
        values = json.loads(response['SecretString'])
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError('ETL runtime secret must be a JSON object in SecretString') from exc
    if not isinstance(values, dict):
        raise RuntimeError('ETL runtime secret must be a JSON object')
    if any(not isinstance(values.get(name), str) or not values[name].strip() for name in names):
        raise RuntimeError('ETL runtime secret must contain nonempty ' + ', '.join(names))
    return {name: values[name] for name in names}


def settings(job, aws):
    _, names = check_job(job)
    config = load_config()
    if names:
        if os.environ.get('ETL_SECRET_ID') or any(name not in os.environ for name in names):
            client = aws.client('secretsmanager', region_name=config.get('aws', 'region'))
            values = secrets_for(job, client)
        else:
            values = {name: required_secret(name) for name in names}
    else:
        values = {}
    return config, values


def validate_bucket_owner(owner):
    if not isinstance(owner, str) or not re.fullmatch(r'[0-9]{12}', owner):
        raise RuntimeError('ETL_S3_BUCKET_OWNER must be set to the 12-digit AWS account id that owns the ETL buckets')
    return owner


def expected_bucket_owner():
    return validate_bucket_owner(os.environ.get('ETL_S3_BUCKET_OWNER', ''))


def command(job, day, source=None, ready=None):
    module, _ = check_job(job)
    business_date(day)
    argv = [sys.executable, '-m', module, '--business-date', day]
    if job in ('search_reindex_weekly.py', 'storage_cleanup_daily.py'):
        argv += ['--job', job.removesuffix('.py')]
    if job == 'user_activity_daily.py':
        if source is None:
            raise ValueError('User activity requires a staged source')
        argv += ['--source', str(source)]
    if job == 'analytics_daily.py':
        if ready is None:
            raise ValueError('Analytics requires a readiness marker')
        argv += ['--ready', str(ready)]
    return argv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job', required=True, choices=JOBS)
    parser.add_argument('--business-date', required=True)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--ready', type=Path)
    args = parser.parse_args()
    subprocess.run(command(args.job, args.business_date, args.source, args.ready), check=True, shell=False)


if __name__ == '__main__':
    main()
