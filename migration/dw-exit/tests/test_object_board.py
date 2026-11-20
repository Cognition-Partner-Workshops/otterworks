import importlib.util
from pathlib import Path
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
    return dict(dict(id='one',name='job',kind='mapping',wave=2,owner='data',subject_area='billing',
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


def test_chain_runs_snowflake_scripting_and_date_formats():
    connection = duckdb.connect()
    try:
        connection.execute('CREATE SCHEMA BILLING')
        connection.execute("CREATE TABLE BILLING.T (ID INTEGER, D DATE)")
        connection.execute("INSERT INTO BILLING.T VALUES (1, DATE '2026-11-09')")
        chain = board.Chain(connection, {'BILLING.T'}, {}, {'BUSINESS_DATE': '20261109'})
        chain.run_text("""CREATE OR REPLACE PROCEDURE SFX_1119.BILLING.P (P_DAY VARCHAR(8))
RETURNS TABLE ()
LANGUAGE SQL
AS
$$
DECLARE
run_day DATE;
BEGIN
run_day := TO_DATE(p_day, 'YYYYMMDD');
LET res RESULTSET := (SELECT ID, TO_CHAR(D, 'YYYY-MM') AS PERIOD FROM SFX_1119.BILLING.T WHERE D <= :run_day);
RETURN TABLE(res);
END;
$$;""", 'routines.sql')
        assert chain.call('SFX_1119.BILLING.P', "'${BUSINESS_DATE}'") == (['ID', 'PERIOD'], [(1, '2026-11')])
        assert chain.query("SELECT TO_DATE('20261109', 'YYYYMMDD') AS D")[1][0][0].isoformat() == '2026-11-09'
    finally:
        connection.close()


def test_float_comparison_and_xsmall_estimate():
    assert board.canonical([0.16246506258069604]) == board.canonical([0.1624650625806961])
    estimate = board.capacity.estimate([{'workload': 'load', 'seconds': 0.5}, {'workload': 'parity', 'seconds': 90}])
    rows = {r['workload']: r for r in estimate['workloads']}
    assert rows['load']['size'] == 'XSMALL' and rows['load']['billed_seconds'] == 120
    assert rows['parity']['billed_seconds'] == 150 and rows['transform']['credits_per_run'] == 0
