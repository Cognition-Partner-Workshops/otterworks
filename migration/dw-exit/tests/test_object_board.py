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


@pytest.fixture(autouse=True)
def offline_credentials(monkeypatch):
    for key in board.CREDENTIALS:
        monkeypatch.delenv(key, raising=False)


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.description = None
        self.sfqid = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, statement):
        self.connection.statements.append(statement)
        self.sfqid = 'query-' + str(len(self.connection.statements))
        self.rows = []
        if statement.startswith('SELECT'):
            if self.connection.error:
                raise self.connection.error
            self.description = [('ID',), ('VALUE',)]
            self.rows = self.connection.rows
        elif statement.startswith('SHOW'):
            self.description = [('name',)]
            self.rows = [(self.connection.routine,)] if self.connection.routine else []

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, rows=(), error=None, routine='JOB'):
        self.rows, self.error, self.routine = rows, error, routine
        self.statements = []
        self.closed = False

    def cursor(self):
        return FakeCursor(self)

    def close(self):
        self.closed = True


def enable_snowflake(monkeypatch, **kwargs):
    for key in board.CREDENTIALS:
        monkeypatch.setenv(key, 'offline-fake')
    connection = FakeConnection(**kwargs)
    def connect(step):
        assert step == 'parity-board'
        return connection
    monkeypatch.setattr(board.snowflake_connection, 'connect', connect)
    return connection


@pytest.mark.parametrize('values',[[],[(1,'x')],[(1,None),(1,'x'),(1,'x')]])
def test_actual_equal_outputs_do_not_migrate(relations,values):
    before,after=relations
    if values:
        before.executemany('INSERT INTO SFX_BILLING.T VALUES (?,?)',values)
        after.executemany('INSERT INTO BILLING.T VALUES (?,?)',values)
    result=board.build_board({'objects':[obj()]},before,after,{'BILLING.T'})
    row=result['rows'][0]
    assert row['legs']['duckdb']['status']=='green'
    assert row['status']=='red'
    assert row['reason']=='snowflake: Snowflake credentials unavailable'
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
    ({},'duckdb: output not materialized: BILLING.T'),
    ({'output_relations':[]},'duckdb: no dependency declared'),
    ({'system':'spark','licence_dependency':'spark'},'duckdb: output not materialized: BILLING.T')])
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
    assert row['reason'] == 'duckdb: output not materialized: BILLING.T'
    assert all(row[field] is None for field in ('row_count', 'column_profile', 'keyed_row_hash', 'sampled_differences'))


def test_empty_manifest_and_snowflake_plan(relations):
    assert board.build_board({'objects':[]})['summary']['rows']==0
    row=board.build_board({'objects':[obj()]},target='snowflake')['rows'][0]
    assert row['status']=='red' and row['row_count'] is None
    assert row['reason']=='duckdb: output not materialized: BILLING.T'
    assert row['legs']['snowflake']['reason']=='Snowflake credentials unavailable'
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
            assert row['reason']=='duckdb: '+errors['*']
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


@pytest.mark.parametrize('values', [[], [(1, 'x')], [(1, None), (1, 'x'), (1, 'x')]])
@pytest.mark.parametrize('system', ['spark', 'powercenter'])
def test_snowflake_and_spark_measurements(relations, monkeypatch, values, system):
    before, after = relations
    if values:
        before.executemany('INSERT INTO SFX_BILLING.T VALUES (?,?)', values)
        after.executemany('INSERT INTO BILLING.T VALUES (?,?)', values)
    connection = enable_snowflake(monkeypatch, rows=values)
    monkeypatch.setenv('RUN_TOKEN', 'sfx1119')
    result = board.build_board({'objects': [obj(system=system)]}, before, after, {'BILLING.T'})
    row = result['rows'][0]
    assert row['status'] == 'green'
    assert row['legs']['snowflake']['row_count'] == {'before': len(values), 'after': len(values)}
    assert row['legs']['snowflake']['query_ids'] == ['query-1', 'query-2', 'query-3']
    assert connection.statements == [
        'ALTER SESSION SET QUERY_TAG=\'{"act":"prove","run_id":"sfx1119","step":"parity-board"}\'',
        "ALTER SESSION SET TIMEZONE='UTC'",
        'SELECT * FROM "SFX_1119"."BILLING"."T"']
    assert connection.closed
    assert result['summary']['legs']['snowflake'] == {'green': 1, 'red': 0, 'measured': 1}


def test_snowflake_mismatch(relations, monkeypatch):
    before, after = relations
    enable_snowflake(monkeypatch, rows=[(1, 'wrong')])
    row = board.build_board({'objects': [obj()]}, before, after, {'BILLING.T'})['rows'][0]
    assert row['reason'] == 'snowflake: measured parity mismatch'
    assert row['legs']['snowflake']['sampled_differences']['SFX_BILLING.T']
    assert row['legs']['duckdb']['status'] == 'green'


@pytest.mark.parametrize('missing', [True, False])
def test_snowflake_query_failure(relations, monkeypatch, missing):
    class QueryError(Exception):
        errno = 2003 if missing else 1234
    enable_snowflake(monkeypatch, error=QueryError('denied'))
    row = board.build_board({'objects': [obj()]}, *relations, {'BILLING.T'})['rows'][0]
    reason = row['legs']['snowflake']['reason']
    assert reason == ('output not materialized in Snowflake: SFX_1119.BILLING.T' if missing else 'measurement failed: denied')
    assert row['legs']['snowflake']['query_ids'][-1] == 'query-3'


@pytest.mark.parametrize('missing_key', board.CREDENTIALS)
def test_no_login_with_any_missing_credential(monkeypatch, missing_key):
    for key in board.CREDENTIALS:
        monkeypatch.setenv(key, 'offline-fake')
    monkeypatch.delenv(missing_key)
    def forbidden(*args):
        pytest.fail('must not connect')
    monkeypatch.setattr(board.snowflake_connection, 'connect', forbidden)
    rows = board.build_board({'objects': [obj(), obj(id='two', output_relations=[])]})['rows']
    assert all(r['legs']['snowflake']['reason'] == 'Snowflake credentials unavailable' for r in rows)


@pytest.mark.parametrize('case', ['green', 'dependency', 'missing_dependency', 'routine', 'no_dependency', 'cycle'])
@pytest.mark.parametrize('kind', ['workflow', 'macro'])
def test_no_output_dependency_proofs(relations, monkeypatch, tmp_path, case, kind):
    connection = enable_snowflake(monkeypatch, routine=None if case == 'routine' else 'JOB')
    artifact = tmp_path / 'converted.sql'
    if case != 'routine':
        artifact.touch()
    dependency = obj(id='dep', subject_area='other')
    routine = obj(id='routine', output_relations=[], kind=kind, target='TRANSFORM.JOB',
                  converted_artifact=str(artifact), depends_on=['dep'])
    if case == 'no_dependency':
        routine['depends_on'] = []
    if case == 'missing_dependency':
        routine['depends_on'] = ['unknown']
    if case == 'cycle':
        routine['depends_on'] = ['routine']
    available = set() if case == 'dependency' else {'BILLING.T'}
    if case == 'dependency':
        connection.rows = [(1, 'wrong')]
    result = board.build_board({'objects': [dependency, routine]}, *relations, available, subject_area='billing')
    assert len(result['rows']) == result['summary']['rows'] == 1
    row = result['rows'][0]
    if case == 'green':
        assert row['status'] == 'green'
        assert any(s.startswith('SHOW TASKS' if kind == 'workflow' else 'SHOW PROCEDURES') for s in connection.statements)
    else:
        expected = {'dependency': 'dependency red: dep', 'missing_dependency': 'dependency red: unknown',
                    'routine': 'routine missing: TRANSFORM.JOB', 'no_dependency': 'no dependency declared',
                    'cycle': 'dependency red: routine'}[case]
        assert all(leg['reason'] == expected for leg in row['legs'].values())
    assert row['row_count'] is None


def test_area_filter_cli():
    output = subprocess.check_output(['make', '-n', 'sfx-manifest-board', 'AREA=billing'], cwd=ROOT, text=True)
    assert '--subject-area "billing"' in output


def test_spark_registry_outputs(tmp_path, monkeypatch):
    monkeypatch.setattr(board, 'ROOT', tmp_path)
    registry = tmp_path / 'etl/spark/jobs/registry'
    registry.mkdir(parents=True)
    (registry / 'job.yaml').write_text('output_relations: [SFX_BILLING.T]')
    assert board.declared_outputs(obj(system='spark', output_relations=[])) == ['SFX_BILLING.T']


def test_snowflake_target_still_measures_both_legs(relations, monkeypatch):
    enable_snowflake(monkeypatch)
    row = board.build_board({'objects': [obj()]}, *relations, {'BILLING.T'}, target='snowflake')['rows'][0]
    assert row['status'] == 'green'


@pytest.mark.parametrize('source,destination', [
    ('SFX_BILLING.T;DROP', 'BILLING.T'), ('SFX_BILLING.T', 'BILLING.T;DROP'),
    ('SFX-BILLING.T', 'BILLING.T'), ('SFX_BILLING.T', 'BILL-ING.T')])
def test_snowflake_rejects_invalid_relation_identifiers(relations, monkeypatch, source, destination):
    connection = enable_snowflake(monkeypatch)
    measurements = board.SnowflakeMeasurements()
    try:
        with pytest.raises(ValueError, match='Invalid identifier'):
            measurements.compare(relations[0], source, destination)
        assert not any(s.startswith('SELECT') for s in connection.statements)
    finally:
        measurements.close()


@pytest.mark.parametrize('column,kind,reason', [
    ('BAD;COLUMN', 'INTEGER', 'Invalid identifier'),
    ('ID', 'INTEGER); DROP TABLE snapshot; --', 'Unsupported snapshot column type')])
def test_snowflake_rejects_invalid_staging_metadata(monkeypatch, column, kind, reason):
    connection = enable_snowflake(monkeypatch)
    class Metadata:
        def execute(self, statement, parameters):
            assert statement == 'DESCRIBE SELECT * FROM query_table(?)'
            assert parameters == ['SFX_BILLING.T']
            return self

        def fetchall(self):
            return [(column, kind), ('VALUE', 'VARCHAR')]

    original = connection.cursor
    def cursor():
        result = original()
        execute = result.execute
        def matching_columns(statement):
            execute(statement)
            if statement.startswith('SELECT'):
                result.description = [(column,), ('VALUE',)]
        result.execute = matching_columns
        return result
    monkeypatch.setattr(connection, 'cursor', cursor)
    measurements = board.SnowflakeMeasurements()
    try:
        with pytest.raises(ValueError, match=reason):
            measurements.compare(Metadata(), 'SFX_BILLING.T', 'BILLING.T')
    finally:
        measurements.close()
