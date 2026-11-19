import csv
import io
import threading
from datetime import datetime, timezone

import mongomock
import pytest
from bson.decimal128 import Decimal128
from fastapi.testclient import TestClient
from pymongo.errors import ConnectionFailure

from odl_sync import metrics, sync
from odl_sync.api import PREFIX, create_app
from odl_sync.parity import write_csv


@pytest.fixture
def db():
    db = mongomock.MongoClient().odl
    for i in range(3):
        db.customers.insert_one(dict(_id=f'cus_{i}', source_keys=dict(db2_cust_no=f'C000000{i}', oracle_account_ids=[7000000 + i], crm_contact_id=f'contact-{i}'),
                                     match={'status': 'matched' if i < 2 else 'single-source'},
                                     accounts=[dict(balance=Decimal128('1.20'), opened_at=datetime(2024, 1, 1, tzinfo=timezone.utc))]))
        db.mapping_exceptions.insert_one(dict(_id=f'exc_{i}', reason='ambiguous_local_time' if i == 0 else 'candidate_match_unconfirmed', status='open'))
    return db


@pytest.fixture
def client(db):
    with TestClient(create_app(db=db, sync_enabled=False)) as client:
        yield client


def report(run_id='r1', day=1):
    return dict(run_id=run_id, generated_at=datetime(2024, 1, day, tzinfo=timezone.utc), passed=True,
                exception_summary={}, tables={'PRODUCTS': dict(source='oracle', depths={
                    'count': dict(source=1, placed=1, unplaced=0, passed=True),
                    'profile': dict(fields={}, passed=True),
                    'keyed_hash': dict(matched=1, mismatched=0, passed=True),
                    'sampled_values': dict(size=1, difference_count=0, differences=[], passed=True, rows=[
                        dict(key='1', expected={'name': 'Everyday'}, actual={'name': 'Everyday'}, raw_source={'name': 'Everyday'})])})})


def test_customer_and_decimal_serialization(client):
    result = client.get(PREFIX + '/customers/cus_0')
    assert result.status_code == 200
    assert result.json()['accounts'][0] == dict(balance='1.20', opened_at='2024-01-01T00:00:00Z')
    assert client.get(PREFIX + '/customers/absent').status_code == 404
    assert client.get('/health').json() == {'status': 'ok'}


def test_customer_filters_and_cursor(client):
    first = client.get(PREFIX + '/customers?limit=2').json()
    assert [row['_id'] for row in first['items']] == ['cus_0', 'cus_1']
    assert first['next_cursor'] == 'cus_1'
    last = client.get(PREFIX + '/customers', params={'limit': 2, 'cursor': first['next_cursor']}).json()
    assert [row['_id'] for row in last['items']] == ['cus_2']
    assert last['next_cursor'] is None
    for params in ({'db2_cust_no': 'C0000001'}, {'oracle_account_id': 7000001}, {'crm_contact_id': 'contact-1'}):
        assert client.get(PREFIX + '/customers', params=params).json()['items'][0]['_id'] == 'cus_1'
    assert len(client.get(PREFIX + '/customers?match_status=matched').json()['items']) == 2
    assert client.get(PREFIX + '/customers?db2_cust_no=missing').json()['items'] == []
    for query in ('limit=0', 'limit=101', 'oracle_account_id=bad', 'oracle_account_id=-1', 'match_status=bad'):
        assert client.get(PREFIX + '/customers?' + query).status_code == 422


def test_exceptions_routes_and_pagination(client):
    assert client.get(PREFIX + '/exceptions/exc_0').status_code == 200
    assert client.get(PREFIX + '/exceptions/absent').status_code == 404
    first = client.get(PREFIX + '/exceptions?reason=candidate_match_unconfirmed&status=open&limit=1').json()
    assert first['items'][0]['_id'] == first['next_cursor'] == 'exc_1'
    last = client.get(PREFIX + '/exceptions', params={'reason': 'candidate_match_unconfirmed', 'status': 'open', 'limit': 1, 'cursor': first['next_cursor']}).json()
    assert last['items'][0]['_id'] == 'exc_2' and last['next_cursor'] is None
    assert client.get(PREFIX + '/exceptions?status=closed').json()['items'] == []


def test_parity_routes_and_csv(client, db):
    assert client.get(PREFIX + '/parity/latest').status_code == 404
    assert client.get(PREFIX + '/parity').json() == {'items': []}
    for run_id in ('absent', 'absent.csv'):
        assert client.get(PREFIX + '/parity/' + run_id).status_code == 404
    db.parity_reports.insert_many([report(), report('r2', 2)])
    listing = client.get(PREFIX + '/parity?limit=1').json()['items']
    assert [r['run_id'] for r in listing] == ['r2']
    latest = client.get(PREFIX + '/parity/latest').json()
    assert latest['run_id'] == 'r2' and latest['generated_at'].endswith('Z')
    assert latest['tables']['PRODUCTS']['depths']['count'] is True
    full = client.get(PREFIX + '/parity/r1').json()
    assert 'rows' not in full['tables']['PRODUCTS']['depths']['sampled_values']
    result = client.get(PREFIX + '/parity/r1.csv')
    assert result.status_code == 200 and result.headers['content-type'].startswith('text/csv')
    expected = io.StringIO(newline='')
    write_csv(report(), expected)
    assert result.text == expected.getvalue()
    assert list(csv.DictReader(io.StringIO(result.text)))[-1]['status'] == 'pass'


def test_metric_labels_are_templates(client):
    before = metrics.read_requests.labels('/customers/{id}', '404')._value.get()
    client.get(PREFIX + '/customers/private-customer-id')
    client.get('/not-a-route/private-customer-id')
    text = client.get('/metrics').text
    assert metrics.read_requests.labels('/customers/{id}', '404')._value.get() == before + 1
    assert 'odl_read_requests_total{route="/customers/{id}",status="404"}' in text
    assert 'odl_read_requests_total{route="unmatched",status="404"}' in text
    assert 'odl_read_request_duration_seconds_bucket{le="0.005",route="/customers/{id}",status="404"}' in text
    assert 'private-customer-id' not in text


def test_database_failure(client, db, monkeypatch):
    def fail(*args, **kwargs):
        raise ConnectionFailure('do not expose connection details')
    monkeypatch.setattr(db.customers, 'find_one', fail)
    result = client.get(PREFIX + '/customers/cus_0')
    assert result.status_code == 503 and result.json() == {'detail': 'Database unavailable'}
    assert metrics.read_requests.labels('/customers/{id}', '503')._value.get() >= 1


def test_combined_mode_runs_sync_and_stops(db, monkeypatch):
    called = threading.Event()
    config = object()
    def run(settings):
        assert settings is config
        called.set()
        return {'status': 'ok'}
    monkeypatch.setattr(sync, 'run', run)
    monkeypatch.setenv('ODL_SYNC_INTERVAL_SECONDS', '60')
    with TestClient(create_app(db=db, settings=config)) as client:
        assert called.wait(2)
        assert client.get('/health').status_code == 200


def test_combined_mode_rejects_bad_interval(db, monkeypatch):
    monkeypatch.setenv('ODL_SYNC_INTERVAL_SECONDS', '0')
    with pytest.raises(ValueError, match='finite and positive'):
        with TestClient(create_app(db=db, settings=object())):
            pass
