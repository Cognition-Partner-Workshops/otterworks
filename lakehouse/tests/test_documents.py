import csv
import json
import os
import shutil
import uuid
from datetime import date

import pytest
import yaml
from jinja2 import Environment, StrictUndefined

from lakehouse.orchestration.graph import load
from lakehouse.parity.engine import compare
from lakehouse.parity.spec import discover
from lakehouse.runtime.ingest import ingest
from lakehouse.runtime.layout import ROOT, data_root
from lakehouse.runtime.session import create_session
from warehouse.seed.columns import TABLES


TABLES = [table for table in TABLES if table.area == 'documents']


@pytest.fixture(scope='module')
def spark():
    original = os.environ.get('NS')
    os.environ['NS'] = 'test-documents-' + uuid.uuid4().hex
    session = create_session()
    yield session
    session.stop()
    shutil.rmtree(data_root())
    if original is None:
        del os.environ['NS']
    else:
        os.environ['NS'] = original


def model(spark, name, day='20261109'):
    paths = list((ROOT / 'dbt/models').glob(f'*/documents/{name}.sql'))
    macros = '\n'.join(path.read_text() for path in (ROOT / 'dbt/macros').glob('*.sql'))
    def reference(target):
        model(spark, target, day).createOrReplaceTempView('documents_test_' + target)
        return 'documents_test_' + target
    sql = Environment(undefined=StrictUndefined).from_string(macros + paths[0].read_text()).render(
        source=lambda _, table: 'documents_input_' + table,
        ref=reference, env_var=lambda _: day, config=lambda **_: '')
    return spark.sql(sql)


def input_rows(spark, table, rows):
    schema = ', '.join(f'{column.name.lower()} string' for column in table.columns)
    schema += ', _business_date date'
    spark.createDataFrame(rows, schema).createOrReplaceTempView('documents_input_' + table.name.lower())


@pytest.mark.parametrize('table', TABLES, ids=lambda table: table.name)
def test_document_snapshots(spark, table):
    values = {'B': '1', 'I': '2', 'D': '2026-11-09', 'T': '2026-11-09 12:00:00'}
    row = [values.get(column.kind, 'Text|\nCase') for column in table.columns]
    input_rows(spark, table, [tuple(row + [date(2026, 11, 9)]), tuple(row + [date(2026, 11, 10)])])
    name = table.name.lower()
    assert model(spark, 'stg_' + name).count() == 1
    result = model(spark, name)
    assert result.count() == (0 if name == 'search_index_log' else 1)
    if name != 'search_index_log':
        assert result.first()[0] == 1
        for column in table.columns:
            if column.kind.startswith('C'):
                assert result.first()[column.name.lower()] == row[table.columns.index(column)][:int(column.kind[1:])].ljust(int(column.kind[1:]))
    input_rows(spark, table, [])
    assert model(spark, 'stg_' + name).count() == 0
    assert model(spark, name).count() == 0
    row[0] = 'bad-id'
    input_rows(spark, table, [tuple(row + [date(2026, 11, 9)])])
    with pytest.raises(Exception, match='CAST_INVALID_INPUT'):
        model(spark, 'stg_' + name).collect()


def test_document_version_order_and_ties(spark):
    table = next(table for table in TABLES if table.name == 'DOC_VERSION')
    rows = [('1', '5', '1', '2026-11-08 00:00:00', '10', 'a'),
            ('2', '5', '2', '2026-11-09 00:00:00', '20', 'b'),
            ('3', '5', '3', '2026-11-09 00:00:00', '30', 'c'),
            ('9', '6', '1', '2026-11-08 00:00:00', '10', 'd'),
            ('7', '6', '2', '2026-11-09 00:00:00', '20', 'e'),
            ('6', '6', '3', '2026-11-09 00:00:00', '30', 'f')]
    input_rows(spark, table, [row + (date(2026, 11, 9),) for row in rows])
    assert {row.document_id: row.version_id for row in model(spark, 'doc_version').collect()} == {5: 3, 6: 7}
    input_rows(spark, table, [rows[0] + (date(2026, 11, 9),),
                              ('4', '5', '4', None, '40', 'd', date(2026, 11, 9))])
    assert model(spark, 'doc_version').first().version_id == 4
    input_rows(spark, table, [('5', '5', '5', '2026-11-09 12:00:00.500001', '40', 'd', date(2026, 11, 9))])
    assert str(model(spark, 'stg_doc_version').first().version_ts) == '2026-11-09 12:00:01'


def test_document_text_and_load_failures(spark, tmp_path):
    table = next(table for table in TABLES if table.name == 'FOLDER')
    input_rows(spark, table, [('1', None, None, 'x' * 150, '2026-11-09', date(2026, 11, 9))])
    assert model(spark, 'folder').first().folder_name == 'x' * 100
    assert model(spark, 'folder').first().owner_user_id is None
    input_rows(spark, table, [('1', None, None, 'x' * 201, '2026-11-09', date(2026, 11, 9))])
    with pytest.raises(Exception, match='exceeds VARCHAR'):
        model(spark, 'stg_folder').collect()
    input_rows(spark, table, [('1', None, None, '', 'bad-date', date(2026, 11, 9))])
    with pytest.raises(Exception, match='CAST_INVALID_INPUT'):
        model(spark, 'stg_folder').collect()
    path = tmp_path / 'documents/FOLDER'
    path.mkdir(parents=True)
    with (path / '20261109.psv').open('w', newline='') as handle:
        csv.writer(handle, delimiter='|').writerow(['1', '', '', 'Name|quoted\nline', '2026-11-09'])
    ingest(spark, tmp_path, '20261109', ['FOLDER'])
    assert spark.table('bronze_documents.folder').first().folder_name == 'Name|quoted\nline'
    with pytest.raises(FileNotFoundError):
        ingest(spark, tmp_path, '20261110', ['FOLDER'])
    (path / '20261109.psv').write_text('bad|row\n')
    with pytest.raises(ValueError, match='expected 5'):
        ingest(spark, tmp_path, '20261109', ['FOLDER'])


def test_storage_set_and_macro_boundaries(spark):
    table = next(table for table in TABLES if table.name == 'STORAGE_USAGE_DAILY')
    rows = [('1', '7', '8', '2026-10-31', '100', '1'),
            ('2', '7', '8', '2026-11-01', '200', '2'),
            ('3', '7', '8', '2026-11-30', '300', '3'),
            ('4', '7', '8', '2026-12-01', '400', '4')]
    input_rows(spark, table, [row + (date(2026, 11, 9),) for row in rows + [rows[1]]])
    assert model(spark, 'storage_usage_daily').count() == 4
    assert tuple(model(spark, 'm_storage_totals').first()) == (7, 500, 5)
    model(spark, 'storage_usage_daily').createOrReplaceTempView('documents_usage')
    macro = (ROOT / 'dbt/macros/documents_storage_totals.sql').read_text()
    query = Environment().from_string(macro + "{{ documents_storage_totals(\"date '2026-10-31'\", \"date '2026-11-01'\") }}").render(ref=lambda _: 'documents_usage')
    assert tuple(spark.sql(query).first()) == (7, 100, 1)
    input_rows(spark, table, [])
    assert model(spark, 'm_storage_totals').count() == 0


def test_documents_graph_and_ownership():
    specs = {key: value for key, value in discover().items() if key.startswith('documents.')}
    assert len(specs) == 35
    nodes = {node['id']: node for dag in load().values() for node in dag['nodes']}
    for identity in specs:
        target = ('dbt_spark_' + identity.removeprefix('documents.spark_')
                  if identity.startswith('documents.spark_') else 'dbt_documents')
        assert nodes['parity_' + identity.replace('.', '_')]['depends_on'] == [target]
    owned = yaml.safe_load((ROOT / 'coverage/domains/documents.yaml').read_text())['legacy_objects']
    assert len(owned) == len(set(owned)) == 97
    assert not any('10_storage_monthly' in identity for identity in owned)
    assert not any(identity.startswith('batch_runner:') for identity in owned)
    assert set().union(*(set(spec['legacy_objects']) for _, spec in specs.values())) <= set(owned)
    search = (ROOT / 'dbt/models/silver/documents/search_index_log.sql').read_text()
    assert "incremental_strategy='append'" in search and 'where false' in search


def test_storage_multiset_parity(spark):
    table = next(table for table in TABLES if table.name == 'STORAGE_USAGE_DAILY')
    rows = [('1', '7', '8', '2026-11-09', '100', '1'),
            ('1', '7', '8', '2026-11-09', '100', '1'),
            (None, None, '8', '2026-11-09', '200', '2')]
    input_rows(spark, table, [row + (date(2026, 11, 9),) for row in rows])
    model(spark, 'stg_storage_usage_daily').createOrReplaceTempView('documents_multiset')
    spec = json.loads((ROOT / 'parity/specs/documents/stg_storage_usage_daily.yaml').read_text())
    query = spec['lakehouse']['sql'].replace('silver_documents.stg_storage_usage_daily', 'documents_multiset')
    actual = [row.asDict() for row in spark.sql(query).collect()]
    expected = [dict(zip(spec['columns'], row)) for row in [
        (None, None, 8, date(2026, 11, 9), 200, 2, 1),
        (1, 7, 8, date(2026, 11, 9), 100, 1, 2),
        (1, 7, 8, date(2026, 11, 9), 100, 1, 3)]]
    assert compare(expected, actual, spec)['passed']
    assert not compare(expected[:-1], actual, spec)['passed']
