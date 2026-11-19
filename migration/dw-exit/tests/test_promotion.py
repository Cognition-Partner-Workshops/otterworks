import json
from pathlib import Path
import subprocess
import sys

import duckdb
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'migration/dw-exit/parity'))
import object_board as parity_board
import promote as promotion
from warehouse.run_config import render


class FakeSnowflake:
    def __init__(self):
        self.rows = {'MATCH': [(1,)], 'MISMATCH': [(2,)], 'LOCAL_RED': [(1,)], 'OUTSIDE': [(1,)]}
        self.statements = []
        self.records = []
        self.pending = []
        self.fail_commit = False
        self.closed = False

    def cursor(self):
        return FakeCursor(self)

    def close(self):
        self.closed = True


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, sql, parameters=()):
        fake = self.connection
        fake.statements.append(sql)
        self.sfqid = f'query-{len(fake.statements)}'
        self.description = [('ID',)] if sql.startswith('SELECT') else []
        self.rows = fake.rows[sql.split('"')[-2]] if self.description else []
        if sql.startswith('CREATE SCHEMA'):
            assert sql == 'CREATE SCHEMA IF NOT EXISTS IDENTIFIER(?) COMMENT = ?'
            assert parameters[0] == render('__RUN_DATABASE__.MIGRATION_CONTROL')
        if sql.startswith('CREATE TABLE'):
            assert sql.startswith('CREATE TABLE IF NOT EXISTS IDENTIFIER(?)')
            assert parameters[0] == render('__RUN_DATABASE__.MIGRATION_CONTROL.OBJECTS')
        if sql == 'COMMIT':
            if fake.fail_commit:
                raise RuntimeError('fake commit failed')
            fake.records.extend(fake.pending)
            fake.pending.clear()
        elif sql == 'ROLLBACK':
            fake.pending.clear()

    def executemany(self, sql, parameters):
        assert sql.startswith('MERGE INTO IDENTIFIER(?)')
        assert 't.SUBJECT_AREA=s.SUBJECT_AREA' in sql and 't.OBJECT_TYPE=s.OBJECT_TYPE' in sql
        assert 't.OBJECT_NAME=s.OBJECT_NAME' in sql
        assert "MIGRATION_STATUS='migrated', PARITY_STATUS='verified'" in sql
        self.connection.statements.append(sql)
        self.connection.pending.extend(parameters)

    def fetchall(self):
        return self.rows


@pytest.fixture
def estate(tmp_path, monkeypatch):
    for key in parity_board.CREDENTIALS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv('RUN_TOKEN', 'sfx1119')
    target = tmp_path / 'target.duckdb'
    monkeypatch.setenv('BOARD_DUCKDB_PATH', str(target))
    objects = [dict(id=name, name=f'SFX_{schema}.{name}', kind='table', wave=1, owner='data',
                    subject_area=schema.lower(), licence_dependency=licence, status='not_started',
                    source='source.sql', target=f'{schema}.{name}', target_type='dbt_model',
                    output_relations=[f'SFX_{schema}.{name}'] if name != 'UNMEASURED' else [])
               for name, schema, licence in [('MATCH', 'AUDIT', 'teradata'),
                                             ('MISMATCH', 'AUDIT', 'none'),
                                             ('LOCAL_RED', 'AUDIT', 'teradata'),
                                             ('UNMEASURED', 'AUDIT', 'powercenter'),
                                             ('OUTSIDE', 'USERS', 'teradata')]]
    manifest = tmp_path / 'manifest.yaml'
    manifest.write_text(yaml.safe_dump({'objects': objects}))
    with duckdb.connect(str(target)) as after:
        after.execute('CREATE SCHEMA AUDIT; CREATE SCHEMA USERS')
        for obj in objects:
            value = 2 if obj['id'] == 'LOCAL_RED' else 1
            after.execute(f"CREATE TABLE {obj['target']} AS SELECT {value}::INTEGER AS ID")

    def source_snapshot(dsn, names):
        before = duckdb.connect()
        before.execute('CREATE SCHEMA SFX_AUDIT; CREATE SCHEMA SFX_USERS')
        for name in names:
            before.execute(f'CREATE TABLE {name} AS SELECT 1::INTEGER AS ID')
        return before, names, {}

    monkeypatch.setattr(parity_board, 'source_snapshot', source_snapshot)
    return manifest


@pytest.fixture
def snowflake(estate, monkeypatch):
    fake = FakeSnowflake()
    for key in parity_board.CREDENTIALS:
        monkeypatch.setenv(key, 'fake')
    monkeypatch.setattr(parity_board.snowflake_connection, 'connect', lambda step: fake)
    return fake


def test_promote_only_fresh_green_objects_in_selected_area(estate, snowflake, monkeypatch):
    report = promotion.promote('audit', estate)
    assert report['promoted'] == ['MATCH']
    assert {r['id']: r['reason'] for r in report['refused']} == {
        'MISMATCH': 'measured parity mismatch',
        'LOCAL_RED': 'measured parity mismatch',
        'UNMEASURED': 'no dependency declared',
    }
    assert len(snowflake.records) == 1
    control, area, kind, name, source, target, evidence = snowflake.records[0]
    assert control == render('__RUN_DATABASE__.MIGRATION_CONTROL.OBJECTS')
    assert (area, kind, name, source, target) == ('audit', 'table', 'SFX_AUDIT.MATCH', 'source.sql', 'AUDIT.MATCH')
    assert json.loads(evidence) == {'id': 'MATCH', 'run_token': 'sfx1119',
                                   'snowflake_query_ids': ['query-1', 'query-2', 'query-3'],
                                   'legs': {'snowflake': 'green', 'duckdb': 'green'}}
    assert '"run_id":"sfx1119"' in snowflake.statements[0]
    assert all('"USERS"' not in sql for sql in snowflake.statements)
    assert snowflake.closed
    manifest = yaml.safe_load(estate.read_text())
    assert [r['id'] for r in manifest['objects'] if r['status'] == 'migrated'] == ['MATCH']
    monkeypatch.delenv('SNOWFLAKE_ACCOUNT')
    for summary in (report['summary'], parity_board.build_board(manifest, subject_area='audit')['summary']):
        assert summary['migrated'] == 1
        assert summary['migrated_areas'] == 0
        assert summary['licence_remaining'] == 2
        assert summary['licence_total'] == 3


def test_entire_area_counts_only_when_complete(estate, snowflake):
    report = promotion.promote('users', estate)
    assert report['promoted'] == ['OUTSIDE']
    assert report['refused'] == []
    assert report['summary']['migrated_areas'] == 1
    assert report['summary']['licence_remaining'] == 0


@pytest.mark.parametrize('run_token', ['sfx1119', 'sfx-test'])
def test_retirement_control_write_offline(run_token, monkeypatch):
    calls = []

    class Cursor(FakeCursor):
        def execute(self, sql, parameters=()):
            calls.append((sql, parameters))

        def executemany(self, sql, parameters):
            calls.append((sql, parameters))

    class Connection(FakeSnowflake):
        def cursor(self):
            return Cursor(self)

    def forbidden(*args):
        pytest.fail('retirement writer opened a Snowflake connection')

    monkeypatch.setattr(parity_board.snowflake_connection, 'connect', forbidden)
    obj = dict(id='catalog', status='retired', target_type='retire', kind='catalog',
               name='DBC.QRYLOGV', source='dbql.csv', subject_area='dbc',
               target='SNOWFLAKE.ACCOUNT_USAGE', retirement_reason='replaced by SNOWFLAKE.ACCOUNT_USAGE')
    promotion.write_retirements(Connection(), [obj, dict(obj, status='not_started')], run_token)
    schema = ('SFX_1119' if run_token == 'sfx1119' else 'SFX_TEST') + '.MIGRATION_CONTROL'
    assert calls[0][0] == 'ALTER SESSION SET QUERY_TAG = ?'
    assert json.loads(calls[0][1][0]) == {'run_id': run_token, 'act': 'retire', 'step': 'migration-control'}
    assert calls[1][1][0] == schema
    assert calls[2][1][0] == schema + '.OBJECTS'
    assert calls[3] == ('BEGIN', ())
    merge, records = calls[4]
    assert merge.startswith('MERGE INTO IDENTIFIER(?)')
    assert 'MIGRATION_STATUS=s.MIGRATION_STATUS, PARITY_STATUS=s.PARITY_STATUS' in merge
    assert 'PARSE_JSON(?) AS EVIDENCE' in merge
    [record] = records
    assert record[:-1] == (schema + '.OBJECTS', 'dbc', 'catalog', 'DBC.QRYLOGV', 'dbql.csv',
                           'SNOWFLAKE.ACCOUNT_USAGE', 'retired', 'retired')
    assert json.loads(record[-1]) == {'id': 'catalog', 'run_token': run_token,
                                      'retirement_reason': obj['retirement_reason']}
    assert calls[5:] == [('COMMIT', ())]


def test_retired_object_stays_out_of_promotion(estate, snowflake):
    manifest = yaml.safe_load(estate.read_text())
    obj = next(obj for obj in manifest['objects'] if obj['id'] == 'MATCH')
    obj.update(status='retired', target_type='retire', retirement_reason='no DBQL usage in 90-day window')
    estate.write_text(yaml.safe_dump(manifest))
    before = estate.read_bytes()
    report = promotion.promote('audit', estate)
    assert report['promoted'] == []
    assert 'MATCH' not in {r['id'] for r in report['refused']}
    assert estate.read_bytes() == before
    assert not snowflake.records
    row = next(r for r in report['rows'] if r['id'] == 'MATCH')
    assert row['status'] == row['migration_status'] == 'retired'
    assert row['reason'] == obj['retirement_reason']
    assert {leg['status'] for leg in row['legs'].values()} == {'retired'}
    assert row['row_count'] is None
    assert all('"MATCH"' not in sql for sql in snowflake.statements)
    assert report['summary']['retired'] == 1
    assert report['summary']['red'] == 3
    assert report['summary']['licence_remaining'] == 2
    assert report['summary']['licence_total'] == 3
    assert report['licence_counters']['licence_dependencies']['remaining'] == 2


def test_outage_refuses_every_object_even_with_green_duckdb(estate, monkeypatch):
    def forbidden(*args):
        pytest.fail('Snowflake connection attempted during credential outage')

    monkeypatch.setattr(parity_board.snowflake_connection, 'connect', forbidden)
    before = estate.read_bytes()
    report = promotion.promote('audit', estate)
    assert report['promoted'] == []
    assert len(report['refused']) == 4
    assert {r['reason'] for r in report['refused']} == {'Snowflake credentials unavailable'}
    assert next(r for r in report['rows'] if r['id'] == 'MATCH')['legs']['duckdb']['status'] == 'green'
    assert report['summary']['migrated'] == 0
    assert report['summary']['licence_remaining'] == 3
    assert estate.read_bytes() == before


def test_failed_control_commit_does_not_update_manifest(estate, snowflake):
    snowflake.fail_commit = True
    before = estate.read_bytes()
    with pytest.raises(RuntimeError, match='fake commit failed'):
        promotion.promote('audit', estate)
    assert not snowflake.records and not snowflake.pending
    assert snowflake.statements[-1] == 'ROLLBACK'
    assert snowflake.closed
    assert estate.read_bytes() == before


def test_unknown_area_makes_no_connection(estate, monkeypatch):
    def forbidden():
        pytest.fail('Snowflake connection attempted for unknown area')

    monkeypatch.setattr(promotion, 'SnowflakeMeasurements', forbidden)
    with pytest.raises(ValueError, match='Unknown subject area'):
        promotion.promote('unknown', estate)


@pytest.mark.parametrize('make_args, area', [
    (['sfx-area-promote', 'AREA=audit'], 'audit'),
    (['sfx-billing-promote', 'AREA=audit'], 'billing'),
])
def test_make_targets_share_the_gate(make_args, area):
    output = subprocess.check_output(['make', '-n', 'RUN_TOKEN=sfx1119', *make_args], cwd=ROOT, text=True)
    assert f"parity/promote.py --subject-area '{area}'" in output
    assert 'NS="sfx-1119-before"' in output
