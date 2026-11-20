"""All execution engines operate on local fixtures, never Snowflake."""
from pathlib import Path

import duckdb
import pytest
import snowflake.connector

from test_object_board import board, obj

FIXTURES = Path(__file__).parent / 'fixtures/area'


def test_seed_registration_discovers_inputs_outside_manifest(monkeypatch):
    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, *args):
            pass

        def __iter__(self):
            return iter([('sfx_fixture', 'stg_extra', 'id', 'integer', None, None),
                         ('sfx_other', 'stg_extra', 'id', 'integer', None, None)])

        def fetchall(self):
            return [(7,)]

    class Source(Cursor):
        def cursor(self):
            return Cursor()

    monkeypatch.setattr(board.psycopg, 'connect', lambda dsn: Source())
    before, ready, errors = board.source_snapshot('local fixture', set(),
        {'fixture': dict(schema='FIXTURE', seed=['STG_*'])})
    try:
        assert ready == {'SFX_FIXTURE.STG_EXTRA'}
        assert errors == {}
        assert before.execute('SELECT * FROM SFX_FIXTURE.STG_EXTRA').fetchall() == [(7,)]
    finally:
        before.close()


@pytest.fixture(autouse=True)
def no_snowflake(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Snowflake connector called')
    monkeypatch.setattr(snowflake.connector, 'connect', forbidden)
    monkeypatch.setattr(snowflake.connector.connection.SnowflakeConnection, 'connect', forbidden)


@pytest.mark.parametrize('engine', ['sql', 'dbt', 'snowpark'])
@pytest.mark.parametrize('rows', [[], [(1, 'x'), (1, None)]])
def test_registered_engine_goes_green(tmp_path, engine, rows):
    config = dict(schema='FIXTURE', seed=['STG_*'], directory=FIXTURES)
    if engine == 'sql':
        config['sql'] = ['load.sql']
    elif engine == 'dbt':
        config.update(dbt_project=FIXTURES/'dbt', dbt=[dict(model='models/result.sql', target='T')])
    else:
        config['snowpark'] = [dict(job=str(FIXTURES/'job.py'), target='T',
                                  inputs={'STG_T': 'STG_T'})]
    areas = {'fixture': config}
    before = duckdb.connect()
    before.execute('CREATE SCHEMA SFX_FIXTURE')
    for table in ('STG_T', 'T'):
        before.execute('CREATE TABLE SFX_FIXTURE.'+table+' (ID INTEGER, VALUE VARCHAR)')
        if rows:
            before.executemany('INSERT INTO SFX_FIXTURE.'+table+' VALUES (?, ?)', rows)
    try:
        after, ready, errors = board.materialize(before, {'SFX_FIXTURE.STG_T', 'SFX_FIXTURE.T'},
            areas=areas, database=tmp_path/'after.duckdb')
        try:
            result = board.build_board({'objects': [obj(subject_area='fixture',
                system='spark' if engine == 'snowpark' else 'powercenter',
                output_relations=['SFX_FIXTURE.T'])]}, before, after, ready, errors, areas=areas)
            assert result['rows'][0]['targets']['duckdb']['status'] == 'green', errors
            assert result['rows'][0]['targets']['snowflake']['status'] == 'red'
        finally:
            after.close()
    finally:
        before.close()


@pytest.mark.parametrize('engine', ['sql', 'dbt', 'snowpark'])
def test_missing_inputs_stay_red(tmp_path, engine):
    config = dict(schema='FIXTURE', seed=[], directory=FIXTURES)
    if engine == 'sql':
        config['sql'] = ['load.sql']
    elif engine == 'dbt':
        config.update(dbt_project=FIXTURES/'dbt', dbt=[dict(model='models/result.sql', target='T')])
    else:
        config['snowpark'] = [dict(job=str(FIXTURES/'job.py'), target='T', inputs={'STG_T': 'STG_T'})]
    before = duckdb.connect()
    try:
        after, ready, errors = board.materialize(before, set(), areas={'fixture': config},
                                                  database=tmp_path/'after.duckdb')
        try:
            assert 'FIXTURE.T' not in ready
            assert errors
        finally:
            after.close()
    finally:
        before.close()
