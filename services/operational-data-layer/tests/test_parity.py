import csv
import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from bson.decimal128 import Decimal128

from odl_sync.parity import (canonical, compare_profiles, compare_rows, profile,
                             row_hash, serialized, tables, unplaced_for, write_csv)
from odl_sync import parity


def test_canonical_hash():
    left = dict(balance=Decimal('1.00'), at=datetime(2024, 1, 1, tzinfo=timezone.utc), nested={'b': 2, 'a': 1})
    right = dict(nested={'a': 1, 'b': 2}, at=datetime(2023, 12, 31, 19, tzinfo=timezone(timedelta(hours=-5))), balance=Decimal128('1.0'))
    assert serialized(left) == serialized(right)
    assert row_hash('a', left) == row_hash('a', right)
    assert row_hash('a', left) != row_hash('b', right)
    assert row_hash('a', {'value': None}) != row_hash('a', {'value': 'None'})
    assert row_hash('a', {'value': 'é'}) != row_hash('a', {'value': 'e'})
    assert canonical(datetime(2024, 1, 1)) == canonical(datetime(2024, 1, 1, tzinfo=timezone.utc))


def test_profiles_exact_decimal_and_null():
    expected = profile([Decimal('0.10'), Decimal('0.20'), None, Decimal('0.10')], 'money')
    actual = profile([Decimal128('0.1'), Decimal128('0.2'), None, Decimal128('0.1')], 'money')
    assert expected['sum'] == Decimal('.40')
    assert expected['distinct'] == 2
    assert expected['null'] == 1
    assert all(check['passed'] for check in compare_profiles(expected, actual).values())
    actual['sum'] = Decimal('.41')
    assert not compare_profiles(expected, actual)['sum']['passed']
    assert profile(['é', None, 'abc', 'é'], 'string') == dict(non_null=3, null=1, distinct=2, min='abc', max='é', min_length=1, max_length=3)
    assert profile([], 'money')['sum'] == 0
    assert profile([None], 'string')['min_length'] is None


def test_hash_differences_and_unplaced():
    expected = [dict(id=str(i), amount=Decimal(i)) for i in range(4)]
    actual = [dict(id='0', amount=Decimal128('0')), dict(id='1', amount=Decimal128('9')), dict(id='9', amount=Decimal128('9'))]
    hashes, sample = compare_rows(expected, actual, 'id', {'3'})
    assert hashes['matched'] == 1
    assert hashes['mismatched'] == 1
    assert hashes['missing_in_target'] == 1
    assert hashes['extra_in_target'] == 1
    assert hashes['unplaced'] == 1
    assert hashes['differing_keys'] == ['1']
    assert sample['size'] == 3 and sample['difference_count'] == 3
    assert not hashes['passed'] and not sample['passed']
    assert compare_rows([], [], 'id')[0]['passed']


def test_duplicate_target_fails_hash():
    row = dict(id='1', name='x')
    hashes, _ = compare_rows([row], [row, row], 'id')
    assert hashes['duplicate_target_keys'] == 1 and not hashes['passed']


def test_four_product_samples_and_exception_classification():
    products = [dict(product_id=i, name=str(i)) for i in range(4)]
    assert compare_rows(products, products, 'product_id')[1]['size'] == 4
    specs = {t.name: t for t in tables()}
    errors = [dict(reason='orphan_history', source_keys=['db2:1'], detail=dict(history_id='1', cust_no='C0000001')),
              dict(reason='candidate_match_unconfirmed', source_keys=['db2:C0000001'], detail={})]
    assert len(unplaced_for(specs['ODL.ACCTHIST'], errors)) == 1
    assert not unplaced_for(specs['ODL.CUSTMAST'], errors)


def test_csv(tmp_path):
    path = tmp_path / 'parity.csv'
    report = dict(run_id='test', tables={'t': dict(source='db2', depths={
        'count': dict(source=1, placed=1, passed=True),
        'profile': dict(fields={'name': compare_profiles({'null': 0}, {'null': 0})}, passed=True)})})
    write_csv(report, path)
    assert path.read_text().splitlines()[0] == 'run_id,source,table,depth,check,field,source_value,target_value,status,detail'


def test_postgres_profiles_use_binary_collation(monkeypatch):
    table = next(t for t in tables() if t.name == 'crm.contacts')
    queries = []
    def rows(conn, query):
        queries.append(query)
        result = {'total_rows': 1}
        for i, value in enumerate(['Jane', '10 Road']):
            for stat, answer in dict(non_null=1, distinct=1, min=value, max=value, min_length=len(value), max_length=len(value)).items():
                result[f'f{i}_{stat}'] = answer
        yield result
    monkeypatch.setattr(parity, 'sql_rows', rows)
    count, profiles = parity.source_profiles(None, table, [dict(contact_id='x', name='Jane', address='10 Road', credit=Decimal('1'))])
    assert count == 1
    assert 'MIN((address COLLATE "C"))' in queries[0]
    assert profiles['address']['min'] == '10 Road'


def test_csv_samples_include_raw_expected_actual(tmp_path):
    path = tmp_path / 'sample.csv'
    report = dict(run_id='r', tables={'t': dict(source='postgres', depths={
        'sampled_values': dict(passed=False, size=1, differences=[], rows=[
            dict(key='1', raw_source={'credit': '0.305'}, expected={'credit': '0.30'}, actual={'credit': '0.31'})])})})
    write_csv(report, path)
    with path.open() as f:
        rows = list(csv.DictReader(f))
    assert rows[1]['status'] == 'fail'
    assert '0.305' in rows[1]['detail']


@pytest.mark.parametrize('run_id', ['latest', 'audit.csv', '', '../audit', 'run/1', 'a' * 129])
def test_invalid_run_ids_rejected_before_connecting(run_id, tmp_path):
    with pytest.raises(ValueError, match='run_id'):
        parity.run(None, run_id, tmp_path / 'report.csv')
    assert not (tmp_path / 'report.csv').exists()


@pytest.mark.parametrize('run_id', ['odl-1795112287-parity-2', 'audit_1.0', 'a'])
def test_valid_run_ids(run_id):
    assert parity.validate_run_id(run_id) == run_id


@pytest.mark.parametrize('source', ['db2', 'oracle', 'postgres'])
@pytest.mark.parametrize('name,address', [('JANE', '1 ROAD'), (' Jane  ', '1   Road'), ('Jäne', '1 Road')])
def test_source_spelling_survives_normalized_matches(source, name, address):
    import mongomock
    from odl_sync.extract import Extract
    from odl_sync.merge import merge
    from test_core import record

    anchor = record('db2', 'C0000001', name.casefold().replace('ä', 'a\u0308').strip(), '1 Road')
    other = record(source, {'db2': 'C0000001', 'oracle': '7000001', 'postgres': 'contact-1'}[source], name, address)
    records = [other] if source == 'db2' else [anchor, other]
    customers, _ = merge([Extract(r.source, [r]) for r in records])
    assert len(customers) == 1
    table = next(t for t in tables() if t.name == {'db2': 'ODL.CUSTMAST', 'oracle': 'ACCOUNTS', 'postgres': 'crm.contacts'}[source])
    collection = mongomock.MongoClient().odl.customers
    collection.insert_many(customers)
    actual = list(collection.aggregate(table.target))[0]
    assert actual['name'] == name and actual['address'] == address
    assert all(c['passed'] for c in compare_profiles(profile([name], 'string'), profile([actual['name']], 'string')).values())
    expected = {table.key: actual[table.key], 'name': name, 'address': address}
    projected = {key: actual[key] for key in expected}
    hashes, sample = compare_rows([expected], [projected], table.key)
    assert hashes['passed'] and sample['passed']
