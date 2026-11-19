"""Strict in-memory service contracts: no network, credentials or cloud access."""

import copy
import hashlib
import json
from datetime import datetime, timezone
from urllib.parse import urlsplit


class FakeHTTPError(RuntimeError):
    pass


class Response:
    def __init__(self, payload, status=200):
        self.payload, self.status_code = payload, status
        self.ok = status < 400

    def json(self):
        return copy.deepcopy(self.payload)

    def raise_for_status(self):
        if not self.ok:
            raise FakeHTTPError(f'fixture HTTP {self.status_code}')


class Timer:
    def __init__(self):
        self.elapsed = 0

    def monotonic(self):
        return self.elapsed

    def sleep(self, seconds):
        self.elapsed += seconds


def frozen_datetime(value):
    instant = datetime.fromisoformat(value)

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)

    return FrozenDatetime


class HTTP:
    def __init__(self, scenario):
        self.scenario = scenario
        self.actions, self.tasks = [], {}
        self.indexes = {name: {'primaryKey': 'id', 'settings': {}, 'documents': {'stale': {'id': 'stale'}}}
                        for name in ('documents', 'files')}

    def task(self, operation):
        if self.scenario.get('no_task_uid'):
            operation()
            return Response({})
        uid = str(len(self.tasks) + 1)
        self.tasks[uid] = [operation, 0, False]
        return Response({'taskUid': int(uid)})

    def request(self, method, url, headers=None, data=None, params=None):
        parsed = urlsplit(url)
        if parsed.hostname not in ('documents.fixture.invalid', 'files.fixture.invalid', 'search.fixture.invalid'):
            raise AssertionError('Unexpected fake HTTP endpoint')
        safe_headers = {key: '[REDACTED SECRET]' if key.lower() == 'authorization' else value
                        for key, value in (headers or {}).items()}
        self.actions.append(dict(method=method, url=url, headers=safe_headers, params=copy.deepcopy(params),
                                 data=json.loads(data) if data is not None else None))
        path = parsed.path.strip('/').split('/')
        failure = self.scenario.get('search_failure')
        if path[0] == 'tasks' and method == 'GET':
            task = self.tasks[path[1]]
            task[1] += 1
            status = ('enqueued' if self.scenario.get('never_complete') or self.scenario.get('queued') and task[1] == 1
                      else self.scenario.get('task_status', 'succeeded'))
            if status == 'succeeded' and not task[2]:
                task[0]()
                task[2] = True
            return Response({'status': status, 'error': {'message': 'fixture task failure'}})
        if path[:2] == ['api', 'v1'] and method == 'GET':
            if failure == 'service_http':
                return Response({}, 503)
            name = path[2]
            expected_size = 'size' if name == 'documents' else 'page_size'
            assert set(params) == {'page', expected_size} and params[expected_size] == 100
            page = params['page']
            records = self.scenario.get(name, [])[(page - 1) * 100:page * 100]
            return Response({name if page % 2 else 'items': records})
        if path == ['indexes'] and method == 'POST':
            if failure == 'create_http':
                return Response({}, 500)
            payload = json.loads(data)
            return self.task(lambda: self.indexes.__setitem__(payload['uid'],
                             {'primaryKey': payload['primaryKey'], 'settings': {}, 'documents': {}}))
        if path[0] == 'indexes':
            name = path[1]
            if method == 'DELETE' and len(path) == 2:
                if failure == 'delete_http':
                    raise FakeHTTPError('fixture delete failure')
                return self.task(lambda: self.indexes.pop(name, None))
            if method == 'PATCH' and path[2] == 'settings':
                if failure == 'settings_http':
                    return Response({}, 500)
                return self.task(lambda: self.indexes[name].__setitem__('settings', json.loads(data)))
            if method == 'POST' and path[2] == 'documents':
                if failure == 'index_http':
                    return Response({}, 500)
                def add():
                    for row in json.loads(data):
                        self.indexes[name]['documents'][str(row['id'])] = row
                return self.task(add)
            if method == 'GET' and path[2] == 'stats':
                return Response({'numberOfDocuments': len(self.indexes.get(name, {}).get('documents', {}))
                                 + int(bool(self.scenario.get('bad_stats')))})
        raise AssertionError(f'Unexpected fake HTTP operation: {method} {url}')

    def get(self, url, **kwargs):
        return self.request('GET', url, **kwargs)

    def post(self, url, **kwargs):
        return self.request('POST', url, **kwargs)

    def patch(self, url, **kwargs):
        return self.request('PATCH', url, **kwargs)

    def delete(self, url, **kwargs):
        return self.request('DELETE', url, **kwargs)


class AWS:
    def __init__(self, scenario):
        self.scenario, self.actions = scenario, []
        self.objects = {obj['key']: copy.deepcopy(obj) for obj in scenario.get('objects', [])}
        self.quarantine, self.reports = {}, {}

    def client(self, service, **kwargs):
        assert service == 's3'
        self.actions.append(dict(operation='client', service=service, **kwargs))
        return self

    def resource(self, service, **kwargs):
        assert service == 'dynamodb'
        self.actions.append(dict(operation='resource', service=service, **kwargs))
        return self

    def Table(self, name):
        assert name == 'otterworks-file-metadata'
        self.actions.append(dict(operation='table', name=name))
        return self

    def scan(self, **kwargs):
        self.actions.append(dict(operation='scan', **copy.deepcopy(kwargs)))
        assert kwargs['ProjectionExpression'] == 's3_key'
        if self.scenario.get('scan_error'):
            raise RuntimeError('fixture scan failure')
        offset = kwargs.get('ExclusiveStartKey', {}).get('offset', 0)
        records = self.scenario.get('references', [])
        result = {'Items': records[offset:offset + 2]}
        if offset + 2 < len(records):
            result['LastEvaluatedKey'] = {'offset': offset + 2}
        return result

    def get_paginator(self, name):
        assert name == 'list_objects_v2'
        self.actions.append(dict(operation='paginator', name=name))
        return self

    def paginate(self, **kwargs):
        self.actions.append(dict(operation='list', **kwargs))
        if self.scenario.get('list_error'):
            raise RuntimeError('fixture list failure')
        objects = [obj for obj in self.objects.values() if obj['key'].startswith(kwargs['Prefix'])]
        if not objects:
            yield {}
        for offset in range(0, len(objects), 2):
            yield {'Contents': [dict(Key=obj['key'], Size=obj['size'],
                                     LastModified=datetime.fromisoformat(obj['last_modified']))
                                for obj in objects[offset:offset + 2]]}

    def copy_object(self, **kwargs):
        self.actions.append(dict(operation='copy', **copy.deepcopy(kwargs)))
        assert kwargs['ExpectedBucketOwner'] == kwargs['ExpectedSourceBucketOwner'] == '123456789012'
        source = kwargs['CopySource']['Key']
        if source in self.scenario.get('copy_failures', []):
            raise RuntimeError('fixture copy failure')
        self.quarantine[kwargs['Key']] = copy.deepcopy(self.objects[source])

    def delete_object(self, **kwargs):
        self.actions.append(dict(operation='delete', **kwargs))
        assert kwargs['ExpectedBucketOwner'] == '123456789012'
        if kwargs['Key'] in self.scenario.get('delete_failures', []):
            raise RuntimeError('fixture delete failure')
        del self.objects[kwargs['Key']]

    def put_object(self, **kwargs):
        body = kwargs.pop('Body')
        self.actions.append(dict(operation='put', **kwargs,
                                 body_sha256=hashlib.sha256(body).hexdigest(), body=json.loads(body)))
        assert kwargs['ExpectedBucketOwner'] == '123456789012'
        if self.scenario.get('report_error'):
            raise RuntimeError('fixture report failure')
        self.reports[kwargs['Key']] = body.decode('utf-8')
