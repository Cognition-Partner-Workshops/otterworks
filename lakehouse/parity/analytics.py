"""Run unchanged analytics source and the native runtime against identical strict fakes."""

import argparse
import copy
import gzip
import hashlib
import importlib.util
import io
import json
import os
import re
import sys
from contextlib import redirect_stdout
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from lakehouse.runtime import analytics_daily as native
from lakehouse.runtime.external_settings import load_config
from lakehouse.runtime.ingest import business_date
from lakehouse.runtime.layout import ROOT, data_root
from lakehouse.runtime.users_activity_report import SUMMARY_COLUMNS


OUTPUTS = ('summary', 'hourly', 'top_users', 'report', 'postgres')


class Services:
    def __init__(self, scenario, day):
        self.scenario = copy.deepcopy(scenario)
        self.day = business_date(day).isoformat()
        self.messages = [dict(MessageId=str(i), ReceiptHandle='receipt-' + str(i),
                              Body=value if isinstance(value, str) else json.dumps(value))
                         for i, value in enumerate(scenario.get('sqs', []))]
        self.offset = 0
        self.deleted, self.objects, self.rows, self.operations = [], {}, {}, []
        self.fail_key = None
        self.fail_db = False
        self.fail_delete = False
        self.fail_scan = False
        self.receive_failures = 0

    def client(self, name, **kwargs):
        assert name in ('sqs', 's3') and kwargs == {'region_name': 'us-east-1'}
        return self

    def resource(self, name, **kwargs):
        assert name == 'dynamodb' and kwargs == {'region_name': 'us-east-1'}
        return self

    def Table(self, name):
        assert name == native.TABLE
        return self

    def receive_message(self, **kwargs):
        assert kwargs == dict(QueueUrl=native.QUEUE, MaxNumberOfMessages=10, WaitTimeSeconds=5,
                              AttributeNames=['All'], MessageAttributeNames=['All'])
        if self.receive_failures:
            self.receive_failures -= 1
            raise RuntimeError('receive failed')
        page = self.messages[self.offset:self.offset+10]
        self.offset += len(page)
        return {'Messages': copy.deepcopy(page)}

    def delete_message_batch(self, **kwargs):
        assert kwargs['QueueUrl'] == native.QUEUE and len(kwargs['Entries']) <= 10
        self.operations.append('sqs:delete')
        if self.fail_delete:
            return {'Failed': [dict(Id=entry['Id'], Code='InternalError') for entry in kwargs['Entries']]}
        for entry in kwargs['Entries']:
            assert any(message['MessageId'] == entry['Id'] and message['ReceiptHandle'] == entry['ReceiptHandle']
                       for message in self.messages)
            self.deleted.append(entry['Id'])
        return {'Successful': [{'Id': entry['Id']} for entry in kwargs['Entries']]}

    def scan(self, **kwargs):
        assert kwargs['FilterExpression'] == 'begins_with(event_date, :ds)'
        assert kwargs['ExpressionAttributeValues'] == {':ds': self.day}
        if self.fail_scan:
            raise RuntimeError('scan failed')

        def decimals(value):
            if isinstance(value, dict):
                if set(value) == {'$decimal'}:
                    return Decimal(value['$decimal'])
                return {key: decimals(item) for key, item in value.items()}
            return value

        records = [decimals(row) for row in self.scenario.get('dynamo', [])
                   if row.get('event_date', '').startswith(self.day)]
        offset = kwargs.get('ExclusiveStartKey', {}).get('offset', 0)
        result = {'Items': records[offset:offset+2]}
        if offset+2 < len(records):
            result['LastEvaluatedKey'] = {'offset': offset+2}
        return result

    def put_object(self, **kwargs):
        assert set(kwargs) == {'Bucket', 'ExpectedBucketOwner', 'Key', 'Body'}
        assert kwargs['Bucket'] == 'fixture-analytics' and kwargs['ExpectedBucketOwner'] == '123456789012'
        self.operations.append('s3:' + kwargs['Key'])
        if self.fail_key and self.fail_key in kwargs['Key']:
            raise RuntimeError('put failed')
        self.objects[kwargs['Key']] = bytes(kwargs['Body'])

    def connect(self, **kwargs):
        service = self

        class Connection:
            pending = None

            def cursor(self):
                return self

            def execute(self, sql, values):
                assert 'ON CONFLICT (report_date) DO UPDATE' in sql
                columns = re.search(r'analytics_daily_summary\s*\((.*?)\)\s*VALUES', sql, re.S).group(1)
                assert [value.strip() for value in columns.split(',')] == list(SUMMARY_COLUMNS) + ['updated_at']
                assert len(values) == len(SUMMARY_COLUMNS)
                self.pending = dict(zip(SUMMARY_COLUMNS, values))

            def commit(self):
                service.operations.append('pg:commit')
                if service.fail_db:
                    raise RuntimeError('database failed')
                service.rows[self.pending['report_date']] = self.pending

            def rollback(self):
                self.pending = None

            def close(self):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        return Connection()


def fixture(day):
    ds = business_date(day).isoformat()
    event = dict(eventType='file_uploaded', event_date=ds, ownerId='owner', editedBy='ignored',
                 timestamp=ds+'T23:00:00-05:00', fileId='f1', sizeBytes=12)
    normal = [event, dict(eventType='document_created', userId='u2', documentId='d1', timestamp='bad'),
              dict(eventType='document_edited', editedBy='u2', documentId='d1', timestamp=ds+'T03:00:00Z'),
              dict(eventType='comment_added', authorId='u3'), dict(eventType='file_shared', fileId='f1'),
              dict(eventType='file_deleted', deletedBy='u4', fileId='f2'), '{bad JSON']
    return dict(version=1, business_date=day, scenarios=[
        dict(name='normal_no_cross_source_dedup', sqs=normal,
             dynamo=[{**event, 'sizeBytes': {'$decimal': '12'}},
                     dict(eventType='file_uploaded', userId='u5', sizeBytes={'$decimal': '1.5'}, event_date=ds),
                     dict(eventType='ignored', event_date='1900-01-01'),
                     dict(eventType='document_created', documentId='', event_date=ds)]),
        dict(name='empty'), dict(name='malformed_json_only', sqs=['{', 'not-json']),
        dict(name='fallback_field', sqs=[dict(event_type='document_created', ownerId='', editedBy='é',
                                            documentId=0, timestamp=None), dict(event_type='custom')]),
        dict(name='missing_fields', sqs=[{}, dict(timestamp=42)]),
        dict(name='mixed_event_columns', sqs=[dict(eventType='file_uploaded', sizeBytes=3),
                                             dict(event_type='document_created', userId='u1')]),
        dict(name='top_100_stable_ties', sqs=[dict(eventType='custom', userId='u'+str(i)) for i in range(105)]),
    ])


def legacy(service, config, day):
    ds = business_date(day)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(ds.year, ds.month, ds.day, tzinfo=timezone.utc) if tz else cls(ds.year, ds.month, ds.day)

    modules = dict(boto3=service, psycopg2=SimpleNamespace(connect=service.connect))
    directory = ROOT.parent / 'etl/scripts'
    for name in ('runtime_config', 'bucket_owner'):
        spec = importlib.util.spec_from_file_location(name, directory / (name+'.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules[name] = module
    with patch.dict(sys.modules, modules), redirect_stdout(io.StringIO()):
        spec = importlib.util.spec_from_file_location('legacy_analytics', directory / 'analytics_daily.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.datetime = Clock
        try:
            module.main()
        except SystemExit as exc:
            if exc.code != 0:
                raise


def outputs(service):
    prefix = 'analytics/daily/year='+service.day[:4]+'/month='+service.day[5:7]+'/day='+service.day[8:10]
    paths = dict(summary=prefix+'/summary.json.gz', hourly=prefix+'/hourly_breakdown.json.gz',
                 top_users=prefix+'/top_users.jsonl.gz', report='reports/analytics/daily/'+service.day+'/report.json')
    result = {}
    for name, key in paths.items():
        raw = service.objects.get(key)
        if raw is not None:
            raw = gzip.decompress(raw) if key.endswith('.gz') else raw
            result[name] = [json.loads(line) for line in raw.splitlines()] if name == 'top_users' else json.loads(raw)
        else:
            result[name] = None
    result['postgres'] = service.rows.get(service.day)
    return result


def prepare(path, day):
    raw = path.read_bytes()
    document = json.loads(raw)
    if document['business_date'] != day or document['version'] != 1:
        raise ValueError('Analytics fixture version/date mismatch')
    root = data_root() / 'analytics_parity' / day
    root.mkdir(parents=True, exist_ok=True)
    config_path = root / 'fixture.ini'
    config_path.write_text('[aws]\nregion=us-east-1\n[database]\nhost=fixture\nport=5432\n'
                           'database=fixture\nuser=fixture\n[s3]\ndata_lake_bucket=fixture-analytics\n'
                           'analytics_prefix=analytics/daily\n')
    env = dict(ETL_CONFIG_PATH=str(config_path), ETL_DB_PASSWORD='fixture-not-a-secret',
               ETL_S3_BUCKET_OWNER='123456789012')
    with patch.dict(os.environ, env):
        config = load_config()
        for side in ('legacy', 'lakehouse'):
            grouped = {name: [] for name in OUTPUTS}
            for scenario in document['scenarios']:
                service = Services(scenario, day)
                if side == 'legacy':
                    legacy(service, config, day)
                else:
                    journal = root / 'journals' / (scenario['name']+'.json')
                    journal.unlink(missing_ok=True)
                    native.run(config, service, service.connect, day, journal)
                for name, payload in outputs(service).items():
                    grouped[name].append(dict(scenario=scenario['name'], payload=payload))
            folder = root / side
            folder.mkdir(exist_ok=True)
            for name, rows in grouped.items():
                with native.atomic_output(folder / (name+'.jsonl')) as handle:
                    handle.writelines(json.dumps(row)+'\n' for row in rows)
            print('analytics.'+side+': executed '+str(len(document['scenarios']))+' scenarios')
    if raw != path.read_bytes():
        raise ValueError('Analytics fixture changed during execution')
    sources = ['etl/scripts/analytics_daily.py', 'etl/scripts/runtime_config.py', 'etl/scripts/bucket_owner.py',
               'lakehouse/runtime/analytics_daily.py', 'lakehouse/runtime/external_settings.py',
               'lakehouse/parity/analytics.py']
    native.save(root / 'provenance.json', dict(fixture_sha256=hashlib.sha256(raw).hexdigest(), business_date=day,
                pandas=native.pd.__version__, network='none: injected SQS/DynamoDB/S3/PostgreSQL',
                sources={name: hashlib.sha256((ROOT.parent / name).read_bytes()).hexdigest() for name in sources}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--business-date', required=True)
    parser.add_argument('--fixture', required=True, type=Path)
    parser.add_argument('--generate', action='store_true')
    args = parser.parse_args()
    if args.generate:
        args.fixture.parent.mkdir(parents=True, exist_ok=True)
        native.save(args.fixture, fixture(args.business_date))
    prepare(args.fixture, args.business_date)


if __name__ == '__main__':
    main()
