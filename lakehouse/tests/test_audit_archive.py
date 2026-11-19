import copy
import gzip
import importlib.util
import io
import json
import sys
from configparser import ConfigParser
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import boto3
import pytest

from lakehouse.audit.archive import archive
from lakehouse.runtime.layout import ROOT


class Missing(Exception):
    response = {'Error': {'Code': 'NoSuchKey'}}


class FakeS3:
    def __init__(self):
        self.objects = {}

    def get_object(self, **args):
        item = self.objects.get(args['Key'])
        if item is None:
            raise Missing()
        if item.get('StorageClass') == 'GLACIER':
            raise RuntimeError('Glacier requires restore')
        return {'Body': io.BytesIO(item['Body'])}

    def head_object(self, **args):
        if args['Key'] not in self.objects:
            raise Missing()
        return self.objects[args['Key']]

    def put_object(self, **args):
        assert args['ExpectedBucketOwner'] == '123456789012'
        if args.get('IfNoneMatch') == '*' and args['Key'] in self.objects:
            raise RuntimeError('Conditional write conflict')
        self.objects[args['Key']] = args


class FakeTable:
    def __init__(self, events):
        self.events = copy.deepcopy(events)
        self.fail_after = None
        self.deleted = 0

    def scan(self, **args):
        cutoff = args['ExpressionAttributeValues'][':cutoff']
        rows = [e for e in self.events if e['timestamp'] < cutoff]
        offset = args.get('ExclusiveStartKey', {}).get('offset', 0)
        page = {'Items': rows[offset:offset+1]}
        if len(rows) > offset+1:
            page['LastEvaluatedKey'] = {'offset': offset+1}
        return page

    def delete_item(self, Key):
        if self.fail_after is not None and self.deleted >= self.fail_after:
            raise RuntimeError('delete interrupted')
        self.events = [e for e in self.events if any(e[k] != v for k, v in Key.items())]
        self.deleted += 1

    def batch_writer(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


EVENTS = [
    {'event_id': 'one', 'timestamp': '2026-08-10T23:59:59Z', 'amount': Decimal('1.25')},
    {'event_id': 'two', 'timestamp': '2026-01-01T00:00:00Z', 'amount': Decimal('2')},
    {'event_id': 'boundary', 'timestamp': '2026-08-11T00:00:00Z'},
    {'event_id': 'current', 'timestamp': '2026-11-09T00:00:00Z'},
]


def run_legacy(monkeypatch, events):
    table, s3 = FakeTable(events), FakeS3()
    config = ConfigParser()
    config.read_dict({'aws': {'region': 'us-east-1'}, 's3': {'archive_bucket': 'archive'}})
    monkeypatch.setitem(sys.modules, 'bucket_owner', SimpleNamespace(
        expected_bucket_owner=lambda: '123456789012'))
    monkeypatch.setitem(sys.modules, 'runtime_config', SimpleNamespace(load_config=lambda: config))
    monkeypatch.setattr(boto3, 'resource', lambda *a, **k: SimpleNamespace(Table=lambda _: table))
    monkeypatch.setattr(boto3, 'client', lambda *a, **k: s3)
    path = ROOT.parent / 'etl/scripts/audit_archive_weekly.py'
    spec = importlib.util.spec_from_file_location('legacy_audit_archive', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 9, 12, tzinfo=timezone.utc).astimezone(tz) if tz else cls(2026, 11, 9, 12)

    monkeypatch.setattr(module, 'datetime', Frozen)
    try:
        module.main()
    except SystemExit as exc:
        assert exc.code == 0
    return table, s3


def test_archive_legacy_file_parity(monkeypatch):
    legacy_table, legacy_s3 = run_legacy(monkeypatch, EVENTS)
    table, s3 = FakeTable(EVENTS), FakeS3()
    archive(table, s3, 'archive', '123456789012', '20261109')
    key = 'audit-archive/year=2026/week=2026-11-09/audit_events.jsonl.gz'
    decoded = lambda client: sorted(
        [json.loads(line) for line in gzip.decompress(client.objects[key]['Body']).splitlines()],
        key=lambda row: row['event_id'])
    assert decoded(s3) == decoded(legacy_s3)
    assert s3.objects[key]['StorageClass'] == legacy_s3.objects[key]['StorageClass'] == 'GLACIER'
    report_key = 'reports/compliance/audit-archive/2026-11-09/report.json'
    reports = [json.loads(client.objects[report_key]['Body']) for client in (s3, legacy_s3)]
    for report in reports:
        del report['generated_at']
        del report['results']['compressed_size_bytes']
    assert reports[0] == reports[1]
    assert table.events == legacy_table.events == EVENTS[2:]
    previous = copy.deepcopy(s3.objects)
    archive(table, s3, 'archive', '123456789012', '20261109')
    assert s3.objects == previous


def test_archive_empty_and_missing_or_invalid_date(monkeypatch):
    legacy_table, legacy_s3 = run_legacy(monkeypatch, [])
    table, s3 = FakeTable([]), FakeS3()
    assert archive(table, s3, 'archive', '123456789012', '20261109') is None
    assert not s3.objects and not legacy_s3.objects
    with pytest.raises(ValueError):
        archive(table, s3, 'archive', '123456789012', 'invalid')


def test_archive_resumes_partial_deletion_without_reading_glacier():
    table, s3 = FakeTable(EVENTS), FakeS3()
    table.fail_after = 1
    with pytest.raises(RuntimeError, match='delete interrupted'):
        archive(table, s3, 'archive', '123456789012', '20261109')
    assert not any(key.endswith('report.json') for key in s3.objects)
    payload = next(obj['Body'] for key, obj in s3.objects.items() if key.endswith('.gz'))
    table.fail_after = None
    report = archive(table, s3, 'archive', '123456789012', '20261109')
    assert report['results']['events_deleted_from_source'] == 2
    assert table.events == EVENTS[2:]
    assert next(obj['Body'] for key, obj in s3.objects.items() if key.endswith('.gz')) == payload


def test_archive_upload_failure_never_deletes_source(monkeypatch):
    table, s3 = FakeTable(EVENTS), FakeS3()
    def fail(**kwargs):
        raise RuntimeError('upload failed')
    monkeypatch.setattr(s3, 'put_object', fail)
    with pytest.raises(RuntimeError, match='upload failed'):
        archive(table, s3, 'archive', '123456789012', '20261109')
    assert table.events == EVENTS
