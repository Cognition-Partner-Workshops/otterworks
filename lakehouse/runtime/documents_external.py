"""Injectable documents maintenance tasks; live runs retain legacy side effects."""

import argparse
import configparser
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import boto3
import requests

from .ingest import business_date
from .layout import data_root


def load_config():
    path = Path(os.environ.get('ETL_CONFIG_PATH', '/opt/etl/config.ini'))
    config = configparser.ConfigParser()
    if not config.read(path):
        raise RuntimeError(f'ETL configuration not found: {path}')
    return config


def required_secret(name):
    value = os.environ.get(name)
    if not value or not value.strip():
        raise RuntimeError(f'Required ETL secret {name} is missing or empty')
    return value


def expected_bucket_owner():
    owner = os.environ.get('ETL_S3_BUCKET_OWNER', '')
    if not re.fullmatch(r'\d{12}', owner):
        raise RuntimeError('ETL_S3_BUCKET_OWNER must be set to the 12-digit AWS account id that owns the ETL buckets')
    return owner


def poll(http, base, headers, response, seconds, timer):
    uid = response.json().get('taskUid')
    if uid is None:
        return
    deadline = timer.monotonic() + seconds
    while timer.monotonic() < deadline:
        result = http.get(f'{base}/tasks/{uid}', headers=headers)
        result.raise_for_status()
        if result.json().get('status') in ('succeeded', 'failed'):
            return
        timer.sleep(1)


def reindex(config, http, api_key, timer=time):
    document_url = config.get('services', 'document_service_url')
    file_url = config.get('services', 'file_service_url')
    base = config.get('services', 'meilisearch_url')
    headers = {'Content-Type': 'application/json'}
    if api_key:
        headers['Authorization'] = 'Bearer ' + api_key
    for index in ('documents', 'files'):
        try:
            response = http.delete(f'{base}/indexes/{index}', headers=headers)
            if response.ok:
                poll(http, base, headers, response, 60, timer)
        except BaseException:
            print('Index delete failed; continuing as in legacy', flush=True)
    for index in ('documents', 'files'):
        response = http.post(base + '/indexes', headers=headers,
                             data=json.dumps({'uid': index, 'primaryKey': 'id'}))
        response.raise_for_status()
        poll(http, base, headers, response, 60, timer)
    ranking = ['words', 'typo', 'proximity', 'attribute', 'sort', 'exactness']
    settings = {
        'documents': {
            'searchableAttributes': ['title', 'content', 'tags'],
            'filterableAttributes': ['type', 'owner_id', 'tags', 'created_at', 'updated_at'],
            'sortableAttributes': ['updated_at', 'created_at'], 'rankingRules': ranking},
        'files': {
            'searchableAttributes': ['name', 'tags', 'mime_type'],
            'filterableAttributes': ['type', 'owner_id', 'mime_type', 'folder_id', 'tags', 'created_at', 'updated_at'],
            'sortableAttributes': ['updated_at', 'created_at', 'size'], 'rankingRules': ranking},
    }
    for index, value in settings.items():
        response = http.patch(f'{base}/indexes/{index}/settings', headers=headers, data=json.dumps(value))
        response.raise_for_status()
        poll(http, base, headers, response, 60, timer)
    counts = {}
    for index, service, size_key in [('documents', document_url, 'size'),
                                      ('files', file_url, 'page_size')]:
        count, page = 0, 1
        while True:
            response = http.get(service + '/api/v1/' + index,
                                params={'page': page, size_key: 100})
            response.raise_for_status()
            payload = response.json()
            records = payload.get(index, payload.get('items', []))
            if not records:
                break
            batch = []
            for record in records:
                if index == 'documents':
                    row = dict(id=record.get('document_id', record.get('id', '')),
                               title=record.get('title', ''), content=record.get('content', ''),
                               owner_id=record.get('owner_id', ''), tags=record.get('tags', []), type='document',
                               created_at=record.get('created_at'), updated_at=record.get('updated_at'))
                else:
                    row = dict(id=record.get('file_id', record.get('id', '')),
                               name=record.get('file_name', record.get('name', '')),
                               owner_id=record.get('owner_id', ''), mime_type=record.get('mime_type', ''),
                               folder_id=record.get('folder_id', ''), size=record.get('size_bytes', record.get('size', 0)),
                               tags=record.get('tags', []), type='file', created_at=record.get('created_at'),
                               updated_at=record.get('updated_at'))
                batch.append(row)
            response = http.post(f'{base}/indexes/{index}/documents', headers=headers, data=json.dumps(batch))
            response.raise_for_status()
            poll(http, base, headers, response, 120, timer)
            count += len(records)
            if len(records) < 100:
                break
            page += 1
        counts[index] = count
    actual = {}
    for index in ('documents', 'files'):
        response = http.get(f'{base}/indexes/{index}/stats', headers=headers)
        response.raise_for_status()
        actual[index] = response.json().get('numberOfDocuments', 0)
    if actual != counts:
        raise SystemExit(1)
    return counts


def cleanup(config, aws, owner_provider=expected_bucket_owner, clock=datetime):
    region = config.get('aws', 'region')
    source = config.get('s3', 'file_storage_bucket')
    quarantine = config.get('s3', 'quarantine_bucket')
    reports = config.get('s3', 'data_lake_bucket')
    day = clock.now(tz=timezone.utc).strftime('%Y-%m-%d')
    owner = owner_provider()
    s3 = aws.client('s3', region_name=region)
    objects = []
    for page in s3.get_paginator('list_objects_v2').paginate(Bucket=source, Prefix='files/'):
        objects.extend(dict(key=obj['Key'], size=obj['Size'], last_modified=obj['LastModified'].isoformat())
                       for obj in page.get('Contents', []))
    table = aws.resource('dynamodb', region_name=region).Table('otterworks-file-metadata')
    references, scan = set(), {'ProjectionExpression': 's3_key'}
    while True:
        response = table.scan(**scan)
        references.update(item.get('s3_key', '') for item in response.get('Items', []) if item.get('s3_key', ''))
        last = response.get('LastEvaluatedKey')
        if not last:
            break
        scan['ExclusiveStartKey'] = last
    orphaned = [obj for obj in objects if obj['key'] not in references]
    moved = failed = 0
    for obj in orphaned:
        try:
            s3.copy_object(Bucket=quarantine, ExpectedBucketOwner=owner, ExpectedSourceBucketOwner=owner,
                           Key=f'quarantined/{day}/{obj["key"]}',
                           CopySource={'Bucket': source, 'Key': obj['key']}, MetadataDirective='COPY')
            s3.delete_object(Bucket=source, ExpectedBucketOwner=owner, Key=obj['key'])
            moved += 1
        except Exception:
            failed += 1
    total_bytes = sum(obj['size'] for obj in objects)
    orphan_bytes = sum(obj['size'] for obj in orphaned)
    savings = orphan_bytes / (1024 ** 3)
    report = {
        'report_type': 'storage_cleanup', 'report_date': day,
        'generated_at': clock.now(tz=timezone.utc).isoformat(),
        'inventory': {'total_objects': len(objects), 'total_size_bytes': total_bytes,
                      'total_size_gb': round(total_bytes / (1024 ** 3), 4)},
        'orphans': {'orphaned_objects': len(orphaned), 'orphaned_bytes': orphan_bytes,
                    'orphaned_size_gb': round(savings, 4),
                    'orphan_percentage': round(len(orphaned) / len(objects) * 100 if objects else 0, 2)},
        'cleanup': {'objects_quarantined': moved, 'objects_failed': failed, 'quarantine_bucket': quarantine},
        'savings': {'storage_freed_gb': round(savings, 4),
                    'estimated_monthly_savings_usd': round(savings * 0.023, 4)},
    }
    owner = owner_provider()
    aws.client('s3', region_name=region).put_object(
        Bucket=reports, ExpectedBucketOwner=owner, Key=f'reports/storage-cleanup/{day}/report.json',
        Body=json.dumps(report, indent=2).encode('utf-8'))
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--job', choices=['search_reindex_weekly', 'storage_cleanup_daily'], required=True)
    parser.add_argument('--business-date', required=True)
    args = parser.parse_args()
    business_date(args.business_date)
    config = load_config()
    if args.job == 'search_reindex_weekly':
        result = reindex(config, requests, required_secret('ETL_MEILISEARCH_API_KEY'))
    else:
        result = cleanup(config, boto3)
    output = data_root() / 'external_runs' / args.business_date
    output.mkdir(parents=True, exist_ok=True)
    temporary = output / (args.job + '.tmp')
    temporary.write_text(json.dumps(result, indent=2) + '\n')
    os.replace(temporary, output / (args.job + '.json'))


if __name__ == '__main__':
    main()
