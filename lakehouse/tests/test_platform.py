import csv
import os
import shutil
import uuid
from datetime import date
from decimal import Decimal

import pytest
import yaml
from jinja2 import Environment, StrictUndefined
from pyspark.sql import types as T

from lakehouse.orchestration import graph, runner
from lakehouse.parity.engine import compare
from lakehouse.runtime import platform
from lakehouse.runtime.layout import ROOT, data_root, database, delta_path
from lakehouse.runtime.session import create_session


DAY = '20261109'
MODELS = {path.stem: path for layer in ('silver', 'gold')
          for path in (ROOT / 'dbt/models' / layer / 'platform').glob('*.sql')}


@pytest.fixture(scope='module')
def spark():
    original = os.environ.get('NS')
    os.environ['NS'] = 'test-platform-' + uuid.uuid4().hex
    session = create_session()
    yield session
    session.stop()
    shutil.rmtree(data_root())
    if original is None:
        del os.environ['NS']
    else:
        os.environ['NS'] = original


class Models:
    def __init__(self, spark, variables=None):
        self.spark = spark
        self.variables = variables or {}
        self.built = set()
        for name in platform.FEEDS:
            self.feed(name, [])

    def feed(self, name, rows):
        columns = platform.FEEDS[name][1]
        schema = T.StructType([T.StructField(c.lower(), T.StringType()) for c in columns]
                              + [T.StructField('_business_date', T.DateType())])
        self.spark.createDataFrame(rows, schema).createOrReplaceTempView('platform_source_' + name.lower())
        self.built.clear()

    def ref(self, name):
        target = 'platform_test_' + name
        if name not in self.built:
            sql = Environment(undefined=StrictUndefined).from_string(
                (ROOT / 'dbt/macros/legacy_text.sql').read_text() + MODELS[name].read_text()).render(
                source=lambda _, table: 'platform_source_' + table, ref=self.ref,
                env_var=lambda _: DAY, config=lambda **_: '',
                var=lambda name, default: self.variables.get(name, default))
            self.spark.sql(sql).createOrReplaceTempView(target)
            self.built.add(name)
        return target

    def rows(self, name):
        return self.spark.table(self.ref(name)).collect()


def query(identifier, username='User', appid='App', clientid='Client',
          start='2026-10-11 00:00:00', statement='SELECT', error='0', day=date(2026, 11, 9)):
    return ('1', '2026-11-09 01:02:03.123456', str(identifier), username, 'SFX_BILLING',
            appid, clientid, start, '2026-11-09 01:02:04.654321', statement, 'READ',
            'select "quoted"|value\nnext line', '1', '123.123456', '42', error, day)


def feeds(root, rows=None):
    for name, (filename, columns) in platform.FEEDS.items():
        with (root / filename).open('w', newline='', encoding='utf-8') as handle:
            writer = csv.writer(handle)
            writer.writerow(columns)
            writer.writerows((rows or {}).get(name, []))


def test_platform_graph_and_ownership(tmp_path, monkeypatch):
    monkeypatch.setenv('NS', 'test-platform-graph')
    monkeypatch.setenv('PLATFORM_DBQL_LANDING', str(tmp_path))
    nodes = {n['id']: n for n in graph.load()['lakehouse_daily']['nodes']}
    owned = yaml.safe_load((ROOT / 'coverage/domains/platform.yaml').read_text())['legacy_objects']
    assert len(owned) == len(set(owned)) == 7
    assert set(nodes['dbt_platform']['legacy_objects']) == set(owned)
    sensors = {n['id'] for n in nodes.values()
               if n['kind'] == 'feed_sensor' and n['domain'] == 'platform'}
    assert len(sensors) == 3
    assert set(nodes['bronze_platform']['depends_on']) == sensors
    assert nodes['dbt_platform']['depends_on'] == ['bronze_platform']
    assert nodes['dbt_platform']['selector'] == 'tag:platform'
    assert nodes['parity_platform']['depends_on'] == ['dbt_platform']
    assert len(nodes['parity_platform']['specs']) == 7
    config = yaml.safe_load((ROOT / 'dbt/dbt_project.yml').read_text())['models']['otterworks_lakehouse']
    for layer in ('silver', 'gold'):
        assert database(layer, 'platform') == layer + '_platform'
        assert delta_path(layer, 'platform', 'TEST').parts[-4:] == ('delta', layer, 'platform', 'test')
        assert config[layer]['platform']['+schema'] == layer + '_platform'
        assert config[layer]['platform']['+tags'] == ['platform']
    command = runner.command(nodes['bronze_platform'], tmp_path, DAY)
    assert command[-3:] == ['lakehouse.runtime.platform', '--business-date', DAY]
    for identity in sensors:
        node = dict(nodes[identity], timeout_seconds=1, poke_interval_seconds=1)
        assert graph.feed_path(node, tmp_path / 'unused', DAY) == platform.feed_path(node['table'])
        monkeypatch.setattr(runner.time, 'sleep', lambda _: None)
        with pytest.raises(TimeoutError, match='not ready'):
            runner.execute(node, tmp_path, DAY)
    feeds(tmp_path)
    for identity in sensors:
        runner.execute(nodes[identity], tmp_path, DAY)


def test_csv_empty_missing_and_invalid(tmp_path, monkeypatch):
    monkeypatch.setenv('PLATFORM_DBQL_LANDING', str(tmp_path))
    path = platform.feed_path('DBC_QRYLOG')
    columns = platform.FEEDS['DBC_QRYLOG'][1]
    with pytest.raises(FileNotFoundError):
        platform.read_feed(path, columns)
    feeds(tmp_path)
    assert platform.read_feed(path, columns) == []
    feeds(tmp_path, {'DBC_QRYLOG': [query(1)[:-1]]})
    assert platform.read_feed(path, columns)[0][11] == 'select "quoted"|value\nnext line'
    with path.open('w', newline='') as handle:
        csv.writer(handle).writerows([columns, ['short']])
    with pytest.raises(ValueError, match='field count'):
        platform.read_feed(path, columns)
    with path.open('w') as handle:
        handle.write('wrong,header\n')
    with pytest.raises(ValueError, match='header'):
        platform.read_feed(path, columns)


def test_empty_ingestion_retry_and_missing_feed(spark, tmp_path, monkeypatch):
    monkeypatch.setenv('PLATFORM_DBQL_LANDING', str(tmp_path))
    feeds(tmp_path)
    for _ in range(2):
        assert set(platform.ingest(spark, DAY).values()) == {0}
    feeds(tmp_path, {'DBC_QRYLOG': [query(1)[:-1]]})
    for _ in range(2):
        assert platform.ingest(spark, DAY)['bronze_platform.dbc_qrylog'] == 1
    raw = spark.table('bronze_platform.dbc_qrylog').first()
    assert raw._business_date == date(2026, 11, 9)
    assert raw.querytext == query(1)[11]
    assert raw._source_file == str(platform.feed_path('DBC_QRYLOG'))
    platform.feed_path('DBC_TABLESV').unlink()
    with pytest.raises(FileNotFoundError):
        platform.ingest(spark, DAY)
    assert spark.table('bronze_platform.dbc_qrylog').count() == 1


def test_empty_models(spark):
    models = Models(spark)
    for name in MODELS:
        assert models.rows(name) == []


def test_types_nulls_multiset_and_dates(spark):
    models = Models(spark)
    models.feed('DBC_QRYLOG', [query(1), query(2, day=date(2026, 11, 8))])
    row = models.rows('qrylogv')[0]
    assert row.queryid == 1 and row.ampcputime == Decimal('123.123456')
    assert row.collecttimestamp.microsecond == 123456
    assert row.firstresptime.microsecond == 654321
    assert row.querytext == query(1)[11]
    edges = [(None, None, 'Table', 'T', 'READ', date(2026, 11, 9))] * 2
    models.feed('DBC_QRYLOGOBJECTS', edges)
    assert len(models.rows('qrylogobjectsv')) == 2
    assert all(row.queryid is None and row.objectdatabasename is None
               for row in models.rows('qrylogobjectsv'))
    models.feed('DBC_QRYLOGOBJECTS', [('1', 'Db', 'Table', '', 'READ', date(2026, 11, 9))])
    assert models.rows('qrylogobjectsv')[0].objecttype == ' '
    models.feed('DBC_TABLESV', [('Db', 'TaBlE', 'V', None, None, None, date(2026, 11, 9))])
    row = models.rows('tablesv')[0]
    assert row.databasename == 'Db' and row.tablename == 'TaBlE'
    assert row.createtimestamp is None and row.accesscount is None
    models.feed('DBC_QRYLOG', [query(1, error='invalid')])
    with pytest.raises(Exception, match='CAST_INVALID_INPUT|cannot be cast'):
        models.rows('dbc_qrylog')


def test_consumer_window_case_grouping_and_order(spark):
    models = Models(spark)
    models.feed('DBC_QRYLOG', [
        query(1, username='MiXeD '), query(2, username='mixed', statement='select '),
        query(3, username='mixed', appid='app'), query(4, username='mixed', clientid='client'),
        query(5, username='A', start='2026-11-09 23:59:59.999999'),
        query(6, start='2026-10-10 23:59:59.999999'),
        query(7, start='2026-11-10 00:00:00'), query(8, error='1'),
        query(9, statement='INSERT'), query(10, start=None), query(11, username=None),
    ])
    rows = models.rows('consumer_reads')
    assert [(r.username, r.read_queries) for r in rows] == [
        ('mixed', 2), ('a', 1), ('mixed', 1), ('mixed', 1), (None, 1)]
    assert rows[0].reads_per_day == Decimal('0.07')
    assert {r.appid for r in rows} == {'App', 'app'}
    assert {r.clientid for r in rows} == {'Client', 'client'}
    models.variables.update(dbql_window_start='2026-11-10 00:00:00',
                            dbql_window_end='2026-11-11 00:00:00')
    models.built.clear()
    result = models.rows('consumer_reads')
    assert len(result) == 1 and result[0].read_queries == 1


def test_parity_multiset_preserves_duplicate_null_edges(spark):
    models = Models(spark)
    models.feed('DBC_QRYLOGOBJECTS', [(None, 'Db', 'Table', 'T', None, date(2026, 11, 9))] * 2)
    models.ref('dbc_qrylogobjects')
    spec = yaml.safe_load((ROOT / 'parity/specs/platform/dbc_qrylogobjects.yaml').read_text())
    sql = spec['lakehouse']['sql'].replace('silver_platform.dbc_qrylogobjects',
                                        'platform_test_dbc_qrylogobjects')
    frame = spark.sql(sql)
    rows = [r.asDict() for r in frame.collect()]
    assert len(rows) == 2 and compare(rows, rows, spec, frame.columns, frame.columns)['passed']
    assert not compare(rows, rows[:1], spec, frame.columns, frame.columns)['passed']
