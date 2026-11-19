import copy
import json
from datetime import date
from decimal import Decimal

import pytest

from lakehouse.parity import __main__ as cli
from lakehouse.parity.engine import compare, normalize_value
from lakehouse.parity.readers import Readers, postgres_connection
from lakehouse.parity.spec import discover, load_spec

SPEC = {'keys': ['id']}


def test_equal_order_independent_and_fingerprints():
    rows = [{'id': 2, 'amount': Decimal('1.20'), 'name': None},
            {'id': 1, 'amount': Decimal('2.30'), 'name': 'A'}]
    result = compare(rows, list(reversed(rows)), SPEC)
    assert result['passed']
    assert result['fingerprints']['legacy'] == result['fingerprints']['lakehouse']
    assert result['fingerprints']['legacy']['amount']['sum'] == '3.5'
    assert result['fingerprints']['legacy']['name']['null_count'] == 1
    assert result['fingerprints']['legacy']['id']['count'] == 2


@pytest.mark.parametrize('left,right,field', [
    ([{'id': 1}], [], 'only_in_legacy'),
    ([], [{'id': 1}], 'only_in_lakehouse'),
])
def test_missing_extra_and_row_counts(left, right, field):
    result = compare(left, right, SPEC, ['id'], ['id'])
    assert not result['passed']
    assert result[field]['count'] == 1
    assert result['row_counts']['legacy'] != result['row_counts']['lakehouse']


@pytest.mark.parametrize('side', ['legacy', 'lakehouse'])
def test_duplicate_keys(side):
    rows = [{'id': 1}, {'id': 1}]
    left, right = (rows, rows[:1]) if side == 'legacy' else (rows[:1], rows)
    result = compare(left, right, SPEC)
    assert not result['passed']
    assert result['duplicate_keys'][side]['key_count'] == 1
    assert result['duplicate_keys'][side]['row_count'] == 2


def test_negative_mutated_row_and_bounded_deterministic_samples():
    rows = [{'id': key, 'value': 'before'} for key in range(5)]
    mutated = copy.deepcopy(rows)
    mutated[0]['value'] = 'after'
    single_mutation = compare(rows, mutated, SPEC)
    assert not single_mutation['passed']
    assert single_mutation['mismatches']['value']['count'] == 1
    for row in mutated:
        row['value'] = 'after'
    result = compare(rows, mutated, SPEC, sample_limit=2)
    reverse = compare(list(reversed(rows)), list(reversed(mutated)), SPEC, sample_limit=2)
    assert not result['passed']
    assert result == reverse
    assert result['mismatches']['value']['count'] == 5
    assert len(result['mismatches']['value']['samples']) == 2
    assert result['fingerprints']['legacy']['value']['hash'] != result['fingerprints']['lakehouse']['value']['hash']
    assert compare(rows, rows, SPEC)['passed']


def test_null_and_empty_and_filters():
    left = [{'id': 1, 'name': None}, {'id': 2, 'name': 'discard'}]
    right = [{'id': 1, 'name': ''}]
    assert not compare(left[:1], right, SPEC)['passed']
    spec = {**SPEC, 'normalize': {'name': {'empty_as_null': True}}, 'filters': {'id': [1]}}
    assert compare(left, right, spec)['passed']
    assert not compare([{'id': None}], [{'id': None}], SPEC)['passed']


def test_normalizations_and_numeric_tolerance():
    spec = {**SPEC, 'normalize': {
        'text': {'trim': True, 'case_fold': True}, 'char': {'rstrip': True},
        'amount': {'numeric_scale': 2}, 'day': {'date_format': '%d/%m/%Y'}},
        'tolerance': {'amount': '0.01'}}
    left = [{'id': 1, 'text': ' STRASSE ', 'char': ' A  ', 'amount': '1.204', 'day': '09/11/2026'}]
    right = [{'id': 1, 'text': 'Straße', 'char': ' A', 'amount': Decimal('1.21'), 'day': date(2026, 11, 9)}]
    assert compare(left, right, spec)['passed']
    right[0]['amount'] = Decimal('1.22')
    result = compare(left, right, spec)
    assert not result['passed'] and result['mismatches']['amount']['count'] == 1
    assert normalize_value('1.205', {'numeric_scale': 2}) == Decimal('1.21')
    assert normalize_value('   ', {'rstrip': True, 'empty_as_null': True}) is None


def test_empty_inputs_and_invalid_comparisons():
    assert compare([], [], SPEC, ['id'], ['id'])['passed']
    for spec in ({'keys': ['missing']}, {**SPEC, 'columns': ['value']},
                 {**SPEC, 'tolerance': {'id': -1}}):
        with pytest.raises(ValueError):
            compare([{'id': 1, 'value': 'a'}], [{'id': 1, 'value': 'a'}], spec)
    with pytest.raises(ValueError, match='Non-finite'):
        normalize_value(float('nan'), {})


def test_csv_reader_and_errors(tmp_path, monkeypatch):
    monkeypatch.setenv('NS', 'test-parity')
    path = tmp_path / '20261109.csv'
    path.write_text('ID,NAME\n1,"quoted, value"\n')
    reader = Readers('20261109')
    side = {'kind': 'file', 'path': str(tmp_path / '{business_date}.csv'),
            'header': True, 'delimiter': ','}
    rows, columns = reader.read(side)
    assert columns == ['id', 'name'] and rows == [{'id': '1', 'name': 'quoted, value'}]
    path.write_text('1|\n')
    side.update(header=False, delimiter='|', columns=['id', 'name'])
    assert reader.read(side)[0] == [{'id': '1', 'name': ''}]
    path.write_text('')
    assert reader.read(side) == ([], ['id', 'name'])
    path.write_text('1|a|extra\n')
    with pytest.raises(ValueError, match='field count'):
        reader.read(side)
    path.unlink()
    with pytest.raises(FileNotFoundError):
        reader.read(side)
    with pytest.raises(ValueError, match='unique'):
        Readers.validate_columns(['id', 'id'])


def test_postgres_environment_precedence(monkeypatch):
    for name in ('DSN', 'HOST', 'PORT', 'DB', 'USER', 'PASSWORD'):
        monkeypatch.delenv('TD_PG_' + name, raising=False)
    monkeypatch.setattr('lakehouse.parity.readers.psycopg.connect', lambda dsn, **kwargs: (dsn, kwargs))
    assert postgres_connection()[1]['port'] == '5432'
    monkeypatch.setenv('TD_PG_DSN', 'dbname=example port=1234')
    assert postgres_connection() == ('dbname=example port=1234', {})
    monkeypatch.setenv('TD_PG_PORT', '4321')
    assert postgres_connection()[1] == {'port': '4321'}


def test_specs_and_evidence_failure_exit(tmp_path, monkeypatch):
    monkeypatch.setenv('NS', 'test-parity')
    specs = discover()
    path, spec = specs['billing.customer_account']
    assert spec['legacy_objects'] == ['teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT',
                                      'bteq_script:warehouse/teradata/scripts/billing/01_load_accounts.bteq']
    invalid = tmp_path / 'bad.yaml'
    invalid.write_text('id: ../unsafe\n')
    with pytest.raises(ValueError):
        load_spec(invalid)

    class FakeReaders:
        def __init__(self, day):
            self.calls = 0

        def read(self, side):
            self.calls += 1
            return [{'id': 1, 'value': self.calls}], ['id', 'value']

        def close(self):
            pass

    monkeypatch.setattr(cli, 'Readers', FakeReaders)
    test_spec = {**spec, 'keys': ['id'], 'columns': ['id', 'value']}
    assert cli.run([(path, test_spec)], '20261109', 1, tmp_path) == 1
    report = json.loads((tmp_path / 'parity/billing.customer_account.json').read_text())
    assert report['spec_hash'] and report['git_sha'] and report['NS'] == 'test-parity'
    assert report['row_counts'] == {'legacy': 1, 'lakehouse': 1}
    assert report['results']['mismatches']['value']['count'] == 1
    assert '| FAIL |' in (tmp_path / 'PARITY.md').read_text()

    monkeypatch.setattr(FakeReaders, 'read', lambda self, side: ([{'id': 1, 'value': 1}], ['id', 'value']))
    assert cli.run([(path, test_spec)], '20261109', 1, tmp_path) == 0
    assert '| PASS |' in (tmp_path / 'PARITY.md').read_text()

    def error_read(self, side):
        raise RuntimeError('reader failed')

    monkeypatch.setattr(FakeReaders, 'read', error_read)
    assert cli.run([(path, test_spec)], '20261109', 1, tmp_path) == 1
    report = json.loads((tmp_path / 'parity/billing.customer_account.json').read_text())
    assert report['results']['error'] == 'RuntimeError: reader failed'
