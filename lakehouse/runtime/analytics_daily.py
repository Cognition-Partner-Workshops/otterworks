"""Daily external analytics with durable extraction and deferred queue acknowledgements."""

import argparse
import fcntl
import gzip
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal

import boto3
import pandas as pd
import psycopg

from .external_settings import expected_bucket_owner, settings, validate_bucket_owner
from .ingest import business_date
from .layout import data_root
from .users_activity_report import SUMMARY_COLUMNS
from .users_exports import atomic_output


QUEUE = 'https://sqs.us-east-1.amazonaws.com/123456789012/otterworks-analytics'
TABLE = 'otterworks-analytics-events'
UPSERT = ('INSERT INTO analytics_daily_summary (' + ', '.join(SUMMARY_COLUMNS) + ', updated_at) VALUES ('
          + ', '.join(['%s'] * len(SUMMARY_COLUMNS)) + ', NOW()) ON CONFLICT (report_date) DO UPDATE SET '
          + ', '.join(name + ' = EXCLUDED.' + name for name in SUMMARY_COLUMNS[1:]) + ', updated_at = NOW()')


def decimal_json(value):
    if isinstance(value, Decimal):
        return int(value) if value == int(value) else float(value)
    raise TypeError(type(value).__name__)


def save(path, value):
    with atomic_output(path) as handle:
        json.dump(value, handle, default=decimal_json)
        handle.flush()
        os.fsync(handle.fileno())


def ready(path, day):
    business_date(day)
    value = json.loads(Path(path).read_text())
    if value != {'business_date': day, 'status': 'ready'}:
        raise ValueError('Analytics readiness marker must attest the requested business date')


def extract(sqs, table, ds):
    events, receipts, processed, errors = [], {}, 0, 0
    while processed < 10000:
        try:
            page = sqs.receive_message(QueueUrl=QUEUE, MaxNumberOfMessages=10, WaitTimeSeconds=5,
                                       AttributeNames=['All'], MessageAttributeNames=['All'])
            errors = 0
        except Exception:
            errors += 1
            if errors >= 3:
                break
            continue
        messages = page.get('Messages', [])
        if not messages:
            break
        for message in messages:
            try:
                event = json.loads(message['Body'])
            except (ValueError, TypeError, KeyError):
                continue
            identity = message['MessageId']
            if identity not in receipts:
                events.append(event)
            receipts[identity] = message['ReceiptHandle']
        processed += len(messages)
    scan = dict(FilterExpression='begins_with(event_date, :ds)', ExpressionAttributeValues={':ds': ds})
    while True:
        page = table.scan(**scan)
        for event in page.get('Items', []):
            events.append({key: decimal_json(value) if isinstance(value, Decimal) else value
                           for key, value in event.items()})
        if not page.get('LastEvaluatedKey'):
            break
        scan['ExclusiveStartKey'] = page['LastEvaluatedKey']
    return events, receipts


def aggregate(events, ds):
    frame = pd.DataFrame(events)
    if 'event_type' in frame.columns and 'eventType' not in frame.columns:
        frame['eventType'] = frame['event_type']
    if 'eventType' not in frame.columns:
        frame['eventType'] = 'unknown'
    frame['resolved_user_id'] = 'unknown'
    for column in ['ownerId', 'editedBy', 'authorId', 'deletedBy', 'userId']:
        if column in frame.columns:
            mask = ((frame['resolved_user_id'] == 'unknown') & frame[column].notna() & (frame[column] != ''))
            frame.loc[mask, 'resolved_user_id'] = frame.loc[mask, column]

    def hour(value):
        try:
            if isinstance(value, str):
                return '%02d' % datetime.fromisoformat(value.replace('Z', '+00:00')).hour
        except ValueError:
            pass
        return '00'

    frame['hour'] = frame['timestamp'].apply(hour) if 'timestamp' in frame.columns else '00'
    actions, hourly = {}, {}
    for _, row in frame.iterrows():
        uid, event, bucket = row['resolved_user_id'], row['eventType'], row['hour']
        user = actions.setdefault(uid, {})
        user[event] = user.get(event, 0) + 1
        counts = hourly.setdefault(bucket, {})
        counts[event] = counts.get(event, 0) + 1
    users = [dict(user_id=uid, actions=counts, total=sum(counts.values())) for uid, counts in actions.items()]
    users.sort(key=lambda user: user['total'], reverse=True)
    users = users[:100]
    hourly = dict(sorted(hourly.items()))
    selected = {name: frame[frame['eventType'] == name] for name in (
        'document_created', 'document_edited', 'comment_added', 'file_uploaded', 'file_shared', 'file_deleted')}

    def distinct(column, names):
        return len(set(value for name in names for value in selected[name][column].dropna().unique())) \
            if column in frame.columns else 0

    documents = dict(created=len(selected['document_created']), edited=len(selected['document_edited']),
                     comments=len(selected['comment_added']))
    files = dict(uploaded=len(selected['file_uploaded']), shared=len(selected['file_shared']),
                 deleted=len(selected['file_deleted']), bytes_uploaded=(
                     int(selected['file_uploaded']['sizeBytes'].fillna(0).sum()) if 'sizeBytes' in frame.columns else 0))
    summary = dict(active_users=len(set(frame['resolved_user_id'].unique()) - {'unknown'}),
                   active_documents=distinct('documentId', ['document_created', 'document_edited']),
                   active_files=distinct('fileId', ['file_uploaded', 'file_shared', 'file_deleted']),
                   total_events=len(events), documents_created=documents['created'],
                   documents_edited=documents['edited'], comments_added=documents['comments'],
                   files_uploaded=files['uploaded'], files_shared=files['shared'],
                   files_deleted=files['deleted'], bytes_uploaded=files['bytes_uploaded'])
    peak = max(hourly.items(), key=lambda item: sum(item[1].values())) if hourly else None
    report = dict(report_type='daily_analytics', report_date=ds, generated_at=ds + 'T00:00:00+00:00',
                  summary=summary, highlights=dict(
                      peak_hour=dict(hour=peak[0], event_count=sum(peak[1].values())) if peak else None,
                      most_active_users=[user['user_id'] for user in users[:5]]),
                  document_metrics=documents, file_metrics=files)
    return summary, hourly, users, report


def acknowledge(sqs, receipts, refresh=False):
    receipts = dict(receipts)
    if refresh and receipts:
        processed = 0
        while processed < 10000:
            messages = sqs.receive_message(QueueUrl=QUEUE, MaxNumberOfMessages=10, WaitTimeSeconds=5,
                                           AttributeNames=['All'], MessageAttributeNames=['All']).get('Messages', [])
            if not messages:
                break
            for message in messages:
                if message['MessageId'] in receipts:
                    receipts[message['MessageId']] = message['ReceiptHandle']
            processed += len(messages)
    entries = [dict(Id=identity, ReceiptHandle=handle) for identity, handle in receipts.items()]
    for offset in range(0, len(entries), 10):
        response = sqs.delete_message_batch(QueueUrl=QUEUE, Entries=entries[offset:offset+10])
        if response.get('Failed'):
            raise RuntimeError('SQS acknowledgement failed')


def execute(config, aws, connect, day, journal, owner):
    ds = business_date(day).isoformat()
    owner = validate_bucket_owner(owner)
    region = config.get('aws', 'region')
    previous = journal.exists()
    state = json.loads(journal.read_text()) if previous else None
    if state is not None and (state.get('version') != 1 or state.get('business_date') != day
                              or state.get('status') not in ('captured', 'written', 'complete')
                              or not isinstance(state.get('events'), list)
                              or not isinstance(state.get('receipts'), dict)):
        raise ValueError('Analytics journal version/date/state mismatch')
    if state and state['status'] == 'complete':
        return state
    sqs = aws.client('sqs', region_name=region)
    if state is None:
        events, receipts = extract(sqs, aws.resource('dynamodb', region_name=region).Table(TABLE), ds)
        state = dict(version=1, business_date=day, status='captured', events=events, receipts=receipts)
        save(journal, state)
    if state['status'] == 'captured' and state['events']:
        summary, hourly, users, report = aggregate(state['events'], ds)
        s3 = aws.client('s3', region_name=region)
        common = dict(Bucket=config.get('s3', 'data_lake_bucket'), ExpectedBucketOwner=owner)
        prefix = config.get('s3', 'analytics_prefix') + f'/year={ds[:4]}/month={ds[5:7]}/day={ds[8:10]}'
        for filename, value in [('summary.json.gz', summary), ('hourly_breakdown.json.gz', hourly)]:
            s3.put_object(**common, Key=prefix + '/' + filename,
                          Body=gzip.compress(json.dumps(value, indent=2).encode(), mtime=0))
        s3.put_object(**common, Key=prefix + '/top_users.jsonl.gz', Body=gzip.compress(
            b''.join(json.dumps(user).encode() + b'\n' for user in users), mtime=0))
        connection = connect(host=config.get('database', 'host'), port=config.getint('database', 'port'),
                             dbname=config.get('database', 'database'), user=config.get('database', 'user'))
        try:
            with connection.cursor() as cursor:
                # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                cursor.execute(UPSERT, [ds] + [summary[name] for name in SUMMARY_COLUMNS[1:]])
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        s3.put_object(**common, Key=f'reports/analytics/daily/{ds}/report.json',
                      Body=json.dumps(report, indent=2).encode())
    state['status'] = 'written'
    save(journal, state)
    acknowledge(sqs, state['receipts'], refresh=previous)
    state['status'] = 'complete'
    save(journal, state)
    return state


def run(config, aws, connect, day, journal, owner_provider=expected_bucket_owner):
    business_date(day)
    owner = validate_bucket_owner(owner_provider())
    journal = Path(journal)
    journal.parent.mkdir(parents=True, exist_ok=True)
    with journal.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return execute(config, aws, connect, day, journal, owner)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--business-date', required=True)
    parser.add_argument('--ready', required=True, type=Path)
    args = parser.parse_args()
    ready(args.ready, args.business_date)
    config, secrets = settings('analytics_daily.py', boto3)
    run(config, boto3, lambda **kwargs: psycopg.connect(password=secrets['ETL_DB_PASSWORD'], **kwargs),
        args.business_date, data_root() / 'transactions/analytics' / (args.business_date + '.json'))


if __name__ == '__main__':
    main()
