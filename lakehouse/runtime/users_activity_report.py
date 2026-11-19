"""Build the 30-day activity report from staged analytics snapshots."""

import argparse
import gzip
import json
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

from pyspark.sql import functions as F

from .ingest import business_date
from .layout import data_root
from .session import create_session
from .users_exports import atomic_output
from .external_settings import check_job, load_config


SUMMARY_COLUMNS = (
    'report_date', 'active_users', 'active_documents', 'active_files', 'total_events',
    'documents_created', 'documents_edited', 'comments_added', 'files_uploaded',
    'files_shared', 'files_deleted', 'bytes_uploaded',
)
LOOKBACK = 30


def top_user_source(day, source):
    return source / 'analytics' / 'daily' / f'year={day:%Y}' / f'month={day:%m}' / f'day={day:%d}' / 'top_users.jsonl.gz'


def top_user_records(entry):
    offset, path = entry
    with gzip.open(path, mode='rt', encoding='utf-8') as source:
        for line_number, line in enumerate(source):
            if line.strip():
                value = json.loads(line)
                yield (value.get('user_id', 'unknown'), value.get('total', 0),
                       value.get('actions', {}), offset, line_number)


def top_users(spark, source, day):
    paths = []
    for offset in range(LOOKBACK):
        path = top_user_source(day - timedelta(days=offset), source)
        try:
            path.stat()
        except FileNotFoundError:
            continue
        paths.append((offset, str(path.resolve())))
    if not paths:
        return []
    records = spark.createDataFrame(
        spark.sparkContext.parallelize(paths).flatMap(top_user_records),
        'user_id STRING, total LONG, actions MAP<STRING,LONG>, offset INT, line_number LONG')
    totals = records.groupBy('user_id').agg(
        F.sum('total').alias('total_actions'), F.count('*').alias('active_days'),
        F.min(F.struct('offset', 'line_number')).alias('first_seen'))
    counts = (records.select('user_id', F.explode('actions').alias('action', 'count'))
              .groupBy('user_id', 'action').agg(F.sum('count').alias('count'))
              .groupBy('user_id').agg(F.map_from_entries(
                  F.collect_list(F.struct('action', 'count'))).alias('actions_by_type')))
    rows = (totals.join(counts, totals.user_id.eqNullSafe(counts.user_id), 'left')
            .orderBy(F.desc('total_actions'), F.asc('first_seen')).limit(500)
            .select(totals.user_id, 'total_actions', 'active_days', 'actions_by_type').collect())
    return [{**row.asDict(), 'actions_by_type': row.actions_by_type or {}} for row in rows]


def build_report(spark, source, day):
    summaries = (spark.read.parquet(str(source / 'daily_summary.parquet')).select(*SUMMARY_COLUMNS)
                 .where(F.col('report_date').between(day - timedelta(days=LOOKBACK), day))
                 .orderBy('report_date').collect())
    if any(row.total_events is None or row.active_users is None for row in summaries):
        raise ValueError('Reporting summaries require non-null total_events and active_users')
    if len({row.report_date for row in summaries}) != len(summaries):
        raise ValueError('Reporting summaries require one row per report_date')
    total_events = sum(row.total_events for row in summaries)
    users = top_users(spark, source, day)
    return {
        'report_type': 'user_activity',
        'report_date': day.isoformat(),
        'generated_at': datetime.combine(day, time(), timezone.utc).isoformat(),
        'lookback_days': LOOKBACK,
        'trends': {
            'total_events': total_events,
            'peak_active_users': max((row.active_users for row in summaries), default=0),
            'avg_daily_events': round(total_events / len(summaries), 2) if summaries else 0,
            'reporting_days': len(summaries),
        },
        'daily_summaries': [row.asDict() for row in summaries],
        'user_summaries': users,
        'top_users': users[:20],
    }


def publish(root, report):
    folder = root / report['report_date']
    users_path = folder / 'user_summaries.jsonl'
    if report['user_summaries']:
        with atomic_output(users_path) as stream:
            for user in report['user_summaries']:
                stream.write(json.dumps(user) + '\n')
    else:
        users_path.unlink(missing_ok=True)

    def report_to(path):
        with atomic_output(path) as stream:
            json.dump(report, stream, indent=2, default=str, sort_keys=True)

    report_to(folder / 'activity_report.json')
    latest = root / 'latest' / 'activity_report.json'
    if not latest.is_file() or json.loads(latest.read_text())['report_date'] <= report['report_date']:
        report_to(latest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--business-date', required=True)
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    check_job('user_activity_daily.py')
    load_config()
    day = business_date(args.business_date)
    spark = create_session()
    try:
        publish(data_root() / 'exports/reports/user-activity', build_report(spark, args.source, day))
    finally:
        spark.stop()


if __name__ == '__main__':
    main()
