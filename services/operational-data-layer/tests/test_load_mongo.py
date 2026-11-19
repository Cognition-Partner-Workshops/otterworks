import os
from copy import deepcopy
from uuid import uuid4

import pytest
from pymongo import MongoClient

from odl_sync.extract import Extract
from odl_sync.load import load
from odl_sync.merge import merge
from test_core import record

pytestmark = pytest.mark.skipif(not os.environ.get('ODL_TEST_MONGO_URI'), reason='requires local MongoDB')


@pytest.fixture
def database():
    with MongoClient(os.environ['ODL_TEST_MONGO_URI'], serverSelectionTimeoutMS=5000) as client:
        name = 'odl_test_' + uuid4().hex
        try:
            yield client[name]
        finally:
            client.drop_database(name)


def test_customer_unique_key_cycles_and_retry(database):
    customers, _ = merge([Extract('db2', [record('db2', 'C0000001', 'A'), record('db2', 'C0000002', 'B')])])
    load(database, customers, [])
    swapped = deepcopy(customers)
    swapped[0]['match_key'], swapped[1]['match_key'] = swapped[1]['match_key'], swapped[0]['match_key']
    swapped[0]['source_keys'], swapped[1]['source_keys'] = swapped[1]['source_keys'], swapped[0]['source_keys']
    for i, doc in enumerate(swapped):
        doc['source_keys']['oracle_account_ids'] = [i + 1]
        doc['source_keys']['crm_contact_id'] = str(uuid4())
    result = load(database, swapped, [])
    assert result['customers']['modified'] == 2
    assert load(database, swapped, [])['customers']['unchanged'] == 2
    restored = deepcopy(customers)
    restored[0]['source_keys']['oracle_account_ids'] = [2]
    restored[1]['source_keys']['oracle_account_ids'] = [1]
    restored[0]['source_keys']['crm_contact_id'] = swapped[1]['source_keys']['crm_contact_id']
    restored[1]['source_keys']['crm_contact_id'] = swapped[0]['source_keys']['crm_contact_id']
    assert load(database, restored, [])['customers']['modified'] == 2
    assert load(database, restored, [])['customers']['unchanged'] == 2


def test_interrupted_key_release_recovers_even_if_source_reverts(database):
    customers, _ = merge([Extract('db2', [record('db2', 'C0000001', 'A')])])
    load(database, customers, [])
    database.customers.update_one({'_id': customers[0]['_id']}, {
        '$set': {'match_key': 'pending:' + customers[0]['_id']},
        '$unset': {'source_keys': '', 'content_hash': ''},
    })
    assert load(database, customers, [])['customers']['modified'] == 1
    assert database.customers.find_one()['source_keys'] == customers[0]['source_keys']


def test_exception_reviews_survive_source_updates(database):
    exception = dict(_id='e1', reason='ambiguous_local_time', status='open', detail={'balance': '1.20'})
    assert load(database, [], [exception])['exceptions']['inserted'] == 1
    review = dict(status='closed', reviewer='operator', notes='Approved', resolved_at='2026-11-19T00:00:00Z')
    database.mapping_exceptions.update_one({'_id': 'e1'}, {'$set': review})
    assert load(database, [], [exception])['exceptions']['unchanged'] == 1
    exception['detail']['balance'] = '2.30'
    assert load(database, [], [exception])['exceptions']['modified'] == 1
    stored = database.mapping_exceptions.find_one()
    assert {key: stored[key] for key in review} == review
    assert stored['detail']['balance'] == '2.30'
    assert load(database, [], [exception])['exceptions']['unchanged'] == 1
