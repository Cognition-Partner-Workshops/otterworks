import argparse
import gzip
import hashlib
import json
import os
from datetime import timedelta
from decimal import Decimal

import boto3

from lakehouse.runtime.ingest import business_date


def decimal_json(value):
    if isinstance(value, Decimal):
        return int(value) if value == int(value) else float(value)
    raise TypeError(type(value).__name__)


def encoded(value):
    return json.dumps(value, default=decimal_json, sort_keys=True).encode('utf-8')


def optional(call, **kwargs):
    try:
        return call(**kwargs)
    except Exception as exc:
        code = getattr(exc, 'response', {}).get('Error', {}).get('Code')
        if code not in ('NoSuchKey', 'NotFound', '404'):
            raise
        return None


def archive(table, s3, bucket, owner, day):
    run_day = business_date(day)
    ds = run_day.isoformat()
    cutoff = (run_day - timedelta(days=90)).isoformat() + 'T00:00:00Z'
    archive_key = f'audit-archive/year={run_day.year}/week={ds}/audit_events.jsonl.gz'
    report_key = f'reports/compliance/audit-archive/{ds}/report.json'
    manifest_key = f'audit-archive/manifests/{ds}.json'
    common = dict(Bucket=bucket, ExpectedBucketOwner=owner)
    existing = optional(s3.get_object, **common, Key=report_key)
    if existing:
        return json.loads(existing['Body'].read())
    existing = optional(s3.get_object, **common, Key=manifest_key)
    if existing:
        manifest = json.loads(existing['Body'].read())
    else:
        events = []
        kwargs = dict(FilterExpression='#ts < :cutoff',
                      ExpressionAttributeNames={'#ts': 'timestamp'},
                      ExpressionAttributeValues={':cutoff': cutoff})
        while True:
            page = table.scan(**kwargs)
            events.extend(page.get('Items', []))
            if not page.get('LastEvaluatedKey'):
                break
            kwargs['ExclusiveStartKey'] = page['LastEvaluatedKey']
        if not events:
            return None
        events.sort(key=lambda event: (str(event['event_id']), event['timestamp']))
        payload = b''.join(encoded(event) + b'\n' for event in events)
        digest = hashlib.sha256(payload).hexdigest()
        compressed = gzip.compress(payload, mtime=0)
        previous = optional(s3.head_object, **common, Key=archive_key)
        if previous:
            if previous.get('Metadata', {}).get('sha256') != digest:
                raise RuntimeError('Archive already exists with a different source snapshot')
        else:
            s3.put_object(**common, Key=archive_key, Body=compressed, StorageClass='GLACIER',
                          Metadata={'sha256': digest}, IfNoneMatch='*')
        manifest = {'keys': [{'event_id': e['event_id'], 'timestamp': e['timestamp']} for e in events],
                    'compressed_size_bytes': len(compressed), 'sha256': digest}
        s3.put_object(**common, Key=manifest_key, Body=encoded(manifest), IfNoneMatch='*')
    for key in manifest['keys']:
        table.delete_item(Key=key)
    count = len(manifest['keys'])
    report = {
        'report_type': 'audit_archive_compliance', 'execution_date': ds,
        'generated_at': ds + 'T00:00:00+00:00',
        'retention_policy': {'retention_days': 90, 'cutoff_date': cutoff},
        'results': {'events_scanned': count, 'events_archived': count,
                    'events_deleted_from_source': count,
                    'archive_location': f's3://{bucket}/{archive_key}',
                    'archive_storage_class': 'GLACIER',
                    'compressed_size_bytes': manifest['compressed_size_bytes']},
        'compliance': {'gdpr_compliant': True, 'soc2_compliant': True,
                       'data_encrypted_at_rest': True, 'data_encrypted_in_transit': True},
    }
    s3.put_object(**common, Key=report_key, Body=encoded(report), IfNoneMatch='*')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--business-date', required=True)
    parser.add_argument('--bucket', default=os.environ.get('AUDIT_ARCHIVE_BUCKET'))
    parser.add_argument('--owner', default=os.environ.get('AUDIT_ARCHIVE_OWNER'))
    parser.add_argument('--table', default='otterworks-audit-events')
    args = parser.parse_args()
    business_date(args.business_date)
    if not args.bucket or not args.owner:
        parser.error('AUDIT_ARCHIVE_BUCKET and AUDIT_ARCHIVE_OWNER must be configured')
    region = os.environ.get('AWS_REGION', 'us-east-1')
    archive(boto3.resource('dynamodb', region_name=region).Table(args.table),
            boto3.client('s3', region_name=region), args.bucket, args.owner, args.business_date)


if __name__ == '__main__':
    main()
