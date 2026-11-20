import duckdb
import pytest

from parity.ladder import local_compare
from parity import object_board as board


@pytest.mark.parametrize('old,new,passed', [
    ([], [], True),
    (['x'], ['x'], True),
    (['x '], ['x'], True),
    (['x '], ['y'], False),
    (['x ', 'x '], ['x'], False),
    ([None], [None], True),
])
@pytest.mark.parametrize('declared_char', [True, False])
def test_owner_char_padding_only(monkeypatch, old, new, passed, declared_char):
    from parity import ladder
    monkeypatch.setattr(ladder, 'char_columns', lambda source: ['VALUE'] if declared_char else [])
    with duckdb.connect() as before, duckdb.connect() as after:
        for db, schema, values in ((before, 'SFX_AUDIT', old), (after, 'AUDIT', new)):
            db.execute('CREATE SCHEMA '+schema)
            db.execute('CREATE TABLE '+schema+'.T (ID INTEGER, VALUE VARCHAR)')
            for value in values:
                db.execute('INSERT INTO '+schema+'.T VALUES (1, ?)', [value])
        result = local_compare(before, after, 'SFX_AUDIT.T', 'AUDIT.T')
        expected = passed if declared_char else old == new
        assert result['passed'] is expected
        assert result['comparison_rules']['trailing_pad_insensitive'] == (['VALUE'] if declared_char else [])
        if old == ['x '] and new == ['x']:
            assert not local_compare(before, after, 'SFX_AUDIT.T', 'AUDIT.T', approved_decisions=False)['passed']
            monkeypatch.setattr(board, 'relation_contract', lambda objects: objects)
            obj = dict(id='char', name='char', kind='table', wave=1, owner='owner',
                       subject_area='audit', system='teradata', licence_dependency='teradata',
                       target_type='table', output_relations=['SFX_AUDIT.T'])
            row = board.build_board({'objects': [obj]}, audit_before=before,
                                    audit_after=after, audit_available={'AUDIT.T'})['rows'][0]
            assert row['status'] == ('green' if expected else 'red')
            assert row['snowflake'] == 'red'


def test_owner_registry_preserves_all_decisions():
    import yaml
    from parity.owner_decisions import decision_registry, SFG1120_DECISIONS
    registry = decision_registry()
    assert len(SFG1120_DECISIONS) == 6
    manifest = yaml.safe_load((board.ROOT / 'migration/dw-exit/manifest.yaml').read_text())
    names = {obj['name'] for obj in manifest['objects']}
    assert all(name in names for decision in SFG1120_DECISIONS for name in decision.get('board_objects', []))
    assert all(d in registry for d in SFG1120_DECISIONS)
    assert any(d['decision_id'] == 'audit-archive-retirement' for d in registry)
    assert any(d['decision_id'] == 'dbc-missing-query-log-fields' for d in registry)
    retirement = next(d for d in registry if d['decision_id'] == 'sfg1120-search-history-retirement')
    assert retirement['drop_order'] == ['SFX_DOCUMENTS.V_SEARCH_HISTORY', 'SFX_DOCUMENTS.SEARCH_INDEX_LOG']
    assert next(d for d in registry if d['decision_id'] == 'sfg1120-storage-finance-confirmation')['status'] == 'approved-pending-confirmation'
    payload = board.build_board({'objects': []})
    assert payload['owner_decisions'] == registry


@pytest.mark.parametrize('area', ['billing', 'content'])
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
        assert row['snowflake'] == 'red'
        assert row['snowflake_reason'] == board.SNOWFLAKE_REASON
        assert row['status'] == row['local_duckdb'] == 'red'
        assert row['reason'] == 'held back at combine pending fixes/owner decisions'


def test_full_manifest_retirements_and_dbc_contract(monkeypatch):
    import yaml
    from parity import dbc_retire
    monkeypatch.setattr(dbc_retire, 'emulator', lambda *args: {'status': 'red', 'reason': 'not run'})
    manifest = yaml.safe_load((board.ROOT / 'migration/dw-exit/manifest.yaml').read_text())
    rows = board.build_board(manifest)['rows']
    approved = {name for decision in board.approved_retirements() for name in decision['board_objects']}
    assert len(approved) == 12
    assert {row['name'] for row in rows if row['status'] == 'retired'} == approved
    assert all(row['subject_area'] in ('audit', 'users', 'documents') for row in rows if row['status'] == 'retired')
    assert all(row['snowflake'] == 'red' for row in rows)
    for row in rows:
        if row['subject_area'] in ('billing', 'content'):
            assert row['status'] == 'red'
        if row['subject_area'] == 'dbc':
            query_log = row['name'].split('.')[-1] in ('DBC_QRYLOG', 'QRYLOGV')
            assert row['status'] == ('red' if query_log else 'approved_deviation')
            if query_log:
                assert 'StatementGroup' in row['reason']
    assert all('/devin/sfg1120-integration/' in item['url']
               for row in rows if row['subject_area'] == 'dbc'
               for item in row['metric_evidence'].values())
