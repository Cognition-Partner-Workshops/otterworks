from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from odl_sync.extract import Extract, SourceRecord
from odl_sync.extract import db2, oracle, postgres
from odl_sync.load import load
from odl_sync.merge import merge
from odl_sync.normalize import (customer_since, db2_key, db2_name, golden_id,
                                match_key, money, oracle_time)


def record(source, key, name='Jane Smith 000001', address='1 Road'):
    data = dict(customer_since=None, source_record={}, history=[]) if source == 'db2' else (
        dict(account={'account_id': int(key)}, ambiguous=False) if source == 'oracle' else dict(contact_id=key, service_cases=[]))
    return SourceRecord(source, key, name, address, data, {'key': key})


def test_normalize():
    assert db2_name('José García'.encode('cp037').hex()) == 'José García'
    assert db2_name('José García'.encode().hex()) == 'José García'
    assert db2_key('C0000001  ') == 'C0000001'
    assert customer_since(date(1, 1, 1)) is None
    assert customer_since(date(2024, 1, 1)) == '2024-01-01'
    assert money(Decimal('0.305'), True).to_decimal() == Decimal('0.30')
    assert money(Decimal('0.315'), True).to_decimal() == Decimal('0.32')
    assert golden_id('db2:C0000001') == golden_id('db2:C0000001')
    assert golden_id('db2:C0000001') != golden_id('oracle:1')
    assert match_key(' JANE  Smíth ', '1 ROAD') == match_key('jane smi\u0301th', '1 road')


@pytest.mark.parametrize('local,utc,ambiguous', [
    ('2024-03-10T01:55:00', '2024-03-10T06:55:00+00:00', False),
    ('2024-03-10T03:05:00', '2024-03-10T07:05:00+00:00', False),
    ('2024-11-03T01:15:00', '2024-11-03T05:15:00+00:00', True),
    ('2025-11-02T01:45:00', '2025-11-02T05:45:00+00:00', True)])
def test_timezone(local, utc, ambiguous):
    value, flag = oracle_time(datetime.fromisoformat(local))
    assert (value.isoformat(), flag) == (utc, ambiguous)


def test_invalid_normalize():
    with pytest.raises(ValueError):
        oracle_time(datetime(2024, 3, 10, 2, 30))
    with pytest.raises(ValueError):
        db2_name('zz')
    with pytest.raises(ValueError):
        db2_key('bad')
    with pytest.raises(ValueError):
        money(None)


def test_three_way():
    docs, errors = merge([Extract(s, [record(s, k)]) for s, k in [('db2', 'C0000001'), ('oracle', '7000000'), ('postgres', str(uuid4()))]])
    assert len(docs) == 1 and not errors
    assert docs[0]['match']['sources'] == ['db2', 'oracle', 'postgres']
    assert docs[0]['match']['status'] == 'matched'
    assert docs[0]['_id'] == golden_id('db2:C0000001')


def test_candidate_and_ambiguous():
    right = record('oracle', '7000000', 'Smith, J. 000001', '2 Road')
    right.data['ambiguous'] = True
    docs, errors = merge([Extract('db2', [record('db2', 'C0000001')]), Extract('oracle', [right])])
    assert len(docs) == 2
    assert {e['reason'] for e in errors} == {'candidate_match_unconfirmed', 'ambiguous_local_time'}
    pair = next(e for e in errors if e['reason'] == 'candidate_match_unconfirmed')
    assert all(pair['_id'] in d['exception_ids'] for d in docs)
    assert all(d['match']['status'] == 'single-source' for d in docs)


def test_duplicates_and_empty():
    docs, errors = merge([Extract('db2', [record('db2', 'C0000001'), record('db2', 'C0000002')])])
    assert not docs
    assert len(errors) == 2 and all(e['reason'] == 'duplicate_match_key' for e in errors)
    assert merge([]) == ([], [])


def test_orphans_and_transform_failures():
    result = db2.from_rows([], [dict(history_id=1, cust_no='C0000001', event_on=date(2020, 1, 1), amount=1)])
    assert not result.records
    assert result.unplaced[0]['reason'] == 'orphan_history'
    key = str(uuid4())
    pg = postgres.from_rows([], [dict(case_id=uuid4(), contact_id=key, subject='x', opened_at=datetime(2024, 1, 1))], [dict(contact_id=key, status='active')])
    assert {e['reason'] for e in pg.unplaced} == {'orphan_service_case', 'orphan_subscription'}
    bad = oracle.from_rows([dict(account_id=1, holder_name='x', address='y', product_id=99, balance=1, opened_at=datetime(2024, 1, 1))], [])
    assert not bad.records and bad.unplaced[0]['reason'] == 'transform_failed'
    docs, errors = merge([result, pg, bad])
    assert not docs and len(errors) == 4


class Result:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class Collection:
    def __init__(self):
        self.docs = {}

    def create_index(self, *args, **kwargs):
        pass

    def find(self, *args):
        return list(self.docs.values())

    def bulk_write(self, operations, ordered):
        inserted = updated = 0
        assert ordered is False
        for op in operations:
            key = op._filter['_id']
            existed = key in self.docs
            if key in self.docs:
                updated += 1
            else:
                inserted += 1
            if '$set' in op._doc:
                document = self.docs.setdefault(key, {'_id': key})
                if not existed:
                    document.update(op._doc.get('$setOnInsert', {}))
                document.update(op._doc['$set'])
                for field in op._doc.get('$unset', {}):
                    document.pop(field, None)
            else:
                self.docs[key] = op._doc
        return Result(upserted_count=inserted, modified_count=updated)

    def delete_many(self, query):
        removed = 0
        for key in query['_id']['$in']:
            removed += self.docs.pop(key, None) is not None
        return Result(deleted_count=removed)


class Database:
    def __init__(self):
        self.customers = Collection()
        self.mapping_exceptions = Collection()

    def list_collection_names(self):
        return ['customers', 'mapping_exceptions']


def test_load_idempotency_update_and_delete():
    db = Database()
    docs, errors = merge([Extract('db2', [record('db2', 'C0000001')])])
    first = load(db, docs, errors)
    assert first['customers']['inserted'] == 1
    assert first['applied'] == {'db2': 1, 'oracle': 0, 'postgres': 0}
    second = load(db, docs, errors)
    assert second['customers']['modified'] == second['customers']['inserted'] == 0
    assert second['applied']['db2'] == 0
    docs[0]['address'] = 'changed'
    assert load(db, docs, errors)['customers']['modified'] == 1
    assert load(db, [], [])['customers']['removed'] == 1


def test_load_write_failure():
    db = Database()
    def fail(*args, **kwargs):
        raise RuntimeError('write failure')
    db.customers.bulk_write = fail
    docs, errors = merge([Extract('db2', [record('db2', 'C0000001')])])
    with pytest.raises(RuntimeError, match='write failure'):
        load(db, docs, errors)


def test_duplicate_parents_account_for_all_dependents():
    from odl_sync.parity import tables, unplaced_for

    keys = [str(uuid4()), str(uuid4())]
    db2_rows = [dict(cust_no=f'C000000{i}', full_name_hex='Jane'.encode().hex(), address='1 Road',
                     opened_on=date(2020, 1, 1), opened_ymd=20200101) for i in (1, 2)]
    history = [dict(history_id=i, cust_no=row['cust_no'], event_on=date(2020, 1, 1), amount=Decimal('1.20'))
               for i, row in enumerate(db2_rows, 1)]
    contacts = [dict(contact_id=key, full_name='Jane', address='1 Road', credit=Decimal('1.20')) for key in keys]
    cases = [dict(case_id=str(uuid4()), contact_id=key, subject='Help', opened_at=datetime(2020, 1, 1)) for key in keys]
    subscriptions = [dict(contact_id=key, status='active') for key in keys]
    docs, errors = merge([db2.from_rows(db2_rows, history), postgres.from_rows(contacts, cases, subscriptions)])
    assert not docs
    assert len(errors) == 10
    specs = {table.name: table for table in tables()}
    for name in ('ODL.CUSTMAST', 'ODL.ACCTHIST', 'crm.contacts', 'crm.service_cases', 'crm.subscription_snapshots'):
        assert len(unplaced_for(specs[name], errors)) == 2
    child = next(e for e in errors if e['reason'] == 'orphan_history')
    assert child['detail']['amount'] == '1.20'
