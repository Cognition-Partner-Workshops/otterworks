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


def test_candidate_comparison_exact_ties_and_empty():
    spec = {'comparison': 'candidates', 'keys': ['id'], 'columns': ['id', 'version', 'value']}
    rows = [{'id': 1, 'version': 1, 'value': 'exact'},
            {'id': 2, 'version': 2, 'value': 'first'},
            {'id': 2, 'version': 3, 'value': 'second'}]
    result = compare(rows, [rows[0], rows[2]], spec)
    assert result['passed']
    assert (result['exact_matched_rows'], result['tie_resolved_rows'], result['mismatches']) == (1, 1, 0)
    assert compare(rows, rows[:2], spec)['passed']
    assert compare([], [], spec, spec['columns'], spec['columns'])['passed']
    for winners in ([rows[0]], [rows[0], rows[2], rows[2]],
                    [rows[0], {**rows[2], 'value': 'corrupt'}],
                    [{**rows[0], 'value': 'corrupt'}, rows[2]],
                    [rows[0], rows[2], {**rows[0], 'id': 3}]):
        assert not compare(rows, winners, spec)['passed']
    assert not compare([{'id': None}], [{'id': None}],
                       {'comparison': 'candidates', 'keys': ['id']})['passed']
    with pytest.raises(ValueError, match='Missing row columns'):
        compare(rows, [{'id': 1}], spec, spec['columns'], spec['columns'])


def test_candidate_aggregate_recomputes_selected_legacy_contributions():
    spec = {'comparison': 'candidates', 'keys': ['id'],
            'columns': ['id', 'owner', 'version', 'value'],
            'candidate_aggregate': {'group_keys': ['owner'], 'value': 'value',
                                    'count': 'count', 'total': 'total'}}
    rows = [dict(id=1, owner=1, version=1, value=10, count=2, total=15),
            dict(id=1, owner=1, version=2, value=20, count=2, total=15),
            dict(id=2, owner=1, version=3, value=5, count=2, total=15),
            dict(id=3, owner=2, version=4, value=7, count=1, total=7)]
    winners = [{**rows[1], 'total': 25}, {**rows[2], 'total': 25}, rows[3]]
    result = compare(rows, winners, spec)
    assert result['passed']
    assert (result['exact_matched_rows'], result['tie_resolved_rows'], result['mismatches']) == (1, 1, 0)
    assert result['aggregate_bounds'][0] == {'key': (Decimal(1),), 'minimum': 15,
                                             'maximum': 25, 'recomputed': 25}
    for changes in ({'total': 20}, {'total': 26}, {'count': 3}, {'value': 19}, {'version': 99}):
        broken = [{**winners[0], **changes}, {**winners[1], **changes}, rows[3]]
        assert not compare(rows, broken, spec)['passed']
    assert not compare(rows, winners[:-1], spec)['passed']
    assert not compare(rows, winners + [winners[0]], spec)['passed']
    assert not compare(rows, winners + [{**rows[3], 'owner': 3, 'id': 4}], spec)['passed']
    # An untied owner's published legacy total is still checked exactly.
    assert not compare([{**row, 'total': 8} if row['owner'] == 2 else row for row in rows],
                       winners, spec)['passed']
    names = spec['columns'] + ['count', 'total']
    assert compare([], [], spec, names, names)['passed']
    with pytest.raises(ValueError, match='share aggregate group keys'):
        compare([rows[0], {**rows[1], 'owner': 2}], winners, spec)


@pytest.mark.parametrize('changes', [
    {'comparison': 'unknown'},
    {'comparison': 'candidates', 'candidate_aggregate': {}},
    {'comparison': 'candidates', 'tolerance': {'id': 1}},
    {'comparison': 'exact', 'candidate_aggregate': {'group_keys': ['id'], 'value': 'id',
                                                 'count': 'count', 'total': 'total'}},
    {'comparison': 'candidates', 'candidate_aggregate': {'group_keys': ['missing'], 'value': 'id',
                                                       'count': 'count', 'total': 'total'}},
])
def test_candidate_spec_rejects_invalid_configuration(tmp_path, changes):
    spec = {**discover()['billing.customer_account'][1], **changes}
    path = tmp_path / 'invalid.yaml'
    path.write_text(json.dumps(spec))
    with pytest.raises(ValueError):
        load_spec(path)


@pytest.mark.parametrize('values,selected,expected,minimum,maximum', [
    ([None, 10], 0, None, 10, 10),
    ([None, 10], 1, 10, 10, 10),
    ([None, None], 0, None, None, None),
    ([-10, -5], 1, -5, -10, -5),
])
def test_candidate_aggregate_null_and_negative_totals(values, selected, expected, minimum, maximum):
    spec = {'comparison': 'candidates', 'keys': ['id'],
            'columns': ['id', 'owner', 'version', 'value'],
            'candidate_aggregate': {'group_keys': ['owner'], 'value': 'value',
                                    'count': 'count', 'total': 'total'}}
    rows = [dict(id=1, owner=1, version=i, value=value, count=1, total=values[0])
            for i, value in enumerate(values)]
    result = compare(rows, [{**rows[selected], 'total': expected}], spec)
    assert result['passed']
    assert result['aggregate_bounds'] == [{'key': (Decimal(1),), 'minimum': minimum,
                                           'maximum': maximum, 'recomputed': expected}]


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
    monkeypatch.setenv('LEGACY_NS', 'test-legacy-parity')
    assert Readers('20261109').path({'path': '{LEGACY_NS}/{business_date}'}).parts[-2:] == (
        'test-legacy-parity', '20261109')
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
    assert spec['legacy_objects'] == ['teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT']
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
