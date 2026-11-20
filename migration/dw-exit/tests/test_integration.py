import duckdb
import pytest

from parity.ladder import local_compare
from parity import object_board as board


@pytest.mark.parametrize('old,new,passed,pending', [
    ([], [], True, False),
    (['x'], ['x'], True, False),
    (['x '], ['x'], False, True),
    (['x '], ['y'], False, False),
    (['x ', 'x '], ['x'], False, False),
])
def test_char_padding_is_strict(monkeypatch, old, new, passed, pending):
    from parity import ladder
    monkeypatch.setattr(ladder, 'char_columns', lambda source: ['VALUE'])
    with duckdb.connect() as before, duckdb.connect() as after:
        for db, schema, values in ((before, 'SFX_AUDIT', old), (after, 'AUDIT', new)):
            db.execute('CREATE SCHEMA '+schema)
            db.execute('CREATE TABLE '+schema+'.T (ID INTEGER, VALUE VARCHAR)')
            for value in values:
                db.execute('INSERT INTO '+schema+'.T VALUES (1, ?)', [value])
        result = local_compare(before, after, 'SFX_AUDIT.T', 'AUDIT.T')
        assert result['passed'] is passed
        assert ('pending owner decision' in result.get('reason', '')) is pending
        assert result['comparison_rules']['trailing_pad_insensitive'] == []
        if pending:
            monkeypatch.setattr(board, 'relation_contract', lambda objects: objects)
            obj = dict(id='char', name='char', kind='table', wave=1, owner='owner',
                       subject_area='audit', system='teradata', licence_dependency='teradata',
                       target_type='table', output_relations=['SFX_AUDIT.T'])
            row = board.build_board({'objects': [obj]}, audit_before=before,
                                    audit_after=after, audit_available={'AUDIT.T'})['rows'][0]
            assert row['status'] == 'red'
            assert row['reason'] == result['reason']


@pytest.mark.parametrize('area', ['billing', 'documents', 'users', 'content'])
@pytest.mark.parametrize('target_type', ['dbt_model', 'retire'])
@pytest.mark.parametrize('materialized', [False, True])
def test_held_areas_are_red_even_with_equal_outputs(area, target_type, materialized):
    with duckdb.connect() as before, duckdb.connect() as after:
        before.execute('CREATE SCHEMA SFX_BILLING')
        after.execute('CREATE SCHEMA BILLING')
        before.execute('CREATE TABLE SFX_BILLING.T (ID INTEGER)')
        after.execute('CREATE TABLE BILLING.T (ID INTEGER)')
        obj = dict(id=area, name='held', kind='table', wave=1, owner='owner',
                   subject_area=area, system='teradata', licence_dependency='teradata',
                   target_type=target_type, output_relations=['SFX_BILLING.T'])
        row = board.build_board({'objects': [obj]}, before, after,
                                {'BILLING.T'} if materialized else set())['rows'][0]
        assert row['status'] == row['local_duckdb'] == 'red'
        assert row['reason'] == 'held back at combine pending fixes/owner decisions'
