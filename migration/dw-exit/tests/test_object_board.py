import builtins
import importlib.util
from pathlib import Path
import socket
import sys
import subprocess

import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('object_board', ROOT/'migration/dw-exit/parity/object_board.py')
board = importlib.util.module_from_spec(spec)
spec.loader.exec_module(board)
from warehouse.run_config import RunConfig


def obj(**changes):
    return dict(dict(id='one',name='job',kind='mapping',wave=2,owner='data',subject_area='fixture',
                system='powercenter',licence_dependency='powercenter',target_type='dbt_model',
                output_relations=['SFX_BILLING.T']),**changes)


@pytest.fixture
def relations():
    before,after = duckdb.connect(),duckdb.connect()
    before.execute('CREATE SCHEMA SFX_BILLING')
    after.execute('CREATE SCHEMA BILLING')
    before.execute('CREATE TABLE SFX_BILLING.T (ID INTEGER, VALUE VARCHAR)')
    after.execute('CREATE TABLE BILLING.T (ID INTEGER, VALUE VARCHAR)')
    yield before,after
    before.close()
    after.close()


@pytest.mark.parametrize('values',[[],[(1,'x')],[(1,None),(1,'x'),(1,'x')]])
def test_actual_equal_outputs_do_not_migrate(relations,values):
    before,after=relations
    if values:
        before.executemany('INSERT INTO SFX_BILLING.T VALUES (?,?)',values)
        after.executemany('INSERT INTO BILLING.T VALUES (?,?)',values)
    result=board.build_board({'objects':[obj()]},before,after,{'BILLING.T'})
    row=result['rows'][0]
    assert row['status']=='green'
    assert row['row_count']=={'before':len(values),'after':len(values)}
    assert row['keyed_row_hash']['SFX_BILLING.T']['difference']==0
    assert len(row['keyed_row_hash']['SFX_BILLING.T']['before'])==64
    assert result['summary']['migrated']==0
    assert result['summary']['licence_remaining']==result['summary']['licence_total']==1


def test_profiles_hashes_samples_preserve_duplicates_and_nulls(relations):
    before,after=relations
    before.execute("INSERT INTO SFX_BILLING.T VALUES (1,NULL),(1,'x'),(1,'x')")
    after.execute("INSERT INTO BILLING.T VALUES (1,NULL),(1,'x')")
    result=board.build_board({'objects':[obj()]},before,after,{'BILLING.T'})
    row=result['rows'][0]
    assert row['status']=='red'
    assert row['row_count']=={'before':3,'after':2}
    assert row['column_profile']['SFX_BILLING.T']['before']['VALUE']['nulls']==1
    assert row['keyed_row_hash']['SFX_BILLING.T']['difference']==1
    assert row['sampled_differences']['SFX_BILLING.T'][0]['key']==[1]


@pytest.mark.parametrize('changes,reason',[
    ({},'output not materialized: BILLING.T'),
    ({'output_relations':[]},'no declared output relation'),
    ({'system':'spark','licence_dependency':'spark'},'source on Spark baseline PR')])
def test_unavailable_never_invents_measurements(changes,reason):
    row=board.build_board({'objects':[obj(**changes)]})['rows'][0]
    assert row['status']=='red' and row['reason']==reason
    assert all(row[field] is None for field in ('row_count','column_profile','keyed_row_hash','sampled_differences'))


def test_measurement_error_and_column_mismatch(relations):
    before,after=relations
    after.execute('ALTER TABLE BILLING.T RENAME VALUE TO OTHER')
    row=board.build_board({'objects':[obj()]},before,after,{'BILLING.T'})['rows'][0]
    assert row['status']=='red' and 'column names/order' in row['reason']
    assert row['row_count'] is None


def test_merged_spark_sources_are_linked_without_fabricating_outputs(tmp_path, monkeypatch):
    monkeypatch.setattr(board, 'ROOT', tmp_path)
    (tmp_path / 'job.py').touch()
    row = board.build_board({'objects': [obj(system='spark', licence_dependency='spark',
        source='job.py', source_ref='demo-snowflake-dw-exit')]})['rows'][0]
    assert row['source'] == 'job.py'
    assert row['source_ref'] == 'demo-snowflake-dw-exit'
    assert row['status'] == 'red'
    assert row['reason'] == 'Spark source available; output not materialized locally'
    assert all(row[field] is None for field in ('row_count', 'column_profile', 'keyed_row_hash', 'sampled_differences'))


def test_empty_manifest_and_snowflake_plan(relations):
    assert board.build_board({'objects':[]})['summary']['rows']==0
    row=board.build_board({'objects':[obj()]},target='snowflake')['rows'][0]
    assert row['status']=='red' and row['row_count'] is None
    assert row['reason']=='Snowflake target selected; execution disabled'
    with pytest.raises(ValueError):
        board.build_board({'objects':[]},target='unknown')


def test_two_columns_and_subject_area_summary(relations, monkeypatch):
    monkeypatch.setattr(board, 'HELD_BACK_AREAS', frozenset())
    before, after = relations
    before.execute("INSERT INTO SFX_BILLING.T VALUES (1, 'x')")
    after.execute("INSERT INTO BILLING.T VALUES (1, 'x')")
    manifest = {'objects': [obj(subject_area='billing'), obj(id='two', name='missing', subject_area='billing', output_relations=[]),
                            obj(id='three', name='spark', subject_area='users', system='spark')]}
    result = board.build_board(manifest, before, after, {'BILLING.T'})
    for row, expected in zip(result['rows'], ('green', 'red', 'red'), strict=True):
        assert set(row['targets']) == {'duckdb', 'snowflake'}
        assert row['status'] == row['targets']['duckdb']['status'] == expected
        assert row['migration_status'] == 'not_started'
        assert row['targets']['snowflake'] == {
            'status': 'red', 'reason': board.SNOWFLAKE_REASON,
            'row_count': None, 'column_profile': None, 'keyed_row_hash': None,
            'sampled_differences': None,
        }
    duckdb_cell = result['rows'][0]['targets']['duckdb']
    assert duckdb_cell['row_count'] == {'before': 1, 'after': 1}
    assert duckdb_cell['keyed_row_hash']['SFX_BILLING.T']['difference'] == 0
    assert result['summary']['targets'] == {
        'duckdb': {'green': 1, 'red': 2}, 'snowflake': {'green': 0, 'red': 3},
    }
    assert result['summary']['by_subject_area'] == {
        'billing': {'duckdb': {'green': 1, 'red': 1}, 'snowflake': {'green': 0, 'red': 2}},
        'users': {'duckdb': {'green': 0, 'red': 1}, 'snowflake': {'green': 0, 'red': 1}},
    }
    readme = board.render_readme(result)
    assert '| billing | 1 green / 1 red | 0 green / 2 red |' in readme
    assert '| Object | Subject area | DuckDB | Snowflake |' in readme
    assert '| job | billing | green | red |' in readme


@pytest.mark.parametrize('target', ['duckdb', 'snowflake'])
def test_snowflake_stays_red_without_network(monkeypatch, relations, target):
    original_import = builtins.__import__

    def deny_snowflake(name, *args, **kwargs):
        assert name.partition('.')[0] != 'snowflake' and name.rsplit('.', 1)[-1] != 'connection', name
        return original_import(name, *args, **kwargs)

    def deny_network(*args, **kwargs):
        pytest.fail('building board cells must not open a network connection')

    isolated_board = importlib.util.module_from_spec(spec)
    with monkeypatch.context() as patch:
        patch.setattr(builtins, '__import__', deny_snowflake)
        patch.setattr(socket, 'socket', deny_network)
        patch.setattr(socket, 'create_connection', deny_network)
        patch.setattr(board.psycopg, 'connect', deny_network)
        spec.loader.exec_module(isolated_board)
        before, after = relations
        result = isolated_board.build_board({'objects': [obj()]}, before, after, {'BILLING.T'}, target=target)
    cell = result['rows'][0]['targets']['snowflake']
    assert cell['status'] == 'red'
    assert cell['reason'] == board.SNOWFLAKE_REASON


def test_straight_conversion_and_missing_input(tmp_path):
    before=duckdb.connect()
    try:
        before.execute('CREATE SCHEMA SFX_BILLING')
        before.execute('CREATE TABLE SFX_BILLING.STG_T (ID INTEGER, VALUE VARCHAR)')
        before.execute('CREATE TABLE SFX_BILLING.T (ID INTEGER, VALUE VARCHAR)')
        before.execute("INSERT INTO SFX_BILLING.STG_T VALUES (1,'abcdefghijkl'),(1,'abcdefghijkl')")
        (tmp_path/'10_load.sql').write_text('INSERT INTO SFX_1119.BILLING.T SELECT * FROM SFX_1119.BILLING.STG_T;')
        (tmp_path/'30_views.sql').write_text('CREATE VIEW SFX_1119.BILLING.V_T AS SELECT * FROM SFX_1119.BILLING.T; CREATE VIEW SFX_1119.BILLING.V_BAD AS SELECT * FROM SFX_1119.BILLING.MISSING;')
        after,ready,errors=board.materialize(before,{'SFX_BILLING.T','SFX_BILLING.STG_T'},tmp_path)
        try:
            assert after.execute('SELECT * FROM BILLING.T').fetchall()==[(1,'abcdefghijkl')]*2
            assert 'BILLING.V_T' in ready
            assert 'BILLING.V_BAD' not in ready and 'input not materialized' in errors['BILLING.V_BAD']
        finally:
            after.close()
        (tmp_path/'10_load.sql').write_text('INSERT INTO')
        (tmp_path/'30_views.sql').write_text('')
        after,ready,errors=board.materialize(before,{'SFX_BILLING.T','SFX_BILLING.STG_T'},tmp_path)
        try:
            assert errors['*']=='conversion parse failed: 10_load.sql'
            row=board.build_board({'objects':[obj()]},before,after,ready,errors)['rows'][0]
            assert row['status']=='red' and row['row_count'] is None
            assert row['reason']==errors['*']
        finally:
            after.close()
    finally:
        before.close()


@pytest.mark.parametrize('token,database,before', [('sfx1119','SFX_1119','sfx-1119-before'),('sfx2220','SFX_2220','sfx-2220-before'),('sfx-lab-a','SFX_LAB_A','sfx-lab-a-before')])
def test_run_config(monkeypatch,token,database,before):
    monkeypatch.setenv('RUN_TOKEN',token)
    config=RunConfig.from_env()
    assert config.database==database and config.before_namespace==before
    assert config.after_namespace==before.removesuffix('before')+'after'
    assert config.render('__RUN_DATABASE__ __RUN_TOKEN__')==database+' '+token
    assert config.environment()['RUN_TOKEN']==token
    with pytest.raises(ValueError):
        RunConfig('sfx; DROP DATABASE test')


def test_manifest_fields_and_spark_references():
    import assess
    estate=assess.build()
    objects=estate['objects']
    assert len(objects)==252
    spark=[r for r in objects if r['system']=='spark']
    assert len(spark)==30 and len({r['source'] for r in spark})==30
    assert all(r['source_ref']=='demo-snowflake-dw-exit' for r in spark)
    assert all(r['licence_dependency'] in {'teradata','powercenter','spark','none'} and r['subject_area'] and r['wave'] and r['owner'] for r in objects)
    assert all(r['status']=='not_started' for r in objects)
    assert estate['counters']['licence_dependencies']['remaining']==252


def test_make_command_line_token_selects_namespace():
    output=subprocess.check_output(['make','-n','sfx-teradata-validate','RUN_TOKEN=sfx2220'],cwd=ROOT,text=True)
    assert 'sfx-2220-before' in output
    assert 'sfx-1119-before' not in output


def test_audit_contract_does_not_change_other_areas():
    audit = obj(subject_area='audit', name='10_summary_daily', kind='bteq', system='teradata')
    billing = obj()
    contracts = board.relation_contract([audit, billing])
    assert contracts[0]['output_relations'] == ['SFX_AUDIT.AUDIT_DAILY_SUMMARY']
    assert contracts[1] == billing
    assert board.build_board({'objects':[billing]})['rows'] == board.base_build_board({'objects':[billing]})['rows']


def test_audit_empty_board_and_missing_proof():
    assert board.build_board({'objects':[]})['summary']['audit']['total'] == 0
    row = board.build_board({'objects':[obj(subject_area='audit', name='10_summary_daily', kind='bteq', system='teradata')]})['rows'][0]
    assert row['status'] == 'red' and row['row_count'] is None
    assert row['reason'] == 'Audit local proof unavailable'
    assert row['snowflake'] == 'red'
    assert row['snowflake_reason'] == 'Snowflake login down for run sfg1120; no live capture/prove'


def test_audit_retirements_keep_setup_read_evidence():
    import yaml
    manifest = yaml.safe_load((ROOT/'migration/dw-exit/manifest.yaml').read_text())
    objects = [o for o in manifest['objects'] if o['subject_area']=='audit' and o['target_type']=='retire']
    rows = board.build_board({'objects':objects})['rows']
    assert len(rows) == 6 and all(r['status']=='retired' for r in rows)
    for row in rows:
        dbql = row['retirement_evidence']['dbql']
        stage = dbql['assessment_usage']['SFX_AUDIT.STG_AUDIT_EVENT_ARCHIVE']
        assert stage['reads'] == 1 and stage['writes'] == 0
        assert stage['records'][0]['query']['UserName'] == 'svc_report_recon'
        assert stage['records'][0]['query']['QueryID'] == '111000000068'
        assert dbql['current_checkout_usage']['SFX_AUDIT.STG_AUDIT_EVENT_ARCHIVE']['records'][0]['query']['QueryID'] == '111000000069'
        assert row['row_count'] is None
    denied = board.build_board({'objects':objects}, target='snowflake')['rows']
    assert all(r['status']=='red' and r['snowflake']=='red' for r in denied)


@pytest.mark.parametrize('approved,identity_match,expected', [(True,True,'approved_deviation'),
                                                           (False,True,'red'),(True,False,'red')])
def test_audit_summary_approval_is_scoped_and_preserves_raw(monkeypatch, approved, identity_match, expected):
    from parity import ladder
    with duckdb.connect() as before, duckdb.connect() as after:
        before.execute('CREATE SCHEMA SFX_AUDIT')
        after.execute('CREATE SCHEMA AUDIT')
        before.execute('CREATE TABLE SFX_AUDIT.AUDIT_DAILY_SUMMARY (SUMMARY_ID INTEGER, VALUE INTEGER)')
        after.execute('CREATE TABLE AUDIT.AUDIT_DAILY_SUMMARY (SUMMARY_ID INTEGER, VALUE INTEGER)')
        before.execute('INSERT INTO SFX_AUDIT.AUDIT_DAILY_SUMMARY VALUES (50001,7)')
        after.execute('INSERT INTO AUDIT.AUDIT_DAILY_SUMMARY VALUES (50002,7)')
        raw = ladder.local_compare(before,after,'SFX_AUDIT.AUDIT_DAILY_SUMMARY','AUDIT.AUDIT_DAILY_SUMMARY')
        before.execute('UPDATE SFX_AUDIT.AUDIT_DAILY_SUMMARY SET SUMMARY_ID=50002')
        normalized = ladder.local_compare(before,after,'SFX_AUDIT.AUDIT_DAILY_SUMMARY','AUDIT.AUDIT_DAILY_SUMMARY')
    monkeypatch.setattr(board,'approved_summary_ids',lambda:approved)
    record = obj(subject_area='audit',name='m_SFX_AUDIT_DAILY_SUMMARY')
    result = board.build_board({'objects':[record]}, audit_pc_results={
        'measurements':{'SFX_AUDIT.AUDIT_DAILY_SUMMARY':normalized},
        'raw_summary_measurement':raw, 'summary_id_contract':'stable date/key',
        'summary_non_identity_multiset_matches':identity_match})['rows'][0]
    assert result['status'] == expected
    assert result['raw_summary_measurement']['keyed_row_hash']['difference'] == 2
    assert result['keyed_row_hash']['SFX_AUDIT.AUDIT_DAILY_SUMMARY']['difference'] == 0


def test_audit_workflow_preserves_non_summary_failure_reason(monkeypatch):
    monkeypatch.setattr(board, 'relation_contract', lambda objects: objects)
    record = obj(subject_area='audit', name='wf_SFX_AUDIT_DAILY',
                 output_relations=['SFX_AUDIT.AUDIT_DAILY_SUMMARY', 'SFX_AUDIT.AUDIT_EVENT'])
    measured = dict(passed=False, row_count={'before': 1, 'after': 1},
                    column_profile={}, keyed_row_hash={}, sampled_differences=[], comparison_rules={})
    summary = dict(measured, passed=True)
    event = dict(measured, reason='event payload mismatch')
    row = board.build_board({'objects': [record]}, audit_pc_results={
        'measurements': {'SFX_AUDIT.AUDIT_DAILY_SUMMARY': summary, 'SFX_AUDIT.AUDIT_EVENT': event},
        'raw_summary_measurement': measured, 'summary_non_identity_multiset_matches': True})['rows'][0]
    assert row['status'] == 'red'
    assert row['reason'] == 'event payload mismatch'
