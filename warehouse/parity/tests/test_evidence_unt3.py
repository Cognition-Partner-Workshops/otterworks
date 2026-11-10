"""Offline UNT-3 checks; snapshot negative controls are not live mapping parity."""
from copy import deepcopy
from datetime import datetime

from jinja2 import Environment
import pytest

from parity.evidence import cell, full_compare, replay_gate
from parity import evidence_unt3 as unt3
from runner import expr


def fixture():
    return {'columns': ['EVENT_ID', 'EVENT_TYPE', 'DOCUMENT_ID', 'EVENT_TS', 'DETAILS'],
            'types': {'EVENT_ID': ['bigint', None, 64, 0, None],
                      'EVENT_TYPE': ['character', 12, None, None, None],
                      'DOCUMENT_ID': ['bigint', None, 64, 0, None],
                      'EVENT_TS': ['timestamp without time zone', None, None, None, 0],
                      'DETAILS': ['character varying', 160, None, None, None]},
            'rows': [[cell(1), cell('DOC_VIEW    '), cell(0), cell(datetime(2026, 11, 9)), cell(None)]]}


def test_positive_empty_and_order_independent():
    snap = fixture()
    assert replay_gate(snap, snap, snap, ['EVENT_ID'], ['EVENT_ID'])['passed']
    snap['rows'] = []
    assert replay_gate(snap, snap, snap, ['EVENT_ID'], ['EVENT_ID'])['passed']


@pytest.mark.parametrize('case', ['unpadded', 'null', 'null_instead_of_zero', 'timestamp',
                                 'timestamp_type', 'duplicate', 'missing', 'id'])
def test_negative_controls(case):
    before = fixture()
    after = deepcopy(before)
    if case == 'unpadded':
        after['rows'][0][1] = cell('DOC_VIEW')
    elif case == 'null':
        after['rows'][0][4] = cell('')
    elif case == 'null_instead_of_zero':
        after['rows'][0][2] = cell(None)
    elif case == 'timestamp':
        after['rows'][0][3] = cell(datetime(2026, 11, 9, microsecond=1))
    elif case == 'timestamp_type':
        after['types']['EVENT_TS'][-1] = 9
    elif case == 'duplicate':
        after['rows'].append(after['rows'][0])
    elif case == 'missing':
        after['rows'] = []
    elif case == 'id':
        after['rows'][0][0] = cell(2)
    assert not full_compare(before, after, ['EVENT_ID'])['equal']
    assert not replay_gate(before, before, after, ['EVENT_ID'], ['EVENT_ID'])['passed']


def test_nonempty_rejects_fail():
    rejects = fixture()
    expected = deepcopy(rejects)
    expected['rows'] = []
    assert not full_compare(expected, rejects, ['EVENT_ID'])['equal']


def test_readonly_guard():
    q = unt3.ReadOnlyQueries(None)
    for sql in ['INSERT INTO X VALUES (1)', 'CREATE TABLE X(A INT)', 'ALTER TABLE X SET COMMENT=\'a\'',
                'DELETE FROM X', 'COPY INTO X', 'MERGE INTO X', 'CALL X()']:
        with pytest.raises(ValueError, match='read-only'):
            q.run(sql)


def test_ownership_and_exact_build_command():
    with pytest.raises(ValueError, match='only the two'):
        unt3.owned('m_SFX_LOGIN_EVENT')
    command = unt3.build_command(unt3.MAPPINGS[1], 'unique-step')
    assert command[2:] == ['build', '--select', 'pc_audit__audit_event', '--step', 'unique-step',
                            '--mapping', 'm_SFX_AUDIT_EVENT']
    assert '--full-refresh' not in command


def test_model_contract_and_shared_reject_predicates():
    models = unt3.ROOT / 'warehouse/dbt/models/pc/audit'
    rendered = {}
    configs = {}
    for mapping in unt3.MAPPINGS:
        model = unt3.owned(mapping)['dbt_model']
        def config(**kwargs):
            configs[model] = kwargs
            return ''
        sql = Environment().from_string((models / (model + '.sql')).read_text()).render(
            config=config, source=lambda *args: 'PC_SRC.AUDIT_EVENT',
            ref=lambda name: 'PC_AUDIT.STG_AUDIT_EVENT')
        assert 'where not (' + unt3.reject_predicate(mapping) + ')' in sql
        assert 'distinct' not in sql.lower()
        rendered[model] = sql
    assert configs['pc_audit__stg_audit_event']['materialized'] == 'table'
    assert configs['pc_audit__audit_event'] == dict(materialized='incremental',
                                                  incremental_strategy='merge', unique_key='EVENT_ID',
                                                  full_refresh=False)
    assert 'from PC_AUDIT.STG_AUDIT_EVENT' in rendered['pc_audit__audit_event']
    assert 'rpad(left(upper(trim(EVENT_TYPE' in rendered['pc_audit__audit_event']
    assert 'trim(left(DETAILS,160)' in rendered['pc_audit__stg_audit_event']


@pytest.mark.parametrize('value,expected', [(None, 0), (-1, 0), (0, 0), (1, 1)])
def test_runner_numeric_iif(value, expected):
    context = expr.CompileContext(port_types={'DOCUMENT_ID': 'bigint'})
    fn = expr.compile_expr('IIF(DOCUMENT_ID > 0, DOCUMENT_ID)', context)
    assert fn({'DOCUMENT_ID': value}) == expected


def test_runner_null_empty_concat_trim_conversion_and_precision():
    from runner.engine import coerce
    context = expr.CompileContext(port_types={'V': 'string'})
    for value in (None, ''):
        assert expr.compile_expr('UPPER(LTRIM(RTRIM(V)))', context)({'V': value}) == value
    assert expr.compile_expr("V || ' by user ' || TO_CHAR(NULL)", context)({'V': None}) == ' by user '
    assert expr.compile_expr('ISNULL(V)', context)({'V': ''}) == 0
    assert expr.compile_expr('ISNULL(V)', context)({'V': None}) == 1
    assert coerce('  abcdef  ', 'string', 5) == '  abc'
    assert expr.compile_expr('TO_BIGINT(V)', context)({'V': '12.9suffix'}) == 12
    with pytest.raises(expr.TransformationError):
        expr.compile_expr('TO_BIGINT(V)', context)({'V': 'bad'})
    with pytest.raises(expr.TransformationError):
        expr.compile_expr("TO_DATE(V,'YYYY-MM-DD HH24:MI:SS')", context)({'V': 'bad'})


def test_duplicate_reporting_and_manifest_fingerprint():
    snap = fixture()
    assert unt3.duplicate_keys(snap) == 0
    snap['rows'] *= 3
    assert unt3.duplicate_keys(snap) == 2
    assert unt3.fingerprint(snap) == unt3.fingerprint(deepcopy(snap))


def test_preflight_rejects_wrong_manifest_before_query(tmp_path, monkeypatch):
    monkeypatch.setattr(unt3, 'OUT', tmp_path)
    (tmp_path / 'manifest.json').write_text('{}')
    with pytest.raises(ValueError, match='SHA256 mismatch'):
        unt3.frozen_input(None, tmp_path)


def test_run_requires_preflight_before_subprocess(tmp_path, monkeypatch):
    monkeypatch.setattr(unt3, 'DEST', tmp_path)
    with pytest.raises(FileNotFoundError):
        unt3.run(unt3.MAPPINGS[0], 1)


def test_nonempty_raw_oracle_rejects_are_not_invented(tmp_path, monkeypatch):
    monkeypatch.setattr(unt3, 'OUT', tmp_path)
    path = tmp_path / unt3.MAPPINGS[0] / 'oracle1'
    path.mkdir(parents=True)
    (path / 'rejects.json').write_text('[{"rows": ["bad"]}]')
    with pytest.raises(ValueError, match='lossy'):
        unt3.reject_template(unt3.MAPPINGS[0], fixture())


@pytest.mark.parametrize('nonempty_rejects', [False, True])
def test_replay_wires_target_and_reject_gates(tmp_path, monkeypatch, nonempty_rejects):
    mapping = unt3.MAPPINGS[1]
    snap = fixture()
    empty = dict(columns=snap['columns'], types=snap['types'], rows=[])
    monkeypatch.setattr(unt3, 'DEST', tmp_path)
    monkeypatch.setattr(unt3, 'oracle', lambda mapping: snap)
    monkeypatch.setattr(unt3, 'reject_template', lambda mapping, template: empty)
    for n in (1, 2):
        path = tmp_path / mapping / f'run{n}'
        unt3.dump(path / 'target.json', snap)
        unt3.dump(path / 'rejects.json', snap if nonempty_rejects else empty)
    if nonempty_rejects:
        with pytest.raises(ValueError, match='Replay parity failed'):
            unt3.replay(mapping)
    else:
        unt3.replay(mapping)
    assert unt3.load(tmp_path / mapping / 'replay.json')['passed'] != nonempty_rejects


def test_export_rejects_uses_exact_predicate_and_typed_rows(tmp_path, monkeypatch):
    snap = fixture()
    monkeypatch.setattr(unt3, 'oracle', lambda mapping: snap)
    monkeypatch.setattr(unt3, 'fetched', lambda *args, **kwargs: snap)
    monkeypatch.setattr(unt3, 'reject_template', lambda mapping, template:
                        dict(columns=snap['columns'], types=snap['types'], rows=[]))
    class Query:
        def run(self, sql):
            assert sql == 'SELECT * FROM SFX_D1110_AFTER.PC_AUDIT.STG_AUDIT_EVENT WHERE EVENT_ID IS NULL'
            return snap['columns'], [(None, 'DOC_VIEW    ', 0, datetime(2026, 11, 9), None)]
    assert not unt3.export_rejects(Query(), unt3.MAPPINGS[1], tmp_path)['equal']
    assert unt3.load(tmp_path / 'rejects.json')['rows'][0][2] == cell(0)


def test_adapter_query_ids():
    assert unt3.adapter_query_ids([None, {}, {'query_id': 'a'}, {'sfqid': 'b'}]) == ['a', 'b']


def test_require_equal_fails_missing_row(tmp_path):
    snap = fixture()
    empty = dict(columns=snap['columns'], types=snap['types'], rows=[])
    with pytest.raises(ValueError, match='Full multiset mismatch'):
        unt3.require_equal(snap, empty, tmp_path / 'result.json')
