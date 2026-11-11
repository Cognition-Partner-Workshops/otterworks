"""HARNESS self-tests only: these do not certify any migrated mapping."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import pytest

import json

from parity import evidence
from parity.evidence import cell, determinism_failures, full_compare, replay_gate, scope, verify_provenance

NO_REJECTS = ([], [], [])


def fixture():
    return {'columns': ['KEY', 'ID', 'VALUE'],
            'types': {'KEY': ['integer'], 'ID': ['integer'], 'VALUE': ['numeric', None, 12, 2]},
            'rows': [[cell(1), cell(100), cell(Decimal('1.00'))],
                     [cell(2), cell(101), cell(None)]]}


def test_positive_and_empty():
    s = fixture()
    assert replay_gate(s, s, s, ['KEY'], ['ID'], NO_REJECTS)['passed']
    s['rows'] = []
    assert replay_gate(s, s, s, ['KEY'], ['ID'], NO_REJECTS)['passed']


@pytest.mark.parametrize('case', ['dropped', 'duplicate', 'value', 'empty', 'scale', 'type', 'resequence', 'duplicate_key'])
def test_negative(case):
    s = fixture()
    after = deepcopy(s)
    if case == 'dropped':
        after['rows'].pop()
    elif case == 'duplicate':
        after['rows'].append(after['rows'][0])
    elif case == 'value':
        after['rows'][0][2] = cell(Decimal('2.00'))
    elif case == 'empty':
        after['rows'][1][2] = cell('')
    elif case == 'scale':
        after['rows'][0][2] = cell(Decimal('1.0'))
    elif case == 'type':
        after['types']['VALUE'][-1] = 3
    elif case == 'resequence':
        after['rows'][0][1] = cell(200)
    else:
        after['rows'][1][0] = after['rows'][0][0]
    assert not replay_gate(s, s, after, ['KEY'], ['ID'], NO_REJECTS)['passed']


def test_timestamp_zone_shift_and_whitespace():
    s = fixture()
    s['rows'][0][2] = cell(datetime(2026, 11, 9, tzinfo=timezone.utc))
    a = deepcopy(s)
    a['rows'][0][2] = cell(datetime(2026, 11, 9, tzinfo=timezone(timedelta(hours=1))))
    assert not full_compare(s, a, ['KEY'])['equal']
    assert cell(' ') != cell('')


def test_multiplicity_complete_and_error():
    s = fixture()
    a = deepcopy(s)
    a['rows'] *= 3
    report = full_compare(s, a, ['KEY'])
    assert [r['multiplicity'] for r in report['only_after']] == [2, 2]
    assert len(report['duplicate_keys_after']) == 2
    with pytest.raises(ValueError, match='business keys'):
        full_compare(s, a, ['MISSING'])
    a['columns'] = ['OTHER']
    assert not full_compare(s, a, ['KEY'])['equal']


def test_scope_is_exact():
    rows = scope()
    assert len(rows) == 8
    assert sum(not r['enabled_in_workflow'] for r in rows) == 2
    assert sum(bool(r['sequence_columns']) for r in rows) == 2
    assert {r['parameters']['$$LOAD_DATE'] for r in rows} == {'20261109'}


def test_live_type_mapping_and_scope_guard():
    from parity.evidence_live import sf_type, upload
    assert sf_type(['bigint', None, 64, 0]) == 'NUMBER(38,0)'
    assert sf_type(['timestamp without time zone', None, None, None, 0]) == 'TIMESTAMP_NTZ(9)'
    with pytest.raises(ValueError, match='Unsupported type'):
        sf_type(['unknown', None, None, None])
    with pytest.raises(ValueError, match='Unowned baseline'):
        upload(None, 'CUSTOMER_ACCOUNT', {})


def test_live_fetch_type_error_and_empty():
    from parity.evidence_live import fetched
    template = {'columns': ['ID'], 'types': {'ID': ['bigint', None, 64, 0]}, 'rows': []}
    class Query:
        def __init__(self, dtype):
            self.dtype = dtype
        def run(self, sql):
            return ([], [('ID', self.dtype)]) if sql.startswith('DESCRIBE') else (['ID'], [])
    assert fetched(Query('NUMBER(38,0)'), 'test', template) == template
    with pytest.raises(ValueError, match='Unexpected warehouse type'):
        fetched(Query('VARCHAR(10)'), 'test', template)


def test_live_landing_nulls_scale_and_hash(tmp_path):
    from parity.evidence_live import expected_landing
    from parity.evidence import sha
    path = tmp_path / 'input.psv'
    path.write_text('1|1.20|\n')
    manifest = {'landing': [{'path': str(path), 'sha256': sha(path)}]}
    row = {'landing_files': [str(path)]}
    template = {'columns': ['ID', 'VALUE', 'TEXT'], 'types': {'ID': ['bigint'], 'VALUE': ['numeric'], 'TEXT': ['text']}}
    got = expected_landing(manifest, row, template)
    assert got['rows'] == [[cell(1), cell(Decimal('1.20')), cell(None)]]
    path.write_text('')
    with pytest.raises(AssertionError):
        expected_landing(manifest, row, template)
    manifest['landing'][0]['sha256'] = sha(path)
    assert expected_landing(manifest, row, template)['rows'] == []


def test_replay_gate_compares_rejects():
    s = fixture()
    rejects = [{'name': 'SECURITY_ALERT.bad', 'rows': ['INFO|1', 'INFO|2', 'INFO|3']}]
    assert replay_gate(s, s, s, ['KEY'], ['ID'], (rejects, rejects, rejects))['passed']
    dropped = [{'name': 'SECURITY_ALERT.bad', 'rows': []}]
    result = replay_gate(s, s, s, ['KEY'], ['ID'], (rejects, rejects, dropped))
    assert not result['passed'] and result['reject_comparisons']['oracle_run2']['after_count'] == 0
    changed = [{'name': 'SECURITY_ALERT.bad', 'rows': ['INFO|1', 'INFO|2', 'INFO|9']}]
    assert not replay_gate(s, s, s, ['KEY'], ['ID'], (rejects, changed, changed))['passed']


def test_divergent_oracle_captures_fail():
    reports = {'m_A': {'equal': True, 'rejects_identical': True},
               'm_B': {'equal': True, 'rejects_identical': False},
               'm_C': {'equal': False, 'rejects_identical': True}}
    assert determinism_failures(reports) == ['m_B', 'm_C']
    assert determinism_failures({'m_A': reports['m_A']}) == []


def test_baselines_require_verified_oracle_artifacts(tmp_path, monkeypatch):
    from parity import evidence_live
    monkeypatch.setattr(evidence, 'OUT', tmp_path)
    monkeypatch.setattr(evidence, 'scope', lambda: [{'mapping': 'm_SFX_SECURITY_ALERT'}])
    (tmp_path / 'manifest.json').write_text('{}')
    oracle = tmp_path / 'm_SFX_SECURITY_ALERT/oracle1'
    oracle.mkdir(parents=True)
    (oracle / 'target.json').write_text(json.dumps({'rows': [[1]] * 61}))
    (oracle / 'rejects.json').write_text('[]')

    class Refuse:
        def run(self, sql):
            raise AssertionError('No live statement may run before provenance is verified')
    with pytest.raises(ValueError, match='No verified oracle capture'):
        evidence_live.baselines(Refuse())
    (tmp_path / 'oracle_provenance.json').write_text(json.dumps(evidence.provenance()))
    verify_provenance()
    (oracle / 'target.json').write_text(json.dumps({'rows': [[1]] * 60}))
    with pytest.raises(ValueError, match='differ from the verified'):
        evidence_live.baselines(Refuse())
    (oracle / 'rejects.json').unlink()
    with pytest.raises(ValueError, match='artifact missing'):
        verify_provenance()
